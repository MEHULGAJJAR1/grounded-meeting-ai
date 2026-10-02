from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Meeting, Participant, Transcript, User
from app.schemas.api import MeetingCreate, MeetingUpdate
from app.services.invalidation import invalidate_analysis
from app.services.presenter import meeting_card, meeting_detail
from app.utils.access import audit, ensure_mutable, own_meeting
from app.utils.rate_limit import rate_limit
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/meetings", tags=["Meetings"])


@router.post("", status_code=201)
def create_meeting(
    data: MeetingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    meeting = Meeting(
        user_id=user.id,
        title=data.title,
        date=data.date,
        meeting_type=data.meeting_type,
        project=data.project,
    )
    meeting.participants = [Participant(name=name) for name in data.participants]
    meeting.transcript = Transcript(raw_text=data.transcript)
    db.add(meeting)
    db.flush()
    audit(db, user.id, "meeting.created", "meeting", meeting.id)
    db.commit()
    return meeting_detail(meeting)


@router.get("")
def list_meetings(
    q: str = Query(default="", max_length=200),
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    criteria = [Meeting.user_id == user.id]
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        criteria.append(
            (Meeting.title.ilike(f"%{escaped}%", escape="\\"))
            | Meeting.project.ilike(f"%{escaped}%", escape="\\")
        )
    if status:
        if status not in {"draft", "queued", "processing", "completed", "failed"}:
            raise HTTPException(422, "Invalid meeting status")
        criteria.append(Meeting.processing_status == status)
    count = db.scalar(select(func.count()).select_from(Meeting).where(*criteria))
    items = db.scalars(
        select(Meeting)
        .where(*criteria)
        .options(
            selectinload(Meeting.participants),
            selectinload(Meeting.action_items),
            selectinload(Meeting.decisions),
            selectinload(Meeting.risks),
            selectinload(Meeting.summary),
        )
        .order_by(Meeting.date.desc(), Meeting.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [meeting_card(item) for item in items],
        "total": count,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{meeting_id}")
def detail(meeting_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return meeting_detail(own_meeting(db, user, meeting_id))


@router.put("/{meeting_id}")
def update_meeting(
    meeting_id: str,
    data: MeetingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    meeting = own_meeting(db, user, meeting_id)
    ensure_mutable(meeting)
    values = data.model_dump(exclude_unset=True)
    if (
        "transcript" in values
        and meeting.transcript
        and meeting.transcript.raw_text != values["transcript"]
    ):
        invalidate_analysis(db, meeting)
        meeting.transcript.raw_text = values.pop("transcript")
    elif "transcript" in values:
        text = values.pop("transcript")
        if not meeting.transcript:
            meeting.transcript = Transcript(raw_text=text)
    if "participants" in values:
        # Delete + flush first to respect the per-meeting unique constraint.
        meeting.participants.clear()
        db.flush()
        meeting.participants = [Participant(name=name) for name in values.pop("participants")]
    for key, value in values.items():
        setattr(meeting, key, value)
    audit(
        db,
        user.id,
        "meeting.updated",
        "meeting",
        meeting.id,
        {"fields": list(data.model_fields_set)},
    )
    db.commit()
    db.expire_all()
    return meeting_detail(own_meeting(db, user, meeting_id))


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    meeting = own_meeting(db, user, meeting_id)
    ensure_mutable(meeting)
    files = [Path(doc.storage_path) for doc in meeting.documents]
    audit(db, user.id, "meeting.deleted", "meeting", meeting.id)
    db.delete(meeting)
    db.commit()
    for path in files:
        path.unlink(missing_ok=True)


@router.post("/{meeting_id}/process", status_code=202)
def queue_processing(
    meeting_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_limit(request, "processing", 12)
    meeting = own_meeting(db, user, meeting_id)
    ensure_mutable(meeting)
    if not meeting.transcript or len(meeting.transcript.raw_text.strip()) < 10:
        raise HTTPException(
            422, "Paste or upload at least 10 characters of transcript before processing"
        )
    # Conditional update prevents two simultaneous requests from enqueuing twice.
    result = db.execute(
        update(Meeting)
        .where(
            Meeting.id == meeting.id,
            Meeting.user_id == user.id,
            Meeting.processing_status.not_in(["queued", "processing"]),
        )
        .values(
            processing_status="queued",
            processing_stage="Queued",
            processing_progress=0,
            processing_error=None,
        )
    )
    if not result.rowcount:
        raise HTTPException(409, "Meeting is already queued or processing")
    audit(db, user.id, "meeting.queued", "meeting", meeting.id)
    db.commit()
    return {"meeting_id": meeting.id, "status": "queued", "stage": "Queued", "progress": 0}


@router.get("/{meeting_id}/processing-status")
def processing_status(
    meeting_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    meeting = own_meeting(db, user, meeting_id)
    return {
        "meeting_id": meeting.id,
        "status": meeting.processing_status,
        "stage": meeting.processing_stage,
        "progress": meeting.processing_progress,
        "error": meeting.processing_error,
    }
