"""Persisted, single-worker processing queue with honest phase-boundary progress.

A failed/restarted job is retried from its durable transcript. Analysis results
and vectors are saved atomically; no half-written intelligence is exposed.
"""

import asyncio
from contextlib import suppress
import logging
from time import monotonic

from sqlalchemy import delete, select, update

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    ActionItem,
    Decision,
    DocumentChunk,
    EmbeddingMetadata,
    Meeting,
    MeetingSummary,
    Participant,
    Question,
    Risk,
    Topic,
    utcnow,
)
from app.services.ai_service import AIServiceError
from app.schemas.intelligence import FinalIntelligence
from app.services.embeddings import embed_texts
from app.services.grounding import canonical, explicit_calendar_date, verify_extraction
from app.services.notification_service import NotificationService
from app.services.preprocessing import chunk_transcript, preprocess, speaker_statistics
from app.services.summarizer import Summarizer
from app.utils.access import audit

logger = logging.getLogger(__name__)


def set_progress(meeting_id: str, stage: str, progress: int):
    with SessionLocal() as db:
        db.execute(
            update(Meeting)
            .where(Meeting.id == meeting_id)
            .values(processing_stage=stage, processing_progress=progress)
        )
        db.commit()
    logger.info("processing_stage", extra={"meeting_id": meeting_id, "stage": stage})


def process_meeting(meeting_id: str, provider_override: str | None = None):
    started = monotonic()
    logger.info("processing_start", extra={"meeting_id": meeting_id})
    try:
        with SessionLocal() as db:
            meeting = db.get(Meeting, meeting_id)
            if not meeting or not meeting.transcript:
                raise ValueError("No transcript is available")
            if not meeting.transcript.raw_text.strip():
                raise ValueError("A nonempty transcript is required")
            meeting.processing_status = "processing"
            meeting.processing_error = None
            db.commit()
            provider = provider_override or get_settings().active_provider

            def advance(stage, percent):
                set_progress(meeting_id, stage, percent)

            advance("Text preprocessing", 5)
            cleaned = preprocess(meeting.transcript.raw_text)
            if len(cleaned) < 10:
                raise ValueError("Transcript must contain at least 10 readable characters")
            advance("Chunking", 12)
            chunks = chunk_transcript(cleaned, meeting.documents)
            if not chunks:
                raise ValueError("Transcript produced no usable text chunks")
            advance("Embedding indexing", 20)
            vectors, embedding_provider, embedding_model = embed_texts(
                [c.content for c in chunks], provider
            )
            advance("AI analysis", 30)
            extracted = Summarizer(provider).extract(
                chunks,
                {
                    "title": meeting.title,
                    "date": meeting.date.isoformat(),
                    "project": meeting.project,
                    "participants": [p.name for p in meeting.participants],
                },
                advance,
            )
            advance("Structured extraction", 58)
            # Both providers have already passed the same strict Pydantic schema.
            advance("Grounding verification", 62)
            payload, report = verify_extraction(extracted, cleaned, provider, advance)
            payload = FinalIntelligence.model_validate(payload).model_dump(mode="json")
            advance("Saving results", 90)
            db.expire_all()
            meeting = db.get(Meeting, meeting_id)
            _save_analysis(
                db,
                meeting,
                cleaned,
                payload,
                report,
                chunks,
                vectors,
                embedding_provider,
                embedding_model,
            )
            meeting.processing_status = "completed"
            meeting.processing_stage = "Complete"
            meeting.processing_progress = 100
            meeting.analysis_provider = (
                f"OpenAI · {get_settings().openai_model}"
                if provider == "openai"
                else "Local extractive"
            )
            meeting.processed_at = utcnow()
            audit(
                db,
                meeting.user_id,
                "meeting.processed",
                "meeting",
                meeting.id,
                {
                    "provider": provider,
                    "claim_count": report["checked_claims"],
                    "flagged": report["flagged"],
                },
            )
            db.commit()
            NotificationService(db).meeting_complete(meeting)
        logger.info(
            "processing_complete",
            extra={"meeting_id": meeting_id, "duration_ms": round((monotonic() - started) * 1000)},
        )
    except Exception as error:
        logger.error(
            "processing_failed",
            extra={"meeting_id": meeting_id, "error_type": type(error).__name__},
        )
        message = (
            str(error)
            if isinstance(error, (ValueError, AIServiceError))
            else "Processing failed safely. Check the server logs and configuration, then retry"
        )
        with SessionLocal() as db:
            db.execute(
                update(Meeting)
                .where(Meeting.id == meeting_id)
                .values(
                    processing_status="failed",
                    processing_stage="Failed",
                    processing_error=message[:500],
                )
            )
            db.commit()


