"""Five explicitly labelled fictional meetings, processed by the real local pipeline."""

from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document, Meeting, Participant, Transcript, User, new_id
from app.services.document_parser import attachment_text
from app.services.processing import process_meeting
from app.utils.access import audit, user_today


def load_demo_data(db: Session, user: User) -> list[str]:
    today = user_today(user)

    def ds(days):
        return (today + timedelta(days=days)).isoformat()

    owner = user.name
    fixtures = [
        (
            "Sprint planning · Platform",
            -1,
            "Sprint planning",
            "Atlas",
            ["Maya", "Rahul", owner],
            f"""Maya: Topic: deployment. Project: Atlas. We are planning the next platform sprint.
Rahul: Decision: We agreed to use a staged deployment with a canary release.
Maya: Action: Rahul to add deployment rollback tests by {ds(3)}. High priority.
{owner}: I'll update the sprint dashboard by {ds(2)}. This is in progress.
Maya: Action: document the canary runbook. Owner is not assigned yet.
Rahul: Risk: delivery may be delayed because the staging environment is blocked by the database migration.
Maya: Open question: Who can approve the production release?
{owner}: Follow-up: revisit the deployment checklist in the next meeting.
Maya: I am pleased with the great progress on Atlas.""",
        ),
        (
            "Product & design alignment",
            -4,
            "Design review",
            "Atlas",
            ["Zoe", "Maya", owner],
            f"""Zoe: Topic: dashboard. The new dashboard groups actions by owner and status.
Maya: Decision: We approved the compact dashboard layout for the next release.
Zoe: Rejected proposal: We rejected hiding unassigned actions from the dashboard.
Zoe: I'll deliver the dashboard accessibility review by {ds(5)}. High priority.
{owner}: Action: {owner} will fix the keyboard navigation by {ds(-1)}. Medium priority.
Maya: Risk: accessibility testing is waiting for the shared test device.
Zoe: Open question: Should completed actions be archived after 30 days?
Maya: Follow-up: review the mobile dashboard layout next week.""",
        ),
        (
            "Authentication architecture review",
            -8,
            "Technical review",
            "Atlas",
            ["Rahul", "Maya", owner],
            f"""Rahul: Topic: authentication. The API currently validates short-lived JWT access tokens.
Maya: Decision: We decided to revoke sessions when passwords change.
Rahul: Tentative decision: We are considering passkeys for a later authentication milestone.
Rahul: I'll implement token revocation by {ds(-3)}. This action is completed. High priority.
{owner}: I'll write the authentication integration tests by {ds(1)}. Critical priority.
Maya: Action: evaluate the session timeout UX. No owner or deadline has been specified.
Rahul: Risk: a technical security bug may allow stale sessions to persist until token expiry.
Maya: Open question: What session duration should enterprise customers use?
Rahul: Commitment: I will share the API threat model by {ds(4)}.""",
        ),
        (
            "Data migration readiness",
            -15,
            "Project review",
            "Orbit",
            ["Rahul", "Zoe", owner],
            f"""Rahul: Topic: database migration. Project: Orbit. The migration copies historical analytics events.
Zoe: Decision: We agreed to perform the database migration in a maintenance window.
Rahul: I'll rehearse the migration with a production-sized dataset by {ds(-2)}. The action is blocked. High priority.
{owner}: Action: {owner} to validate the analytics event counts by {ds(6)}. Low priority.
Zoe: Action: publish the maintenance notice by Friday.
Rahul: Dependency: the migration depends on approval from the infrastructure team.
Zoe: Risk: delivery could be delayed if the export exceeds the maintenance window.
{owner}: Open question: How will failed events be replayed?
Rahul: I am concerned about the time needed for the database backfill.""",
        ),
        (
            "Customer onboarding retrospective",
            -35,
            "Retrospective",
            "Orbit",
            ["Maya", "Zoe", owner],
            f"""Maya: Topic: onboarding. We reviewed the customer onboarding workflow for Orbit.
Zoe: Decision: We confirmed that each new account will get a guided onboarding checklist.
Maya: I'll publish the onboarding checklist by {ds(-20)}. The action is completed. Medium priority.
Zoe: Action: Zoe to test the onboarding email copy by {ds(7)}. Low priority.
{owner}: I'll organise an onboarding training session. No deadline is specified.
Maya: Risk: a resource capacity shortage may slow down new account support.
Zoe: Open question: Which support hours should appear in the onboarding guide?
{owner}: Follow-up: revisit customer onboarding feedback at the next retrospective.
Maya: I am happy with the onboarding feedback.""",
        ),
    ]
    created = []
    for title, offset, kind, project, names, text in fixtures:
        existing = db.scalar(
            select(Meeting).where(
                Meeting.user_id == user.id, Meeting.is_demo.is_(True), Meeting.title == title
            )
        )
        if existing:
            continue
        meeting = Meeting(
            user_id=user.id,
            title=title,
            date=today + timedelta(days=offset),
            meeting_type=kind,
            project=project,
            is_demo=True,
            processing_status="draft",
        )
        unique_names = list({name.casefold(): name for name in reversed(names)}.values())
        meeting.participants = [Participant(name=name) for name in reversed(unique_names)]
        db.add(meeting)
        db.flush()
        identity = new_id()
        filename = title.split(" ·")[0].lower().replace(" ", "-").replace("&", "and") + ".txt"
        path = get_settings().upload_path / user.id / f"{identity}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        document = Document(
            id=identity,
            user_id=user.id,
            meeting_id=meeting.id,
            filename=filename,
            file_type="txt",
            storage_path=str(path),
            size_bytes=len(text.encode()),
            processing_status="completed",
            extracted_text=text,
            pages=[{"page": None, "section": 1, "text": text}],
            attached_to_transcript=True,
        )
        db.add(document)
        meeting.transcript = Transcript(raw_text=attachment_text(document))
        audit(db, user.id, "demo.loaded", "meeting", meeting.id, {"fictional": True})
        db.commit()
        process_meeting(meeting.id, provider_override="local")
        created.append(meeting.id)
    db.expire_all()
    return created
