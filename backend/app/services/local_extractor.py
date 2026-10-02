"""Conservative extractive baseline that works without network credentials.

All text is copied from real source lines. Only explicit linguistic patterns
create actions/decisions/risks; ambiguous proposals are labelled for review.
"""

import re

from app.schemas.intelligence import (
    ActionClaim,
    Claim,
    DecisionClaim,
    Evidence,
    ExtractionOutput,
    RiskClaim,
    Sentiment,
)
from app.services.preprocessing import speaker_line

DATE_PATTERN = r"\b(?:\d{4}-\d{2}-\d{2}|(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|(?:next\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))|tomorrow|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?)\b"
DATE_RE = re.compile(DATE_PATTERN, re.I)
DUE_RE = re.compile(r"\b(?:by|due(?:\s+on)?|deadline(?:\s+is)?|on)\s+(" + DATE_PATTERN + r")", re.I)
ACTION_RE = re.compile(
    r"(?i:\b(?:action(?: item)?\s*:|I will|we will|I\'ll|I shall|assigned to|responsible for|we should|someone should|needs to|need to)\b)|\b[A-Z][\w\'-]+(?:\s+[A-Z][\w\'-]+)?\s+(?:will|shall|to)\s+\w"
)
TOPIC_WORDS = [
    "deployment",
    "dashboard",
    "authentication",
    "API",
    "design",
    "testing",
    "onboarding",
    "budget",
    "security",
    "migration",
    "analytics",
    "sprint",
    "database",
    "accessibility",
    "launch",
]


def make_claim(text: str, quote: str, line: int, confidence: float = 0.9) -> Claim:
    return Claim(
        text=text[:4000],
        evidence=[Evidence(quote=quote[:5000], line_start=line, line_end=line)],
        confidence=confidence,
    )


def explicit_owner(content: str, speaker: str | None) -> str:
    if speaker and re.search(r"\b(?:I will|I'll|I shall|I am responsible for)\b", content, re.I):
        return speaker
    match = re.search(
        r"(?:^|Action(?: item)?:\s*)([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)\s+(?:will|shall|to|is responsible for)\b",
        content,
    )
    if match and match.group(1).casefold() not in {"we", "i", "someone", "team", "action"}:
        return match.group(1)
    match = re.search(r"\b(?:assigned to|owner:)\s*([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)", content)
    return match.group(1) if match else "Unassigned"


