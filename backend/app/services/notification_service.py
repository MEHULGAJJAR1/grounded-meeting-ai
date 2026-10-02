"""In-app notifications plus an optional SMTP transport, with daily deduplication."""

from datetime import timedelta
from email.message import EmailMessage
import logging
import smtplib
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ActionItem, Meeting, Notification, User
from app.utils.access import user_today

logger = logging.getLogger(__name__)


class NotificationTransport(Protocol):
    def send(self, recipient: str, subject: str, message: str) -> None: ...


class SMTPTransport:
    def send(self, recipient: str, subject: str, message: str) -> None:
        settings = get_settings()
        email = EmailMessage()
        email["From"] = settings.smtp_from or settings.smtp_username
        email["To"] = recipient
        email["Subject"] = subject
        email.set_content(message)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(email)


class NotificationService:
    def __init__(self, db: Session, transport: NotificationTransport | None = None):
        self.db = db
        self.transport = transport or (SMTPTransport() if get_settings().smtp_host else None)

    def create(
        self,
        user: User,
        kind: str,
        title: str,
        message: str,
        key: str,
        meeting_id: str | None = None,
    ) -> Notification | None:
        if not user.notifications_enabled or self.db.scalar(
            select(Notification).where(Notification.dedup_key == key)
        ):
            return None
        notification = Notification(
            user_id=user.id,
            kind=kind,
            title=title,
            message=message,
            dedup_key=key,
            meeting_id=meeting_id,
        )
        self.db.add(notification)
        self.db.commit()
        if self.transport and not user.is_demo:
            try:
                self.transport.send(user.email, title, message)
            except Exception as error:
                logger.warning(
                    "notification_delivery_failed",
                    extra={"user_id": user.id, "error_type": type(error).__name__},
                )
        return notification

    def meeting_complete(self, meeting: Meeting):
        self.create(
            meeting.user,
            "meeting_complete",
            "Meeting analysis is ready",
            f"Your meeting '{meeting.title}' has been processed. Review the evidence and action items in Grounded.",
            f"complete:{meeting.id}:{meeting.processed_at.isoformat()}",
            meeting.id,
        )

    def deadline_reminders(self):
        users = self.db.scalars(select(User).where(User.notifications_enabled.is_(True))).all()
        for user in users:
            today = user_today(user)
            actions = self.db.scalars(
                select(ActionItem).where(
                    ActionItem.user_id == user.id,
                    ActionItem.status.not_in(["Completed", "Cancelled"]),
                    ActionItem.due_date.is_not(None),
                    ActionItem.due_date <= today + timedelta(days=3),
                )
            ).all()
            for item in actions:
                overdue = item.due_date < today
                kind = "overdue_task" if overdue else "upcoming_deadline"
                self.create(
                    user,
                    kind,
                    "Task is overdue" if overdue else "Upcoming task deadline",
                    f"'{item.task[:120]}' is due {item.due_date.isoformat()}. Check your action tracker.",
                    f"{kind}:{item.id}:{today.isoformat()}",
                    item.meeting_id,
                )
