"""Provider wire-contract tests use an HTTP transport ONLY inside tests.

No production service returns fixtures. Live OpenAI validation is a separate,
explicit opt-in script because tests must not send private data or spend money.
"""

import asyncio
from datetime import timedelta
import json
import secrets

import httpx
from openai import OpenAI
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import ActionItem, Meeting, Notification, User
from app.schemas.intelligence import ExtractionOutput
from app.services.ai_service import AIServiceError, OpenAIService
from app.services.embeddings import cosine, embed_texts, local_embedding
from app.services.local_extractor import extract_local
from app.services.notification_service import NotificationService
from app.services.processing import ProcessingWorker, process_meeting
from app.utils.access import user_today
from conftest import NORMAL_TRANSCRIPT, make_meeting, processed_meeting
import pytest


def test_real_sdk_structured_output_wire_contract(monkeypatch):
    expected = extract_local(NORMAL_TRANSCRIPT)
    requests = []

    def transport(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["response_format"]["type"] == "json_schema"
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert schema["schema"]["additionalProperties"] is False
        return httpx.Response(
            200,
            json={
                "id": "contract-response",
                "object": "chat.completion",
                "created": 1770000000,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": expected.model_dump_json(),
                            "refusal": None,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            },
        )

    settings = get_settings()
    old = settings.openai_api_key
    settings.openai_api_key = secrets.token_urlsafe(32)
    client = OpenAI(
        api_key=settings.openai_api_key,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
    )
    monkeypatch.setattr("app.services.ai_service.OpenAI", lambda **kwargs: client)
    try:
        actual = OpenAIService().extract(NORMAL_TRANSCRIPT, 1, {"title": "Contract test"})
        assert isinstance(actual, ExtractionOutput) and actual.action_items[0].owner == "Rahul"
        assert "untrusted DATA" in requests[0]["messages"][0]["content"]
    finally:
        settings.openai_api_key = old
        client.close()


def test_openai_failure_is_safe_and_not_fake_fallback(monkeypatch):
    settings = get_settings()
    old = settings.openai_api_key
    settings.openai_api_key = secrets.token_urlsafe(32)
    client = OpenAI(
        api_key=settings.openai_api_key,
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    401,
                    json={
                        "error": {
                            "message": "sensitive vendor body",
                            "type": "invalid_request_error",
                        }
                    },
                )
            )
        ),
    )
    monkeypatch.setattr("app.services.ai_service.OpenAI", lambda **kwargs: client)
    try:
        with pytest.raises(AIServiceError) as raised:
            OpenAIService().extract(NORMAL_TRANSCRIPT, 1, {})
        assert "sensitive vendor body" not in str(raised.value)
    finally:
        settings.openai_api_key = old
        client.close()


def test_local_embedding_is_deterministic_and_retrieval_is_meaningful():
    assert local_embedding("deployment plan") == local_embedding("deployment plan")
    assert cosine(local_embedding("deployment"), local_embedding("deployment release")) > cosine(
        local_embedding("deployment"), local_embedding("gardening flowers")
    )
    vectors, provider, model = embed_texts(["deployment"], "local")
    assert provider == "local" and len(vectors[0]) == 384 and model.startswith("lexical-hash")


def test_worker_claims_real_queued_jobs(client, auth):
    meeting = make_meeting(client, auth)
    assert client.post(f"/api/meetings/{meeting['id']}/process", headers=auth).status_code == 202

    async def exercise():
        worker = ProcessingWorker()
        await worker.start()
        try:
            for _ in range(80):
                await asyncio.sleep(0.025)
                with SessionLocal() as db:
                    if db.get(Meeting, meeting["id"]).processing_status == "completed":
                        return
            raise AssertionError("Worker did not finish the queued real local job")
        finally:
            await worker.stop()

    asyncio.run(exercise())
    assert (
        client.get(f"/api/meetings/{meeting['id']}/processing-status", headers=auth).json()[
            "progress"
        ]
        == 100
    )


def test_failed_analysis_has_persisted_safe_failure(client, auth, monkeypatch):
    meeting = make_meeting(client, auth)

    def fail(*args, **kwargs):
        raise AIServiceError("Provider unavailable; retry later")

    monkeypatch.setattr("app.services.processing.Summarizer.extract", fail)
    process_meeting(meeting["id"])
    data = client.get(f"/api/meetings/{meeting['id']}", headers=auth).json()
    assert data["processing_status"] == "failed" and data["summary"] is None
    assert "Provider unavailable" in data["processing_error"]