def extract_local(
    text: str, start_line: int = 1, participants: list[str] | None = None, project: str = ""
) -> ExtractionOutput:
    groups: dict[str, list] = {
        key: [] for key in ExtractionOutput.model_fields if key != "sentiment"
    }
    positive, concern = [], []
    people: set[str] = set()
    topics: set[str] = set()
    for number, raw in enumerate(text.splitlines(), start_line):
        line = raw.strip()
        if not line or line.startswith("[Document:"):
            continue
        speaker, content = speaker_line(line)
        if not content:
            continue
        if speaker and speaker.casefold() not in people:
            people.add(speaker.casefold())
            groups["people"].append(make_claim(speaker, line, number))
        lower = content.casefold()
        claim = make_claim(content, line, number)
        if len(content) >= 20:
            groups["key_points"].append(claim)
        rejected = bool(
            re.search(r"\b(?:rejected proposal|reject(?:ed)?|ruled out|decided against)\b", lower)
        )
        tentative = bool(
            re.search(
                r"\b(?:tentative decision|tentatively|proposal|proposed|considering|might)\b", lower
            )
        )
        confirmed = bool(
            re.search(r"\b(?:decision:|decided|agreed|approved|confirmed)\b", lower)
        ) and not re.search(
            r"\b(?:not|haven't|haven’t)\s+(?:decided|agreed|approved|confirmed)\b", lower
        )
        if rejected or tentative or confirmed:
            kind = "Rejected" if rejected else "Tentative" if tentative else "Confirmed"
            groups["decisions"].append(DecisionClaim(**claim.model_dump(), decision_type=kind))
        if (
            (ACTION_RE.search(content) or lower.startswith("action:"))
            and not re.search(r"^(?:open question|unanswered question|question):", lower)
            and not (
                (confirmed or tentative or rejected)
                and not re.search(r"\b(?:action:|I will|I\'ll|commitment:)\b", content, re.I)
            )
        ):
            owner = explicit_owner(content, speaker)
            due = DUE_RE.search(content)
            priority_match = re.search(
                r"\b(critical|high|medium|low)\s+priority\b|\bpriority[: ]+(critical|high|medium|low)\b",
                lower,
            )
            priority = (
                next(g for g in priority_match.groups() if g).title()
                if priority_match
                else "Medium"
            )
            status = "Pending"
            for needle, value in [
                (r"\bcancelled\b", "Cancelled"),
                (r"\bcompleted\b|\balready done\b", "Completed"),
                (r"\bin progress\b", "In Progress"),
                (r"\bblocked\b", "Blocked"),
            ]:
                if re.search(needle, lower):
                    status = value
                    break
            deps = (
                [claim]
                if re.search(r"\b(?:depends on|dependent on|after .+ is|waiting for)\b", lower)
                else []
            )
            groups["action_items"].append(
                ActionClaim(
                    **claim.model_dump(),
                    owner=owner,
                    owner_evidence=line if owner != "Unassigned" else "",
                    due_date=due.group(1) if due else "Not specified",
                    due_date_evidence=line if due else "",
                    priority=priority,
                    priority_evidence=line if priority_match else "",
                    status=status,
                    status_evidence=line if status != "Pending" else "",
                    dependencies=deps,
                )
            )
        risk_pattern = r"\b(?:risk|blocker|blocked|depends on|dependency|delay|understaffed|unresolved issue|waiting for|capacity shortage)\b"
        if re.search(risk_pattern, lower) and not re.search(
            r"\b(?:no|without|resolved)\s+(?:risks?|blockers?)\b", lower
        ):
            category = (
                "Blocker"
                if re.search(r"\bblock(?:er|ed)\b", lower)
                else "Dependency"
                if re.search(r"\b(?:depends on|dependency|waiting for)\b", lower)
                else "Resource"
                if re.search(r"\b(?:understaffed|capacity|resource)\b", lower)
                else "Technical"
                if re.search(r"\b(?:latency|bug|security|technical|error)\b", lower)
                else "Delivery"
                if re.search(r"\b(?:delay|deadline|delivery|launch)\b", lower)
                else "Unresolved issue"
            )
            severity = re.search(
                r"\b(low|medium|high|critical)\s+(?:severity|risk)\b|\bseverity\s*:\s*(low|medium|high|critical)\b",
                content,
                re.I,
            )
            groups["risks"].append(
                RiskClaim(
                    **claim.model_dump(),
                    category=category,
                    severity=(severity.group(1) or severity.group(2)).title()
                    if severity
                    else "Unknown",
                    severity_evidence=line[:5000] if severity else "",
                )
            )
        if "?" in content or re.search(
            r"\b(?:open question|unanswered question|unanswered:)\b", lower
        ):
            # Only explicit answers resolve a question in this baseline.
            later = text.splitlines()[number - start_line + 1 :]
            if not any(
                re.match(r"\s*(?:\w+:\s*)?(?:Answer|Answered):", other, re.I) for other in later[:3]
            ):
                groups["questions"].append(claim)
        if re.search(r"\b(?:follow.up|follow up|next meeting|revisit)\b", lower):
            groups["follow_ups"].append(claim)
        if re.search(r"\b(?:commitment|commit to|promise|I will|I'll|we will)\b", content, re.I):
            groups["commitments"].append(claim)
        if re.search(r"\b(?:depends on|dependency|waiting for|dependent on)\b", lower):
            groups["dependencies"].append(claim)
        for match in DATE_RE.finditer(content):
            groups["important_dates"].append(make_claim(match.group(), line, number))
        project_match = re.search(r"\bProject:\s*([\w -]+?)(?:[.;]|$)", content, re.I)
        if project_match:
            groups["projects"].append(make_claim(project_match.group(1).strip(), line, number))
        elif project and re.search(r"\b" + re.escape(project) + r"\b", content, re.I):
            if not any(item.text.casefold() == project.casefold() for item in groups["projects"]):
                groups["projects"].append(make_claim(project, line, number))
        for name in participants or []:
            if name.casefold() not in people and re.search(
                r"\b" + re.escape(name) + r"\b", content, re.I
            ):
                people.add(name.casefold())
                groups["people"].append(make_claim(name, line, number))
        explicit_topic = re.search(r"\bTopic:\s*([^.;]+)", content, re.I)
        names = (
            [explicit_topic.group(1).strip()]
            if explicit_topic
            else [
                word
                for word in TOPIC_WORDS
                if re.search(r"\b" + re.escape(word) + r"\b", content, re.I)
            ]
        )
        for name in names:
            if name.casefold() not in topics:
                topics.add(name.casefold())
                groups["topics"].append(make_claim(name, line, number))
        if re.search(r"\b(?:worried|concerned|frustrated)\b", lower):
            concern.extend(claim.evidence)
        if re.search(r"\b(?:happy|pleased|excited|great progress)\b", lower):
            positive.extend(claim.evidence)
    salient = groups["decisions"] + groups["action_items"] + groups["risks"] + groups["key_points"]
    unique = []
    seen = set()
    for item in salient:
        if item.text.casefold() not in seen:
            unique.append(
                Claim(**{key: item.model_dump()[key] for key in ("text", "evidence", "confidence")})
            )
            seen.add(item.text.casefold())
    groups["three_line_summary"] = unique[:3]
    groups["executive_summary"] = unique[:5]
    groups["detailed_summary"] = groups["key_points"][:30]
    groups["bullet_summary"] = unique[:10]
    limits = {
        "decisions": 50,
        "action_items": 80,
        "risks": 50,
        "questions": 40,
        "key_points": 30,
        "follow_ups": 30,
        "commitments": 30,
        "dependencies": 30,
        "projects": 30,
        "people": 80,
        "important_dates": 40,
        "topics": 30,
    }
    for name, limit in limits.items():
        groups[name] = groups[name][:limit]
    if concern and positive:
        sentiment = Sentiment(
            label="Mixed",
            description="Explicit positive and concerned language appears in the transcript.",
            evidence=(positive + concern)[:5],
        )
    elif concern:
        sentiment = Sentiment(
            label="Concerned",
            description="The transcript contains explicit expressions of concern.",
            evidence=concern[:5],
        )
    elif positive:
        sentiment = Sentiment(
            label="Positive",
            description="The transcript contains explicit positive expressions.",
            evidence=positive[:5],
        )
    else:
        sentiment = Sentiment(
            label="Not enough evidence",
            description="No explicit tone signals detected; no mood or personality is inferred.",
            evidence=[],
        )
    return ExtractionOutput(**groups, sentiment=sentiment)
