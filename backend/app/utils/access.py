from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Meeting, User


def own_meeting(db: Session, user: User, meeting_id: str) -> Meeting:
    meeting = db.scalar(select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == user.id))
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    return meeting


def ensure_mutable(meeting: Meeting):
    if meeting.processing_status in {"queued", "processing"}:
        raise HTTPException(409, "Meeting is processing; try again when analysis is finished")


def audit(
    db: Session,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
):
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )


def user_today(user: User):
    return datetime.now(ZoneInfo(user.timezone)).date()
