from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import ActionItem, Meeting, Question, Risk, User
from app.schemas.api import ActionCreate, ActionUpdate, QuestionUpdate, RiskUpdate
from app.services.presenter import action_dict
from app.utils.access import audit, ensure_mutable, own_meeting, user_today
from app.utils.security import get_current_user

router = APIRouter(prefix="/api", tags=["Action tracker"])


def own_action(db: Session, user: User, action_id: str) -> ActionItem:
    item = db.scalar(
        select(ActionItem).where(ActionItem.id == action_id, ActionItem.user_id == user.id)
    )
    if not item:
        raise HTTPException(404, "Action item not found")
    return item


@router.get("/action-items")
def list_actions(
    filter: str = "All",
    status: str | None = None,
    priority: str | None = None,
    owner: str | None = Query(default=None, max_length=120),
    meeting_id: str | None = None,
    q: str = Query(default="", max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    criteria = [ActionItem.user_id == user.id]
    valid_filters = {
        "All",
        "Pending",
        "Completed",
        "Overdue",
        "High Priority",
        "Unassigned",
        "My Tasks",
    }
    if filter not in valid_filters:
        raise HTTPException(422, "Unknown action filter")
    if filter in {"Pending", "Completed"}:
        criteria.append(ActionItem.status == filter)
    elif filter == "Overdue":
        criteria.extend(
            [
                ActionItem.due_date < user_today(user),
                ActionItem.status.not_in(["Completed", "Cancelled"]),
            ]
        )
    elif filter == "High Priority":
        criteria.append(ActionItem.priority.in_(["High", "Critical"]))
    elif filter == "Unassigned":
        criteria.append(ActionItem.owner == "Unassigned")
    elif filter == "My Tasks":
        criteria.append(func.lower(ActionItem.owner) == user.name.casefold())
    if status:
        if status not in {"Pending", "In Progress", "Completed", "Blocked", "Cancelled"}:
            raise HTTPException(422, "Unknown status")
        criteria.append(ActionItem.status == status)
    if priority:
        if priority not in {"Low", "Medium", "High", "Critical"}:
            raise HTTPException(422, "Unknown priority")
        criteria.append(ActionItem.priority == priority)
    if owner:
        criteria.append(func.lower(ActionItem.owner) == owner.casefold())
    if meeting_id:
        own_meeting(db, user, meeting_id)
        criteria.append(ActionItem.meeting_id == meeting_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        criteria.append(ActionItem.task.ilike(f"%{escaped}%", escape="\\"))
    total = db.scalar(select(func.count()).select_from(ActionItem).where(*criteria))
    items = db.scalars(
        select(ActionItem)
        .where(*criteria)
        .options(joinedload(ActionItem.meeting))
        .order_by(ActionItem.due_date.asc().nullslast(), ActionItem.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [action_dict(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/action-items", status_code=201)
def create_action(
    data: ActionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    meeting = own_meeting(db, user, data.meeting_id)
    ensure_mutable(meeting)
    values = data.model_dump()
    item = ActionItem(
        **values,
        user_id=user.id,
        due_date_text=data.due_date.isoformat() if data.due_date else "Not specified",
        source_type="manual",
        grounding_status="user_provided",
        confidence=0.0,
    )
    db.add(item)
    db.flush()
    audit(db, user.id, "action.created", "action_item", item.id, {"source": "manual"})
    db.commit()
    return action_dict(item)


@router.put("/action-items/{action_id}")
def update_action(
    action_id: str,
    data: ActionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = own_action(db, user, action_id)
    ensure_mutable(item.meeting)
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    if "due_date" in values:
        item.due_date_text = item.due_date.isoformat() if item.due_date else "Not specified"
    if values:
        item.manually_edited = True
        # Evidence and the original support score remain in source_snapshot.
        # The mutable record is now a human state, never a newly grounded claim.
        item.grounding_status = "user_provided"
        item.confidence = 0.0
        audit(
            db,
            user.id,
            "action.updated",
            "action_item",
            item.id,
            {"fields": list(values), "source": "human"},
        )
    db.commit()
    return action_dict(item)


@router.delete("/action-items/{action_id}", status_code=204)
def delete_action(
    action_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    item = own_action(db, user, action_id)
    ensure_mutable(item.meeting)
    audit(db, user.id, "action.deleted", "action_item", item.id)
    db.delete(item)
    db.commit()


@router.put("/risks/{risk_id}")
def update_risk(
    risk_id: str,
    data: RiskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    risk = db.scalar(
        select(Risk).join(Meeting).where(Risk.id == risk_id, Meeting.user_id == user.id)
    )
    if not risk:
        raise HTTPException(404, "Risk not found")
    ensure_mutable(risk.meeting)
    risk.status = data.status
    audit(db, user.id, "risk.updated", "risk", risk.id, {"status": data.status})
    db.commit()
    return {"id": risk.id, "status": risk.status}


@router.put("/questions/{question_id}")
def update_question(
    question_id: str,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    question = db.scalar(
        select(Question).join(Meeting).where(Question.id == question_id, Meeting.user_id == user.id)
    )
    if not question:
        raise HTTPException(404, "Question not found")
    ensure_mutable(question.meeting)
    question.status = data.status
    question.answer = data.answer
    audit(
        db,
        user.id,
        "question.updated",
        "question",
        question.id,
        {"status": data.status, "answer_source": "human"},
    )
    db.commit()
    return {"id": question.id, "status": question.status, "answer": question.answer}
