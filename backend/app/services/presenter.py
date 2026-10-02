"""One serializer shared by APIs and exports to avoid diverging representations."""

from app.models import ActionItem, Document, Meeting
from app.utils.time import iso_utc


def action_dict(item: ActionItem) -> dict:
    return {
        "id": item.id,
        "meeting_id": item.meeting_id,
        "meeting_title": item.meeting.title,
        "task": item.task,
        "owner": item.owner,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "due_date_text": item.due_date_text,
        "priority": item.priority,
        "status": item.status,
        "dependencies": item.dependencies,
        "notes": item.notes,
        "evidence": item.evidence,
        "confidence": item.confidence,
        "grounding_status": item.grounding_status,
        "source_type": item.source_type,
        "manually_edited": item.manually_edited,
        "source_snapshot": item.source_snapshot,
        "created_at": iso_utc(item.created_at),
        "updated_at": iso_utc(item.updated_at),
    }


def document_dict(item: Document, include_text: bool = False) -> dict:
    data = {
        "id": item.id,
        "meeting_id": item.meeting_id,
        "filename": item.filename,
        "file_type": item.file_type,
        "size_bytes": item.size_bytes,
        "processing_status": item.processing_status,
        "processing_error": item.processing_error,
        "attached_to_transcript": item.attached_to_transcript,
        "page_count": len(item.pages),
        "created_at": iso_utc(item.created_at),
    }
    if include_text:
        data.update(extracted_text=item.extracted_text, pages=item.pages)
    return data


def meeting_card(item: Meeting) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "date": item.date.isoformat(),
        "meeting_type": item.meeting_type,
        "project": item.project,
        "participants": [p.name for p in item.participants],
        "processing_status": item.processing_status,
        "processing_stage": item.processing_stage,
        "processing_progress": item.processing_progress,
        "analysis_provider": item.analysis_provider,
        "preview_grounding_status": item.summary.payload["executive_summary"][0].get(
            "grounding_status"
        )
        if item.summary and item.summary.payload.get("executive_summary")
        else None,
        "is_demo": item.is_demo,
        "action_count": len(item.action_items),
        "decision_count": len(item.decisions),
        "risk_count": len([r for r in item.risks if r.status == "Open"]),
        "created_at": iso_utc(item.created_at),
        "preview": item.summary.payload.get("executive_summary", [{}])[0].get("text", "")
        if item.summary and item.summary.payload.get("executive_summary")
        else "",
    }


def meeting_detail(item: Meeting) -> dict:
    data = meeting_card(item)
    data.update(
        transcript=item.transcript.raw_text if item.transcript else "",
        cleaned_transcript=item.transcript.cleaned_text if item.transcript else "",
        processing_error=item.processing_error,
        processed_at=iso_utc(item.processed_at) if item.processed_at else None,
        summary=item.summary.payload if item.summary else None,
        grounding_report=item.summary.grounding_report if item.summary else None,
        participant_analysis=[
            {
                "id": p.id,
                "name": p.name,
                "source": p.source,
                "word_count": p.word_count,
                "speaking_share": p.speaking_share,
                "topics": p.topics,
                "assigned_tasks": sum(
                    a.owner.casefold() == p.name.casefold() for a in item.action_items
                ),
            }
            for p in item.participants
        ],
        action_items=[action_dict(a) for a in item.action_items],
        decisions=[
            {
                "id": d.id,
                "text": d.text,
                "decision_type": d.decision_type,
                "evidence": d.evidence,
                "confidence": d.confidence,
                "grounding_status": d.grounding_status,
            }
            for d in item.decisions
        ],
        risks=[
            {
                "id": r.id,
                "text": r.text,
                "category": r.category,
                "severity": r.severity,
                "status": r.status,
                "evidence": r.evidence,
                "confidence": r.confidence,
                "grounding_status": r.grounding_status,
            }
            for r in item.risks
        ],
        questions=[
            {
                "id": q.id,
                "text": q.text,
                "status": q.status,
                "answer": q.answer,
                "evidence": q.evidence,
                "confidence": q.confidence,
                "grounding_status": q.grounding_status,
            }
            for q in item.questions
        ],
        topics=[
            {
                "id": t.id,
                "name": t.name,
                "evidence": t.evidence,
                "confidence": t.confidence,
                "grounding_status": t.grounding_status,
            }
            for t in item.topics
        ],
        documents=[document_dict(d) for d in item.documents],
        health={
            "decisions": len(item.decisions),
            "action_items": len(item.action_items),
            "unresolved_questions": sum(q.status == "Unanswered" for q in item.questions),
            "risks": sum(r.status == "Open" for r in item.risks),
            "unassigned_tasks": sum(a.owner == "Unassigned" for a in item.action_items),
            "tasks_with_deadlines": sum(
                a.due_date_text != "Not specified" for a in item.action_items
            ),
            "tasks_with_calendar_dates": sum(a.due_date is not None for a in item.action_items),
        },
    )
    return data
