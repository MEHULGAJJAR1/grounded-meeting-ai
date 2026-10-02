from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.exports import MIME_TYPES, export_meeting
from app.services.presenter import meeting_detail
from app.utils.access import audit, own_meeting
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/meetings", tags=["Exports"])


@router.get("/{meeting_id}/export/{format}")
def export(
    meeting_id: str,
    format: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if format not in MIME_TYPES:
        raise HTTPException(422, "Export format must be pdf, docx, json, markdown or csv")
    meeting = own_meeting(db, user, meeting_id)
    content, media_type, filename = export_meeting(meeting_detail(meeting), format)
    audit(db, user.id, "meeting.exported", "meeting", meeting_id, {"format": format})
    db.commit()
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
