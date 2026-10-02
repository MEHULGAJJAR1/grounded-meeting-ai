"""Independent source validation, entailment verification and conservative scoring.

Missing/unsupported metadata is reset to explicit sentinels. Unsupported claims
are withheld from result collections and preserved in the review report.
"""

from datetime import date, datetime
import hashlib
import re
from typing import Callable

from app.schemas.intelligence import ExtractionOutput
from app.services.ai_service import OpenAIService
from app.services.preprocessing import speaker_line


def canonical(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def locate_evidence(quote: str, transcript: str) -> dict | None:
    """Allow whitespace/case normalization only, never fuzzy semantic matching."""
    if not quote.strip():
        return None
    offset = transcript.find(quote)
    end = offset + len(quote)
    if offset < 0:
        pieces = re.split(r"\s+", quote.strip())
        pattern = r"\s+".join(re.escape(part) for part in pieces)
        match = re.search(pattern, transcript, re.I)
        if not match:
            return None
        offset, end = match.span()
    headers = list(re.finditer(r"\[Document: (.*?) \| (page|section) (\d+)\]", transcript[:offset]))
    return {
        "quote": transcript[offset:end],
        "line_start": transcript.count("\n", 0, offset) + 1,
        "line_end": transcript.count("\n", 0, end) + 1,
        "filename": headers[-1].group(1) if headers else None,
        "page": int(headers[-1].group(3)) if headers and headers[-1].group(2) == "page" else None,
        "section": int(headers[-1].group(3))
        if headers and headers[-1].group(2) == "section"
        else None,
    }


def explicit_calendar_date(value: str) -> date | None:
    # A relative day, missing year or numeric ambiguity is retained as literal text.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def owner_is_explicit(owner: str, evidence: str) -> bool:
    if not re.search(r"\b" + re.escape(owner) + r"\b", evidence, re.I):
        return False
    speaker, content = speaker_line(evidence)
    if (
        speaker
        and speaker.casefold() == owner.casefold()
        and re.search(r"\b(?:I will|I'll|I shall|I am responsible for)\b", content, re.I)
    ):
        return True
    patterns = [
        r"\b" + re.escape(owner) + r"\s+(?:will|shall|to|is responsible for)\b",
        r"\b(?:assigned to|owner:)\s*" + re.escape(owner) + r"\b",
    ]
    return any(re.search(pattern, evidence, re.I) for pattern in patterns)


def deadline_is_explicit(value: str, evidence: str) -> bool:
    if canonical(value) not in canonical(evidence):
        return False
    return bool(
        re.search(
            r"\b(?:by|due(?:\s+on)?|deadline(?:\s+is)?|on)\s+" + re.escape(value), evidence, re.I
        )
    )


def literal_verdict(kind: str, item: dict, quotes: list[dict]) -> tuple[str, str, float]:
    joined = " ".join(e["quote"] for e in quotes)
    if canonical(item["text"]) not in canonical(joined):
        return (
            "uncertain",
            "Local mode can verify literal excerpts, not paraphrased entailment",
            0.55,
        )
    if (
        kind == "action_items"
        and re.search(r"\b(?:should|could|might|someone|needs? to)\b", joined, re.I)
        and not re.search(r"\b(?:will|I'll|action:)\b", joined, re.I)
    ):
        return "uncertain", "Proposed or ambiguous action; commitment is not explicit", 0.55
    if kind == "questions" and not re.search(
        r"\b(?:open question|unanswered|still don't know|still unknown)\b", joined, re.I
    ):
        return "uncertain", "Question is explicit, but unanswered status needs review", 0.6
    if kind == "decisions":
        decision_type = item["decision_type"]
        tentative = re.search(
            r"\b(?:tentative|tentatively|propos(?:al|ed)|might|considering)\b", joined, re.I
        )
        rejected = re.search(r"\b(?:reject(?:ed)?|ruled out|against)\b", joined, re.I)
        if decision_type == "Confirmed" and (tentative or rejected):
            return "unsupported", "Source does not support a confirmed decision", 0.1
    return "supported", "Claim is a literal source excerpt with valid evidence", 0.95


def verify_extraction(
    extraction: ExtractionOutput,
    transcript: str,
    provider: str = "local",
    progress: Callable[[str, int], None] | None = None,
) -> tuple[dict, dict]:
    raw = extraction.model_dump()
    records: list[dict] = []
    record_map: dict[str, dict] = {}
    pointers: dict[tuple[str, int], str] = {}
    for kind, items in raw.items():
        if kind == "sentiment":
            continue
        for index, item in enumerate(items):
            key_data = (
                canonical(item["text"])
                + "|"
                + "|".join(canonical(e["quote"]) for e in item["evidence"])
            )
            if kind in {"decisions", "action_items", "questions", "risks"}:
                key_data += (
                    "|"
                    + kind
                    + "|"
                    + str(
                        {
                            k: v
                            for k, v in item.items()
                            if k not in {"text", "evidence", "confidence"}
                        }
                    )
                )
            identity = hashlib.sha256(key_data.encode()).hexdigest()[:16]
            pointers[(kind, index)] = identity
            if identity in record_map:
                continue
            evidence = []
            missing = False
            for source in item["evidence"]:
                location = locate_evidence(source["quote"], transcript)
                if location:
                    evidence.append(location)
                else:
                    missing = True
            record = {
                "id": identity,
                "kind": kind,
                "text": item["text"],
                "item": item,
                "evidence": evidence,
                "verdict": "unsupported" if missing or not evidence else "uncertain",
                "reason": "A cited quote is absent from the transcript"
                if missing or not evidence
                else "Awaiting verification",
                "score": 0.0 if missing or not evidence else 0.5,
            }
            records.append(record)
            record_map[identity] = record
    verifiable = [
        record
        for record in records
        if record["evidence"] and record["reason"] == "Awaiting verification"
    ]
    if provider == "openai" and verifiable:
        service = OpenAIService()
        for offset in range(0, len(verifiable), 10):
            batch = verifiable[offset : offset + 10]
            payload = []
            for record in batch:
                item = record["item"]
                # Core task and editable metadata are independently assessed. A
                # fabricated owner must not erase an otherwise valid task; it is
                # reset below, with a visible field-level correction instead.
                core = {
                    key: value
                    for key, value in item.items()
                    if key in {"text", "evidence", "decision_type", "category", "dependencies"}
                }
                payload.append(
                    {
                        "claim_id": record["id"],
                        "kind": record["kind"],
                        "claim": core,
                        "verified_quotes": record["evidence"],
                    }
                )
                record["field_checks"] = {}
                if record["kind"] == "action_items":
                    for field, fallback in (
                        ("owner", "Unassigned"),
                        ("due_date", "Not specified"),
                        ("priority", "Medium"),
                        ("status", "Pending"),
                    ):
                        metadata_quote = item.get(field + "_evidence", "")
                        location = locate_evidence(metadata_quote, transcript)
                        if location:
                            payload.append(
                                {
                                    "claim_id": record["id"] + ":" + field,
                                    "kind": "explicit task " + field,
                                    "claim": {
                                        "text": f"The {field} explicitly stated for THIS task is {item[field]}.",
                                        "task": item["text"],
                                        "value": item[field],
                                        "evidence": [location],
                                    },
                                    "verified_quotes": record["evidence"] + [location],
                                }
                            )
                if record["kind"] == "risks" and item["severity"] != "Unknown":
                    location = locate_evidence(item.get("severity_evidence", ""), transcript)
                    if location:
                        payload.append(
                            {
                                "claim_id": record["id"] + ":severity",
                                "kind": "explicit risk severity",
                                "claim": {
                                    "text": f"The severity explicitly stated for THIS risk is {item['severity']}.",
                                    "risk": item["text"],
                                    "value": item["severity"],
                                    "evidence": [location],
                                },
                                "verified_quotes": record["evidence"] + [location],
                            }
                        )
            # Full-meeting context is required: later answers, reversals and
            # corrections can invalidate a seemingly entailed local quote.
            checks = service.verify(payload, transcript).checks
            mapping = {check.claim_id: check for check in checks}
            for record in batch:
                check = mapping.get(record["id"])
                if not check:
                    record.update(
                        verdict="uncertain",
                        reason="Independent verifier omitted this claim",
                        score=0.35,
                    )
                else:
                    record.update(verdict=check.verdict, reason=check.reason, score=check.score)
                for field in ("owner", "due_date", "priority", "status", "severity"):
                    metadata_check = mapping.get(record["id"] + ":" + field)
                    record["field_checks"][field] = bool(
                        metadata_check and metadata_check.verdict == "supported"
                    )
            if progress:
                progress(
                    "Grounding verification",
                    62 + int(14 * min(offset + len(batch), len(verifiable)) / len(verifiable)),
                )
    else:
        for record in verifiable:
            verdict, reason, score = literal_verdict(
                record["kind"], record["item"], record["evidence"]
            )
            if record["kind"] == "questions":
                last_line = max(e["line_end"] for e in record["evidence"])
                if any(
                    re.search(r"(?:^|:\s*)(?:Answer|Answered):", line, re.I)
                    for line in transcript.splitlines()[last_line:]
                ):
                    verdict, reason, score = (
                        "uncertain",
                        "A later explicit answer marker exists; unanswered status needs review",
                        0.5,
                    )
            record.update(verdict=verdict, reason=reason, score=score)
    result: dict = {}
    corrections: list[dict] = []
    entries: list[dict] = []
    for kind, items in raw.items():
        if kind == "sentiment":
            continue
        result[kind] = []
        for index, item in enumerate(items):
            record = record_map[pointers[(kind, index)]]
            if record["verdict"] == "unsupported":
                continue
            grounded = dict(item)
            grounded["evidence"] = record["evidence"]
            # Confidence is deliberately capped; it is a support heuristic, not a probability.
            confidence = (
                round(min(0.97, 0.45 + 0.5 * record["score"]), 3)
                if record["verdict"] == "supported"
                else min(0.6, record["score"])
            )
            grounded["grounding_status"] = (
                "verified" if record["verdict"] == "supported" else "review"
            )
            grounded["confidence"] = confidence
            if kind == "risks" and grounded["severity"] != "Unknown":
                source = grounded.get("severity_evidence", "")
                location = locate_evidence(source, transcript)
                supported = location and re.search(
                    r"\b" + re.escape(grounded["severity"]) + r"\b", source, re.I
                )
                if provider == "openai":
                    supported = supported and record.get("field_checks", {}).get("severity", False)
                if not supported:
                    corrections.append(
                        {
                            "claim_id": record["id"],
                            "field": "severity",
                            "kind": "risks",
                            "text": grounded["text"],
                            "original_value": grounded["severity"],
                            "fallback": "Unknown",
                            "verdict": "unsupported",
                            "reason": "Unsupported risk severity reset to Unknown",
                            "confidence": 0.1,
                        }
                    )
                    grounded.update(
                        severity="Unknown",
                        severity_evidence="",
                        confidence=min(grounded["confidence"], 0.55),
                        grounding_status="review",
                    )
            if kind == "action_items":
                for field, fallback in (("owner", "Unassigned"), ("due_date", "Not specified")):
                    original = grounded[field].strip() or fallback
                    source = grounded.get(field + "_evidence", "")
                    location = locate_evidence(source, transcript)
                    supported = original == fallback or (
                        location
                        and (
                            owner_is_explicit(original, location["quote"])
                            if field == "owner"
                            else deadline_is_explicit(original, location["quote"])
                        )
                    )
                    if provider == "openai" and original != fallback:
                        supported = supported and record.get("field_checks", {}).get(field, False)
                    if not supported:
                        corrections.append(
                            {
                                "claim_id": record["id"],
                                "kind": "action_items",
                                "text": grounded["text"],
                                "field": field,
                                "original_value": original,
                                "fallback": fallback,
                                "reason": f"{field.replace('_', ' ').title()} is not explicitly supported; reset to {fallback}",
                                "verdict": "unsupported",
                                "confidence": 0.1,
                            }
                        )
                        grounded[field] = fallback
                        grounded[field + "_evidence"] = ""
                        grounded["confidence"] = min(grounded["confidence"], 0.55)
                        grounded["grounding_status"] = "review"
                    else:
                        grounded[field] = original
                for field, fallback in (("priority", "Medium"), ("status", "Pending")):
                    source = grounded.get(field + "_evidence", "")
                    location = locate_evidence(source, transcript)
                    if not source:
                        if grounded[field] != fallback:
                            corrections.append(
                                {
                                    "claim_id": record["id"],
                                    "field": field,
                                    "original_value": grounded[field],
                                    "fallback": fallback,
                                    "kind": "action_items",
                                    "text": grounded["text"],
                                    "reason": "Non-default task metadata has no source quote",
                                    "verdict": "unsupported",
                                    "confidence": 0.1,
                                }
                            )
                            grounded["confidence"] = min(grounded["confidence"], 0.55)
                            grounded["grounding_status"] = "review"
                        grounded[field] = fallback
                        grounded[field + "_provenance"] = "application_default"
                    else:
                        value = grounded[field]
                        match_value = re.search(r"\b" + re.escape(value) + r"\b", source, re.I)
                        negated = re.search(r"\bnot\s+(?:yet\s+)?" + re.escape(value), source, re.I)
                        independent_support = provider != "openai" or record.get(
                            "field_checks", {}
                        ).get(field, False)
                        if not location or not match_value or negated or not independent_support:
                            if value != fallback or source:
                                corrections.append(
                                    {
                                        "claim_id": record["id"],
                                        "field": field,
                                        "original_value": value,
                                        "fallback": fallback,
                                        "kind": "action_items",
                                        "text": grounded["text"],
                                        "reason": "Unsupported task state reset to application default",
                                        "verdict": "unsupported",
                                        "confidence": 0.1,
                                    }
                                )
                            grounded[field] = fallback
                            grounded[field + "_evidence"] = ""
                            grounded["confidence"] = min(grounded["confidence"], 0.55)
                            grounded["grounding_status"] = "review"
                            grounded[field + "_provenance"] = "application_default"
                        else:
                            grounded[field + "_provenance"] = "transcript"
                dependency_results = []
                for dep in grounded["dependencies"]:
                    ev = [locate_evidence(e["quote"], transcript) for e in dep["evidence"]]
                    if (
                        ev
                        and all(ev)
                        and canonical(dep["text"]) in canonical(" ".join(e["quote"] for e in ev))
                    ):
                        dependency_results.append(
                            {**dep, "evidence": ev, "grounding_status": "verified"}
                        )
                    else:
                        corrections.append(
                            {
                                "claim_id": record["id"],
                                "field": "dependencies",
                                "kind": "action_items",
                                "text": dep["text"],
                                "original_value": dep["text"],
                                "fallback": "Withheld",
                                "reason": "Dependency lacks literal support",
                                "verdict": "unsupported",
                                "confidence": 0.1,
                            }
                        )
                grounded["dependencies"] = dependency_results
            result[kind].append(grounded)
    for record in records:
        entries.append(
            {
                "id": record["id"],
                "kind": record["kind"],
                "text": record["text"],
                "verdict": record["verdict"],
                "reason": record["reason"],
                "confidence": round(record["score"], 3),
                "evidence": record["evidence"],
            }
        )
    sentiment = raw["sentiment"]
    tone_evidence = [locate_evidence(e["quote"], transcript) for e in sentiment["evidence"]]
    if sentiment["label"] != "Not enough evidence":
        supported = bool(tone_evidence) and all(tone_evidence)
        if supported and provider == "openai":
            verdict = (
                OpenAIService()
                .verify(
                    [{"claim_id": "sentiment", "kind": "tone overview", "claim": sentiment}],
                    "\n".join(e["quote"] for e in tone_evidence),
                )
                .checks
            )
            supported = len(verdict) == 1 and verdict[0].verdict == "supported"
        if not supported:
            corrections.append(
                {
                    "claim_id": "sentiment",
                    "kind": "sentiment",
                    "text": sentiment["description"],
                    "field": "tone",
                    "original_value": sentiment["label"],
                    "fallback": "Not enough evidence",
                    "reason": "Tone overview lacked verified support",
                    "verdict": "unsupported",
                    "confidence": 0,
                }
            )
            sentiment = {
                "label": "Not enough evidence",
                "description": "No supported tone overview is available.",
                "evidence": [],
            }
        else:
            sentiment["evidence"] = tone_evidence
    result["sentiment"] = sentiment
    counts = {
        verdict: sum(record["verdict"] == verdict for record in records)
        for verdict in ("supported", "unsupported", "uncertain")
    }
    report = {
        "checked_claims": len(records),
        "verified": counts["supported"],
        "flagged": counts["unsupported"],
        "review": counts["uncertain"],
        "metadata_corrections": len(corrections),
        "evidence_pass_rate": round(100 * counts["supported"] / len(records), 1) if records else 0,
        "verification_method": "Exact quote validation + independent OpenAI entailment check"
        if provider == "openai"
        else "Exact quote validation + conservative literal/pattern checks (local mode)",
        "confidence_method": "Heuristic support score based on quote validity, entailment and explicit metadata. Not a calibrated probability or a guarantee of truth.",
        "entries": entries,
        "corrections": corrections,
        "flagged_claims": [entry for entry in entries if entry["verdict"] == "unsupported"],
    }
    return result, report
