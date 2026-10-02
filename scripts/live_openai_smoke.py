#!/usr/bin/env python3
"""Explicitly consented, billable OpenAI integration check using fictional data.

Uses a disposable SQLite database, real provider SDK calls, production processing
and tenant-scoped RAG. Does not print keys, tokens, passwords or transcript bodies.
"""

import argparse
from datetime import date
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Consent to real OpenAI requests and account charges for fictional test data",
    )
    args = parser.parse_args()
    if not args.confirm_live:
        raise SystemExit(
            "No requests made. Pass --confirm-live to consent to billable provider checks."
        )
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise SystemExit("No requests made. Configure OPENAI_API_KEY in your private .env first.")
    with tempfile.TemporaryDirectory(prefix="grounded-live-check-") as directory:
        os.environ.update(
            APP_ENV="test",
            SMTP_HOST="",
            SMTP_FROM="",
            AI_PROVIDER="openai",
            ALLOW_DEMO_DATA="false",
            DATABASE_URL="sqlite:///" + str(Path(directory) / "check.db"),
            UPLOAD_DIR=str(Path(directory) / "uploads"),
            JWT_SECRET_KEY=secrets.token_urlsafe(48),
        )
        sys.path.insert(0, str(ROOT / "backend"))
        from app.database import Base, SessionLocal, engine
        from app.models import Meeting, Transcript, User
        from app.services.processing import process_meeting
        from app.services.rag import answer_question
        from app.utils.security import hash_password

        Base.metadata.create_all(engine)
        source = (
            "Maya: Action: update the migration checklist.\n"
            "Maya: Action: Rahul to write the release runbook by 2026-10-08. High priority.\n"
            "Rahul: I'll share the deployment draft by Friday.\n"
            "Maya: Risk: capacity approval may delay delivery.\n"
            "Rahul: Open question: Who approves the deployment?"
        )
        with SessionLocal() as db:
            user = User(
                name="Maya",
                email="live-check@example.com",
                password_hash=hash_password(secrets.token_urlsafe(24)),
            )
            other = User(
                name="Other account",
                email="isolated-check@example.com",
                password_hash=hash_password(secrets.token_urlsafe(24)),
            )
            db.add_all([user, other])
            db.flush()
            meeting = Meeting(
                user_id=user.id,
                title="Fictional provider verification",
                date=date(2026, 10, 1),
                meeting_type="Provider check",
                processing_status="queued",
            )
            db.add(meeting)
            db.flush()
            db.add(Transcript(meeting_id=meeting.id, raw_text=source))
            db.commit()
            meeting_id, user_id, other_id = meeting.id, user.id, other.id
        try:
            process_meeting(meeting_id)
            with SessionLocal() as db:
                meeting = db.get(Meeting, meeting_id)
                assert meeting.processing_status == "completed", (
                    "Provider processing did not complete"
                )
                assert meeting.analysis_provider == "openai", "Unexpected provider"
                actions = meeting.action_items
                missing = next(a for a in actions if "migration checklist" in a.task.casefold())
                assert missing.owner == "Unassigned" and missing.due_date_text == "Not specified"
                explicit = next(a for a in actions if "release runbook" in a.task.casefold())
                assert explicit.owner == "Rahul" and explicit.due_date == date(2026, 10, 8)
                relative = next(a for a in actions if "deployment draft" in a.task.casefold())
                assert relative.due_date is None and "friday" in relative.due_date_text.casefold()
                assert all(r.severity == "Unknown" for r in meeting.risks)
                assert all(a.evidence for a in actions)
                answer = answer_question(
                    db, db.get(User, user_id), "Show action items assigned to Rahul.", 8, None, []
                )
                assert answer["claims"] and not answer["insufficient_evidence"]
                assert all(s["meeting_id"] == meeting_id for s in answer["sources"])
                isolated = answer_question(
                    db, db.get(User, other_id), "Show action items assigned to Rahul.", 8, None, []
                )
                assert isolated["insufficient_evidence"] and not isolated["sources"]
                print(
                    json.dumps(
                        {
                            "passed": True,
                            "provider": "openai",
                            "actions": len(actions),
                            "checked_claims": meeting.summary.grounding_report["checked_claims"],
                            "answer_claims": len(answer["claims"]),
                            "tenant_isolation": True,
                            "data": "fictional; disposable database removed on exit",
                        },
                        indent=2,
                    )
                )
        except Exception as error:
            print(json.dumps({"passed": False, "error_type": type(error).__name__}))
            raise SystemExit(
                "Live check failed. Check provider configuration and meeting verification semantics; no private payload was logged."
            ) from None
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
