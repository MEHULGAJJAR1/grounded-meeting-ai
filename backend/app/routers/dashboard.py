from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionItem, AuditLog, Decision, Meeting, Notification, Question, Risk, User
from app.services.presenter import action_dict, meeting_card
from app.utils.access import user_today
from app.utils.security import get_current_user
from app.utils.time import iso_utc

router = APIRouter(prefix="/api", tags=["Dashboard & notifications"])


def count(db, cls, *criteria):
    return db.scalar(select(func.count()).select_from(cls).where(*criteria)) or 0


@router.get("/dashboard/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scope = ActionItem.user_id == user.id
    today = user_today(user)
    active = ActionItem.status.not_in(["Completed", "Cancelled"])
    risk_count = (
        db.scalar(
            select(func.count())
            .select_from(Risk)
            .join(Meeting)
            .where(Meeting.user_id == user.id, Risk.status == "Open")
        )
        or 0
    )
    question_count = (
        db.scalar(
            select(func.count())
            .select_from(Question)
            .join(Meeting)
            .where(Meeting.user_id == user.id, Question.status == "Unanswered")
        )
        or 0
    )
    upcoming = db.scalars(
        select(ActionItem)
        .where(scope, active, ActionItem.due_date.is_not(None))
        .order_by(ActionItem.due_date)
        .limit(6)
    ).all()
    recent = db.scalars(
        select(Meeting)
        .where(Meeting.user_id == user.id)
        .order_by(Meeting.date.desc(), Meeting.created_at.desc())
        .limit(4)
    ).all()
    return {
        "total_meetings": count(db, Meeting, Meeting.user_id == user.id),
        "total_action_items": count(db, ActionItem, scope),
        "pending_actions": count(db, ActionItem, scope, ActionItem.status == "Pending"),
        "completed_actions": count(db, ActionItem, scope, ActionItem.status == "Completed"),
        "unassigned_actions": count(db, ActionItem, scope, ActionItem.owner == "Unassigned"),
        "upcoming_deadlines": count(
            db,
            ActionItem,
            scope,
            active,
            ActionItem.due_date >= today,
            ActionItem.due_date <= today + timedelta(days=7),
        ),
        "overdue_actions": count(db, ActionItem, scope, active, ActionItem.due_date < today),
        "open_risks": risk_count,
        "unanswered_questions": question_count,
        "recent_meetings": [meeting_card(m) for m in recent],
        "deadline_items": [action_dict(a) for a in upcoming],
        "today": today.isoformat(),
        "timezone": user.timezone,
    }


@router.get("/dashboard/charts")
def charts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    actions = db.execute(
        select(ActionItem.status, ActionItem.priority, ActionItem.owner).where(
            ActionItem.user_id == user.id
        )
    ).all()
    statuses = Counter(row.status for row in actions)
    priorities = Counter(row.priority for row in actions)
    owners = Counter(row.owner for row in actions)
    meeting_dates = db.scalars(select(Meeting.date).where(Meeting.user_id == user.id)).all()
    decision_dates = db.scalars(
        select(Meeting.date).join(Decision).where(Meeting.user_id == user.id)
    ).all()
    risk_dates = db.scalars(select(Meeting.date).join(Risk).where(Meeting.user_id == user.id)).all()
    today = user_today(user)
    # Six actual calendar months; no fabricated trend percentages.
    months = []
    current = today.replace(day=1)
    for _ in range(6):
        months.insert(0, current.strftime("%Y-%m"))
        current = (current - timedelta(days=1)).replace(day=1)
    mc = Counter(d.strftime("%Y-%m") for d in meeting_dates)
    dc = Counter(d.strftime("%Y-%m") for d in decision_dates)
    rc = Counter(d.strftime("%Y-%m") for d in risk_dates)
    return {
        "by_status": [
            {"name": s, "value": statuses[s]}
            for s in ["Pending", "In Progress", "Completed", "Blocked", "Cancelled"]
        ],
        "by_priority": [
            {"name": p, "value": priorities[p]} for p in ["Low", "Medium", "High", "Critical"]
        ],
        "by_owner": [{"name": owner, "value": amount} for owner, amount in owners.most_common(12)],
        "over_time": [
            {"month": month, "meetings": mc[month], "decisions": dc[month], "risks": rc[month]}
            for month in months
        ],
        "counts_include_review_candidates": True,
    }


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return {
        "items": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "message": n.message,
                "meeting_id": n.meeting_id,
                "is_read": n.is_read,
                "created_at": iso_utc(n.created_at),
            }
            for n in items
        ],
        "unread": count(
            db, Notification, Notification.user_id == user.id, Notification.is_read.is_(False)
        ),
    }


@router.put("/notifications/{notification_id}/read")
def read_notification(
    notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if not item:
        raise HTTPException(404, "Notification not found")
    item.is_read = True
    db.commit()
    return {"id": item.id, "is_read": True}


@router.get("/audit-log")
def audit_log(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()
    return {
        "items": [
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "details": a.details,
                "created_at": iso_utc(a.created_at),
            }
            for a in items
        ]
    }
