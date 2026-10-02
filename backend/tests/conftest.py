"""Each test gets a clean isolated database; processing uses real local services."""

import os
from pathlib import Path
import secrets
import tempfile

_TEST_DIR = tempfile.TemporaryDirectory(prefix="grounded-tests-")
os.environ["APP_ENV"] = "test"
os.environ["ALLOW_DEMO_DATA"] = "false"
os.environ["AI_PROVIDER"] = "local"
os.environ["OPENAI_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_FROM"] = ""
os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///" + str(Path(_TEST_DIR.name) / "tests.db")
)
os.environ["UPLOAD_DIR"] = str(Path(_TEST_DIR.name) / "uploads")

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app
from app.utils.rate_limit import _windows


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _windows.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as value:
        yield value


@pytest.fixture
def auth(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "maya@example.com", "name": "Maya", "password": "ValidPassword123"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def other_auth(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "name": "Other User", "password": "ValidPassword123"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


NORMAL_TRANSCRIPT = """Maya: Topic: deployment. Project: Atlas. We reviewed deployment readiness.
Maya: Action: Rahul to add rollback tests by 2026-10-05. High priority.
Rahul: I'll document the deployment runbook by 2026-10-06. This is in progress.
Maya: Decision: We agreed to use a canary deployment.
Rahul: Tentative decision: We are considering a blue-green release later.
Maya: Rejected proposal: We rejected skipping rollback tests.
Maya: Risk: delivery may be delayed because the staging environment is blocked.
Rahul: Open question: Who can approve the production deployment?
Maya: Follow-up: revisit the rollout plan in the next meeting.
Rahul: I am concerned about staging readiness."""


def make_meeting(client, headers, transcript=NORMAL_TRANSCRIPT, title="Platform sprint"):
    result = client.post(
        "/api/meetings",
        headers=headers,
        json={
            "title": title,
            "date": "2026-10-01",
            "participants": ["Maya", "Rahul"],
            "project": "Atlas",
            "transcript": transcript,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def processed_meeting(client, headers, transcript=NORMAL_TRANSCRIPT):
    from app.services.processing import process_meeting

    meeting = make_meeting(client, headers, transcript)
    queued = client.post(f"/api/meetings/{meeting['id']}/process", headers=headers)
    assert queued.status_code == 202, queued.text
    process_meeting(meeting["id"])
    detail = client.get(f"/api/meetings/{meeting['id']}", headers=headers)
    assert detail.json()["processing_status"] == "completed", detail.text
    return detail.json()