def _save_analysis(db, meeting, cleaned, payload, report, chunks, vectors, provider, model):
    risk_states = {canonical(r.text): r.status for r in meeting.risks}
    question_states = {canonical(q.text): (q.status, q.answer) for q in meeting.questions}
    retained_actions = db.scalars(
        select(ActionItem).where(
            ActionItem.meeting_id == meeting.id,
            (ActionItem.source_type == "manual") | ActionItem.manually_edited.is_(True),
        )
    ).all()
    retained_keys = {canonical(a.source_snapshot.get("text", a.task)) for a in retained_actions}
    for cls in (Decision, Risk, Question, Topic, DocumentChunk):
        db.execute(delete(cls).where(cls.meeting_id == meeting.id))
    db.execute(
        delete(ActionItem).where(
            ActionItem.meeting_id == meeting.id,
            ActionItem.source_type == "extracted",
            ActionItem.manually_edited.is_(False),
        )
    )
    meeting.transcript.cleaned_text = cleaned
    if meeting.summary:
        meeting.summary.payload = payload
        meeting.summary.grounding_report = report
    else:
        db.add(MeetingSummary(meeting_id=meeting.id, payload=payload, grounding_report=report))
    for kind, cls, text_field in (
        ("decisions", Decision, "text"),
        ("risks", Risk, "text"),
        ("questions", Question, "text"),
        ("topics", Topic, "name"),
    ):
        for claim in payload[kind]:
            values = {
                "meeting_id": meeting.id,
                text_field: claim["text"],
                "evidence": claim["evidence"],
                "confidence": claim["confidence"],
                "grounding_status": claim["grounding_status"],
            }
            if cls is Decision:
                values["decision_type"] = claim["decision_type"]
            elif cls is Risk:
                values.update(
                    category=claim["category"],
                    severity=claim["severity"],
                    status=risk_states.get(canonical(claim["text"]), "Open"),
                )
            elif cls is Question:
                status, answer = question_states.get(canonical(claim["text"]), ("Unanswered", ""))
                values.update(status=status, answer=answer)
            db.add(cls(**values))
    for claim in payload["action_items"]:
        if canonical(claim["text"]) in retained_keys:
            continue
        due = explicit_calendar_date(claim["due_date"])
        db.add(
            ActionItem(
                meeting_id=meeting.id,
                user_id=meeting.user_id,
                task=claim["text"],
                owner=claim["owner"],
                due_date=due,
                due_date_text=claim["due_date"],
                priority=claim["priority"],
                status=claim["status"],
                dependencies=claim["dependencies"],
                evidence=claim["evidence"],
                confidence=claim["confidence"],
                grounding_status=claim["grounding_status"],
                source_type="extracted",
                source_snapshot=claim,
            )
        )
    statistics = speaker_statistics(cleaned)
    people = {p.name.casefold(): p for p in meeting.participants}
    for name, stats in statistics.items():
        person = people.get(name.casefold())
        if not person:
            person = Participant(meeting_id=meeting.id, name=name, source="speaker_label")
            db.add(person)
        person.word_count = stats["word_count"]
        person.speaking_share = stats["speaking_share"]
        person.topics = [
            topic["text"]
            for topic in payload["topics"]
            if any(e["line_start"] in stats["lines"] for e in topic["evidence"])
        ]
    # Clear stale speaker metrics after a transcript edit; provided names remain metadata.
    for person in meeting.participants:
        if person.name.casefold() not in {name.casefold() for name in statistics}:
            person.word_count = None
            person.speaking_share = None
            person.topics = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        record = DocumentChunk(
            meeting_id=meeting.id,
            user_id=meeting.user_id,
            document_id=chunk.document_id,
            content=chunk.content,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            page_number=chunk.page_number,
            content_hash=chunk.content_hash,
            embedding=vector,
        )
        record.embedding_metadata = EmbeddingMetadata(
            provider=provider, model=model, dimensions=len(vector)
        )
        db.add(record)
    db.flush()


class ProcessingWorker:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.stopping = False

    async def start(self):
        with SessionLocal() as db:
            # This application runs one API/queue worker. Production replicas need
            # an external durable queue; see the explicit deployment constraints.
            db.execute(
                update(Meeting)
                .where(Meeting.processing_status == "processing")
                .values(
                    processing_status="queued",
                    processing_stage="Queued after server restart",
                    processing_progress=0,
                )
            )
            db.commit()
        self.task = asyncio.create_task(self.run(), name="meeting-processing-worker")

    async def run(self):
        last_reminders = monotonic()
        while not self.stopping:
            try:
                claimed = None
                with SessionLocal() as db:
                    candidate = db.scalar(
                        select(Meeting.id)
                        .where(Meeting.processing_status == "queued")
                        .order_by(Meeting.updated_at)
                        .limit(1)
                    )
                    if candidate:
                        result = db.execute(
                            update(Meeting)
                            .where(Meeting.id == candidate, Meeting.processing_status == "queued")
                            .values(processing_status="processing")
                        )
                        db.commit()
                        if result.rowcount:
                            claimed = candidate
                if claimed:
                    await asyncio.to_thread(process_meeting, claimed)
                elif monotonic() - last_reminders > 60:
                    await asyncio.to_thread(self.reminders)
                    last_reminders = monotonic()
                else:
                    await asyncio.sleep(0.75)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.error("queue_worker_error", extra={"error_type": type(error).__name__})
                await asyncio.sleep(2)

    @staticmethod
    def reminders():
        with SessionLocal() as db:
            NotificationService(db).deadline_reminders()

    async def stop(self):
        self.stopping = True
        if self.task:
            # Let in-flight to_thread work finish rather than freeing its DB engine.
            try:
                await asyncio.wait_for(
                    asyncio.shield(self.task), timeout=get_settings().openai_timeout_seconds + 30
                )
            except asyncio.TimeoutError:
                self.task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.task