def test_notifications_deadline_dedup_and_transport(client, auth):
    meeting = make_meeting(client, auth)

    class CapturingTransport:
        def __init__(self):
            self.sent = []

        def send(self, recipient, subject, message):
            self.sent.append((recipient, subject, message))

    transport = CapturingTransport()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "maya@example.com"))
        today = user_today(user)
        db.add(
            ActionItem(
                meeting_id=meeting["id"],
                user_id=user.id,
                task="Upcoming task",
                owner="Maya",
                due_date=today + timedelta(days=1),
                due_date_text=(today + timedelta(days=1)).isoformat(),
            )
        )
        db.add(
            ActionItem(
                meeting_id=meeting["id"],
                user_id=user.id,
                task="Overdue task",
                due_date=today - timedelta(days=1),
                due_date_text=(today - timedelta(days=1)).isoformat(),
            )
        )
        db.commit()
        service = NotificationService(db, transport)
        service.deadline_reminders()
        service.deadline_reminders()
        assert len(transport.sent) == 2
        assert len(db.scalars(select(Notification)).all()) == 2
        user.notifications_enabled = False
        db.commit()
        assert service.create(user, "test", "Title", "Message", "disabled") is None


def test_openai_field_verification_keeps_task_and_resets_wrong_owner(monkeypatch):
    from app.schemas.intelligence import Verification, VerificationBatch
    from app.services.grounding import verify_extraction

    text = "Maya: Action: update the runbook. Rahul will review the design."
    proposed = extract_local(text)
    proposed.action_items[0].owner = "Rahul"
    proposed.action_items[0].owner_evidence = text
    settings = get_settings()
    old = settings.openai_api_key
    settings.openai_api_key = secrets.token_urlsafe(32)

    def checks(self, claims, context):
        return VerificationBatch(
            checks=[
                Verification(
                    claim_id=c["claim_id"],
                    verdict="unsupported" if c["kind"] == "explicit task owner" else "supported",
                    reason="Assignment must refer to this task",
                    score=0.05 if c["kind"] == "explicit task owner" else 0.9,
                )
                for c in claims
            ]
        )

    monkeypatch.setattr("app.services.ai_service.OpenAIService.verify", checks)
    try:
        result, report = verify_extraction(proposed, text, "openai")
        assert result["action_items"][0]["owner"] == "Unassigned"
        assert result["action_items"][0]["grounding_status"] == "review"
        assert report["metadata_corrections"] == 1
    finally:
        settings.openai_api_key = old


def test_rag_answer_requires_quotes_and_independent_entailment(client, auth, monkeypatch):
    from app.schemas.intelligence import RAGAnswer, AnswerClaim, Verification, VerificationBatch
    from app.services.ai_service import OpenAIService

    processed_meeting(client, auth, "Maya: Action: write the runbook.")
    settings = get_settings()
    old = settings.openai_api_key
    old_provider = settings.ai_provider
    settings.ai_provider = "openai"
    settings.openai_api_key = secrets.token_urlsafe(32)

    def propose(self, query, sources, history):
        return RAGAnswer(
            insufficient_evidence=False,
            explanation="",
            claims=[
                AnswerClaim(
                    text="The task is cancelled",
                    source_ids=[sources[0]["id"]],
                    evidence_quotes=["Status: Pending"],
                ),
                AnswerClaim(
                    text="Unrelated claim",
                    source_ids=["missing-source"],
                    evidence_quotes=["unrelated text"],
                ),
            ],
        )

    def verify(self, claims, context):
        return VerificationBatch(
            checks=[
                Verification(
                    claim_id=c["claim_id"],
                    verdict="unsupported",
                    reason="A pending record does not entail cancellation",
                    score=0,
                )
                for c in claims
            ]
        )

    monkeypatch.setattr(OpenAIService, "answer", propose)
    monkeypatch.setattr(OpenAIService, "verify", verify)
    try:
        response = client.post("/api/ask", headers=auth, json={"query": "Show pending tasks"})
        assert response.status_code == 200
        assert (
            response.json()["insufficient_evidence"]
            and response.json()["grounding"]["withheld"] == 2
        )
    finally:
        settings.openai_api_key = old
        settings.ai_provider = old_provider
