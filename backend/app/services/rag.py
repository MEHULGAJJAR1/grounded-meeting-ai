"""Tenant-scoped hybrid retrieval and source-verified RAG over real meeting data."""

from datetime import timedelta
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    ActionItem,
    Decision,
    Document,
    DocumentChunk,
    Meeting,
    Question,
    Risk,
    User,
)
from app.services.ai_service import AIServiceError, OpenAIService
from app.services.embeddings import cosine, embed_texts, tokens
from app.services.grounding import canonical, locate_evidence
from app.utils.access import own_meeting, user_today


def _source(
    identity: str,
    meeting: Meeting,
    text: str,
    kind: str,
    evidence: list | None = None,
    score: float = 1.0,
) -> dict:
    return {
        "id": identity,
        "meeting_id": meeting.id,
        "meeting_title": meeting.title,
        "meeting_date": meeting.date.isoformat(),
        "text": text,
        "source_kind": kind,
        "evidence": evidence or [],
        "score": round(score, 4),
    }


def _record_sources(
    db: Session, user: User, query: str, limit: int, meeting_id: str | None
) -> tuple[list[dict], bool]:
    lower = query.casefold()
    today = user_today(user)
    action_intent = bool(
        re.search(r"\b(?:task|tasks|action|actions|assigned|deadline|deadlines|overdue)\b", lower)
    )
    risk_intent = bool(re.search(r"\b(?:risk|risks|blocker|blockers)\b", lower))
    decision_intent = bool(re.search(r"\b(?:decision|decisions|decided)\b", lower))
    question_intent = bool(re.search(r"\b(?:unanswered|unresolved question|questions)\b", lower))
    sources = []
    restrictive = action_intent and bool(
        re.search(
            r"\b(?:assigned|overdue|upcoming|coming next|completed|pending|unassigned)\b", lower
        )
    )
    scope = [Meeting.user_id == user.id]
    if meeting_id:
        scope.append(Meeting.id == meeting_id)
    if decision_intent and "last month" in lower:
        first = today.replace(day=1)
        previous_last = first - timedelta(days=1)
        scope += [Meeting.date >= previous_last.replace(day=1), Meeting.date < first]
        restrictive = True
    if action_intent:
        query_db = (
            select(ActionItem)
            .join(Meeting)
            .where(*scope, ActionItem.user_id == user.id)
            .options(joinedload(ActionItem.meeting))
        )
        if "overdue" in lower:
            query_db = query_db.where(
                ActionItem.due_date < today, ActionItem.status.not_in(["Completed", "Cancelled"])
            )
        elif re.search(r"\bnext week\b", lower):
            next_monday = today + timedelta(days=7 - today.weekday())
            query_db = query_db.where(
                ActionItem.due_date >= next_monday,
                ActionItem.due_date <= next_monday + timedelta(days=6),
                ActionItem.status.not_in(["Completed", "Cancelled"]),
            )
            restrictive = True
        elif any(word in lower for word in ("upcoming", "coming next", "due next", "next 7 days")):
            query_db = query_db.where(
                ActionItem.due_date >= today,
                ActionItem.due_date <= today + timedelta(days=7),
                ActionItem.status.not_in(["Completed", "Cancelled"]),
            )
        if "unassigned" in lower:
            query_db = query_db.where(ActionItem.owner == "Unassigned")
        if "completed" in lower:
            query_db = query_db.where(ActionItem.status == "Completed")
        elif "pending" in lower:
            query_db = query_db.where(ActionItem.status == "Pending")
        items = db.scalars(
            query_db.order_by(
                ActionItem.due_date.asc().nullslast(), ActionItem.created_at.desc()
            ).limit(1000)
        ).all()
        owner_match = re.search(r"assigned to\s+([\w .'-]+?)(?:[?!.]|$)", query, re.I)
        owner = (
            owner_match.group(1).strip()
            if owner_match
            else (user.name if re.search(r"\bmy tasks\b", lower) else None)
        )
        if owner and owner.casefold() in {"me", "myself"}:
            owner = user.name
        if owner:
            items = [
                item
                for item in items
                if item.owner.casefold() == owner.casefold()
                or item.owner.casefold().startswith(owner.casefold() + " ")
            ]
            restrictive = True
        for item in items[:limit]:
            source = _source(
                f"action:{item.id}",
                item.meeting,
                f"Task: {item.task}\nOwner: {item.owner}\nDue date: {item.due_date_text}\nPriority: {item.priority}\nStatus: {item.status}"
                + (f"\nNotes: {item.notes}" if item.notes else "")
                + f"\nGrounding state: {item.grounding_status}",
                "action record",
                item.evidence,
            )
            source["record_provenance"] = (
                "user-entered/edited current record"
                if item.source_type == "manual" or item.manually_edited
                else "grounded extraction; current editable state"
            )
            source["action_id"] = item.id
            source["grounding_status"] = item.grounding_status
            sources.append(source)
    for enabled, cls, kind in (
        (risk_intent, Risk, "risk record"),
        (decision_intent, Decision, "decision record"),
        (question_intent, Question, "question record"),
    ):
        if not enabled:
            continue
        statement = select(cls).join(Meeting).where(*scope).options(joinedload(cls.meeting))
        if cls is Risk and re.search(r"\b(?:unresolved|open|still)\b", lower):
            statement = statement.where(Risk.status == "Open")
            restrictive = True
        if cls is Question:
            statement = statement.where(Question.status == "Unanswered")
            restrictive = True
        items = db.scalars(statement.order_by(cls.created_at.desc()).limit(300)).all()
        terms = set(tokens(query)) - {
            "risk",
            "unresolved",
            "open",
            "still",
            "decision",
            "made",
            "last",
            "month",
            "question",
            "unanswered",
        }
        ranked = []
        for item in items:
            overlap = len(terms & set(tokens(item.text)))
            score = 1.0 if not terms else 0.5 + min(0.5, overlap / len(terms))
            if terms and not overlap:
                continue
            text = item.text
            text += (
                f"\nDecision type: {item.decision_type}"
                if cls is Decision
                else f"\nStatus: {item.status}"
            )
            text += f"\nGrounding state: {item.grounding_status}"
            source = _source(
                f"{kind.split()[0]}:{item.id}", item.meeting, text, kind, item.evidence, score
            )
            source["grounding_status"] = item.grounding_status
            source["record_provenance"] = (
                "Source-backed record with current editable workflow state"
            )
            ranked.append(source)
        sources.extend(sorted(ranked, key=lambda source: source["score"], reverse=True)[:limit])
    return sources, restrictive


