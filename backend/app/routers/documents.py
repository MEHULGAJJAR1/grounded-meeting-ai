import logging
from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Document, Transcript, User, new_id
from app.schemas.api import DocumentAttach
from app.services.document_parser import DocumentParseError, attachment_text, extract_document
from app.services.invalidation import invalidate_analysis
from app.services.presenter import document_dict
from app.utils.access import audit, ensure_mutable, own_meeting
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


def own_document(db: Session, user: User, document_id: str) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    if not document:
        raise HTTPException(404, "Document not found")
    return document


def _attach(db: Session, user: User, document: Document, meeting_id: str):
    meeting = own_meeting(db, user, meeting_id)
    ensure_mutable(meeting)
    if document.processing_status != "completed":
        raise HTTPException(409, "This document has not been successfully extracted")
    if document.attached_to_transcript:
        if document.meeting_id == meeting_id:
            return
        raise HTTPException(409, "This document is already attached to another meeting")
    incoming = attachment_text(document)
    prior = meeting.transcript.raw_text if meeting.transcript else ""
    combined = (prior.rstrip() + "\n\n" + incoming).strip()
    if len(combined) > get_settings().max_transcript_chars:
        raise HTTPException(422, "Combined transcript exceeds MAX_TRANSCRIPT_CHARS")
    invalidate_analysis(db, meeting)
    if meeting.transcript:
        meeting.transcript.raw_text = combined
    else:
        meeting.transcript = Transcript(raw_text=combined)
    document.meeting_id = meeting_id
    document.attached_to_transcript = True


@router.post("/upload", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    meeting_id: str | None = Form(default=None),
    append_to_transcript: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = get_settings()
    if meeting_id:
        ensure_mutable(own_meeting(db, user, meeting_id))
    filename = re.sub(
        r"[\x00-\x1f\[\]\|]", "_", Path((file.filename or "transcript.txt").replace("\\", "/")).name
    )[:255]
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in {"txt", "pdf", "docx", "csv"}:
        raise HTTPException(415, "Supported files are TXT, PDF, DOCX and CSV")
    data = file.file.read(settings.max_upload_size + 1)
    file.file.close()
    if len(data) > settings.max_upload_size:
        raise HTTPException(
            413, f"File exceeds the {settings.max_upload_size // (1024 * 1024)} MB upload limit"
        )
    identity = new_id()
    storage = settings.upload_path / user.id / f"{identity}.{extension}"
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_bytes(data)
    document = Document(
        id=identity,
        user_id=user.id,
        meeting_id=meeting_id,
        filename=filename,
        file_type=extension,
        storage_path=str(storage),
        size_bytes=len(data),
        processing_status="extracting",
    )
    db.add(document)
    db.commit()
    try:
        text, pages = extract_document(filename, data)
        document.extracted_text = text
        document.pages = pages
        document.processing_status = "completed"
        db.commit()
        if meeting_id and append_to_transcript:
            _attach(db, user, document, meeting_id)
        audit(
            db,
            user.id,
            "document.uploaded",
            "document",
            identity,
            {"file_type": extension, "size_bytes": len(data)},
        )
        db.commit()
        return document_dict(document, True)
    except DocumentParseError as error:
        document.processing_status = "failed"
        document.processing_error = str(error)
        db.commit()
        logger.warning(
            "document_extraction_failed",
            extra={"user_id": user.id, "error_type": type(error).__name__},
        )
        raise HTTPException(422, {"message": str(error), "document_id": identity}) from None


@router.get("")
def list_documents(
    meeting_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    criteria = [Document.user_id == user.id]
    if meeting_id:
        own_meeting(db, user, meeting_id)
        criteria.append(Document.meeting_id == meeting_id)
    total = db.scalar(select(func.count()).select_from(Document).where(*criteria))
    items = db.scalars(
        select(Document)
        .where(*criteria)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [document_dict(item) for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{document_id}")
def document_detail(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return document_dict(own_document(db, user, document_id), True)


@router.post("/{document_id}/attach")
def attach_document(
    document_id: str,
    data: DocumentAttach,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = own_document(db, user, document_id)
    _attach(db, user, document, data.meeting_id)
    audit(db, user.id, "document.attached", "document", document.id)
    db.commit()
    return document_dict(document, True)


@router.get("/{document_id}/download")
def download_document(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    document = own_document(db, user, document_id)
    if not Path(document.storage_path).is_file():
        raise HTTPException(404, "Stored file is unavailable")
    return FileResponse(
        document.storage_path, filename=document.filename, media_type="application/octet-stream"
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    document = own_document(db, user, document_id)
    if document.meeting_id:
        ensure_mutable(own_meeting(db, user, document.meeting_id))
    path = Path(document.storage_path)
    audit(
        db,
        user.id,
        "document.deleted",
        "document",
        document.id,
        {"imported_text_retained": document.attached_to_transcript},
    )
    # Imported text is a copy in the transcript; deleting the original upload does
    # not rewrite the meeting. This is explicit in the UI and documentation.
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
