"""Ensure transcript edits cannot silently leave stale AI facts or vectors active."""

from sqlalchemy import delete
from app.models import ActionItem, Decision, DocumentChunk, MeetingSummary, Question, Risk, Topic


def invalidate_analysis(db, meeting):
    for item in meeting.action_items:
        if item.source_type == "extracted" and item.manually_edited:
            # Human edits are retained as human records; the original proposal is
            # still available in source_snapshot, but not attributed to new text.
            item.source_type = "manual"
            item.evidence = []
            item.grounding_status = "user_provided"
            item.confidence = 0.0
    db.flush()
    db.execute(
        delete(ActionItem).where(
            ActionItem.meeting_id == meeting.id,
            ActionItem.source_type == "extracted",
            ActionItem.manually_edited.is_(False),
        )
    )
    for cls in (MeetingSummary, Decision, Risk, Question, Topic, DocumentChunk):
        db.execute(delete(cls).where(cls.meeting_id == meeting.id))
    meeting.processing_status = "draft"
    meeting.processing_stage = "Transcript updated · ready to process"
    meeting.processing_progress = 0
    meeting.analysis_provider = None
    meeting.processing_error = None
    meeting.processed_at = None
    if meeting.transcript:
        meeting.transcript.cleaned_text = ""