def retrieve(
    db: Session, user: User, query: str, limit: int = 8, meeting_id: str | None = None
) -> dict:
    if meeting_id:
        own_meeting(db, user, meeting_id)
    # Explicit latest-meeting queries choose a real latest record, not arbitrary top-k.
    if (
        not meeting_id
        and re.search(r"\b(?:last|latest|most recent)\b", query, re.I)
        and "last month" not in query.casefold()
    ):
        candidates = db.scalars(
            select(Meeting)
            .where(Meeting.user_id == user.id, Meeting.processing_status == "completed")
            .order_by(Meeting.date.desc(), Meeting.created_at.desc())
            .limit(100)
        ).all()
        keywords = set(tokens(query)) - {
            "last",
            "latest",
            "most",
            "recent",
            "summarise",
            "summarize",
            "summary",
            "decided",
            "decision",
            "overview",
            "takeaways",
            "notes",
            "happened",
            "tell",
            "give",
            "can",
            "could",
            "key",
            "points",
            "important",
            "action",
            "question",
            "risk",
        }
        chosen = next(
            (
                m
                for m in candidates
                if not keywords
                or keywords & set(tokens(m.title + " " + m.meeting_type + " " + m.project))
            ),
            None,
        )
        if chosen:
            meeting_id = chosen.id
        else:
            return {
                "sources": [],
                "retrieval_mode": "current database selection",
                "indexed_chunks": 0,
                "note": "No matching processed meeting exists in your workspace for this latest-meeting request.",
            }
    records, restrictive = _record_sources(db, user, query, min(20, limit + 4), meeting_id)
    if restrictive:
        return {
            "sources": records[:20],
            "retrieval_mode": "current database records",
            "indexed_chunks": 0,
            "note": "Current editable records are used for assignments, deadlines and statuses. Results are limited to 20 sources.",
        }
    statement = (
        select(DocumentChunk)
        .join(Meeting)
        .where(
            DocumentChunk.user_id == user.id,
            Meeting.user_id == user.id,
            Meeting.processing_status == "completed",
        )
        .options(joinedload(DocumentChunk.meeting), joinedload(DocumentChunk.embedding_metadata))
    )
    if meeting_id:
        statement = statement.where(DocumentChunk.meeting_id == meeting_id)
    chunks = db.scalars(statement.limit(10000)).all()
    document_ids = {chunk.document_id for chunk in chunks if chunk.document_id}
    filenames = (
        dict(
            db.execute(
                select(Document.id, Document.filename).where(
                    Document.user_id == user.id, Document.id.in_(document_ids)
                )
            ).all()
        )
        if document_ids
        else {}
    )
    query_vectors = {}
    modes = set()
    query_terms = set(tokens(query))
    ranked = []
    for chunk in chunks:
        meta = chunk.embedding_metadata
        identity = (meta.provider, meta.model)
        if identity not in query_vectors:
            try:
                vectors, _, _ = embed_texts([query], meta.provider, meta.model)
                query_vectors[identity] = vectors[0]
            except Exception:
                raise HTTPException(
                    503,
                    "The embedding provider is unavailable; check your OpenAI key, model and connection",
                ) from None
        score = max(0.0, cosine(query_vectors[identity], chunk.embedding))
        overlap = len(query_terms & set(tokens(chunk.content))) / max(1, len(query_terms))
        combined = 0.7 * score + 0.3 * overlap
        modes.add(
            "OpenAI semantic embeddings"
            if meta.provider == "openai"
            else "local lexical feature embeddings"
        )
        if combined < 0.045 and not meeting_id:
            continue
        evidence = [
            {
                "quote": chunk.content,
                "line_start": chunk.start_line,
                "line_end": chunk.end_line,
                "page": chunk.page_number,
                "filename": filenames.get(chunk.document_id),
            }
        ]
        source = _source(
            f"chunk:{chunk.id}", chunk.meeting, chunk.content, "transcript", evidence, combined
        )
        ranked.append(source)
    ranked.sort(key=lambda source: source["score"], reverse=True)
    # Preserve multiple relevant passages while deduplicating overlapping chunks.
    selected = []
    for source in ranked:
        if any(
            source["meeting_id"] == s["meeting_id"]
            and canonical(source["text"]) in canonical(s["text"])
            for s in selected
        ):
            continue
        selected.append(source)
        if len(selected) >= limit:
            break
    return {
        "sources": (records + selected)[:20],
        "retrieval_mode": " + ".join(sorted(modes)) or "current database records",
        "indexed_chunks": len(chunks),
        "note": "Retrieval is restricted to your own meeting history. Similarity is not a confidence probability.",
    }


def answer_question(
    db: Session, user: User, query: str, limit: int, meeting_id: str | None, history: list[dict]
) -> dict:
    retrieval = retrieve(db, user, query, limit, meeting_id)
    review_excluded = sum(
        source.get("grounding_status") == "review" for source in retrieval["sources"]
    )
    sources = [
        source for source in retrieval["sources"] if source.get("grounding_status") != "review"
    ]
    if review_excluded:
        retrieval["note"] += (
            f" {review_excluded} unverified current-record candidate(s) excluded from answers."
        )
    provider = get_settings().active_provider
    if not sources:
        return {
            "answer": "I couldn't find supporting evidence in your meeting history. Try a more specific question or process a relevant meeting first.",
            "claims": [],
            "sources": [],
            "insufficient_evidence": True,
            "provider": provider,
            "retrieval_mode": retrieval["retrieval_mode"],
            "grounding": {"verified": 0, "withheld": 0, "review_sources_excluded": review_excluded},
            "note": retrieval["note"],
        }
    if provider == "local":
        claims = []
        # Real extractive answers: copy the most query-relevant source sentences.
        terms = set(tokens(query))
        for source in sources[:10]:
            if source["source_kind"] != "transcript":
                quote = source["text"]
            else:
                lines = [
                    line.strip()
                    for line in source["text"].splitlines()
                    if line.strip() and not line.startswith("[Document:")
                ]
                lines.sort(key=lambda line: len(terms & set(tokens(line))), reverse=True)
                quote = lines[0] if lines else source["text"]
            claims.append(
                {
                    "text": quote,
                    "source_ids": [source["id"]],
                    "evidence_quotes": [quote],
                    "grounding_status": source.get("grounding_status", "verified"),
                }
            )
        note = (
            "Local extractive mode: these are source excerpts, not an LLM-generated synthesis. "
            + retrieval["note"]
        )
        return {
            "answer": "Here is the supporting information from your meeting history:",
            "claims": claims,
            "sources": sources,
            "insufficient_evidence": False,
            "provider": "local",
            "retrieval_mode": retrieval["retrieval_mode"],
            "grounding": {
                "verified": sum(c["grounding_status"] == "verified" for c in claims),
                "withheld": 0,
                "review_sources_excluded": review_excluded,
            },
            "note": note,
        }
    service = OpenAIService()
    try:
        proposed = service.answer(query, sources, history)
        if proposed.insufficient_evidence:
            return {
                "answer": "I couldn't verify a sufficient answer from the retrieved evidence.",
                "claims": [],
                "sources": sources,
                "insufficient_evidence": True,
                "provider": f"OpenAI · {get_settings().openai_model}",
                "retrieval_mode": retrieval["retrieval_mode"],
                "grounding": {
                    "verified": 0,
                    "withheld": len(proposed.claims),
                    "review_sources_excluded": review_excluded,
                },
                "note": "The provider reported insufficient support; no proposed claim was presented. "
                + retrieval["note"],
            }
        mapping = {source["id"]: source for source in sources}
        valid = []
        withheld = 0
        for index, claim in enumerate(proposed.claims):
            referenced = [mapping.get(identity) for identity in claim.source_ids]
            if (
                not referenced
                or not all(referenced)
                or not all(
                    any(locate_evidence(quote, source["text"]) for source in referenced)
                    for quote in claim.evidence_quotes
                )
            ):
                withheld += 1
                continue
            checks = service.verify(
                [{"claim_id": str(index), "kind": "RAG answer", "claim": claim.model_dump()}],
                "\n\n".join(source["text"] for source in referenced),
            ).checks
            if len(checks) != 1 or checks[0].verdict != "supported":
                withheld += 1
                continue
            valid.append(
                {
                    **claim.model_dump(),
                    "grounding_status": "user_provided"
                    if any(
                        source.get("grounding_status") == "user_provided" for source in referenced
                    )
                    else "verified",
                }
            )
        return {
            "answer": "Based on your meeting history:"
            if valid
            else "I couldn't verify an answer from the retrieved evidence.",
            "claims": valid,
            "sources": sources,
            "insufficient_evidence": not valid,
            "provider": f"OpenAI · {get_settings().openai_model}",
            "retrieval_mode": retrieval["retrieval_mode"],
            "grounding": {
                "verified": sum(c["grounding_status"] == "verified" for c in valid),
                "withheld": withheld,
                "review_sources_excluded": review_excluded,
            },
            "note": ("Unsupported answer claims were withheld. " if withheld else "")
            + retrieval["note"],
        }
    except AIServiceError as error:
        raise HTTPException(503, str(error)) from None
