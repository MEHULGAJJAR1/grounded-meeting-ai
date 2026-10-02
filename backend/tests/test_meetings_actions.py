import pytest
from conftest import make_meeting, processed_meeting


def test_meeting_crud(client, auth):
    meeting = make_meeting(client, auth)
    path = f"/api/meetings/{meeting['id']}"
    assert client.get(path, headers=auth).json()["title"] == "Platform sprint"
    changed = client.put(
        path,
        headers=auth,
        json={"title": "Release planning", "participants": ["Maya", "Maya", "Rahul"]},
    )
    assert changed.status_code == 200 and changed.json()["participants"] == ["Maya", "Rahul"]
    assert client.get("/api/meetings", headers=auth).json()["total"] == 1
    assert client.get("/api/meetings?q=Release", headers=auth).json()["total"] == 1
    assert client.delete(path, headers=auth).status_code == 204
    assert client.get(path, headers=auth).status_code == 404


def test_action_crud_and_filters(client, auth):
    meeting = make_meeting(client, auth)
    result = client.post(
        "/api/action-items",
        headers=auth,
        json={
            "meeting_id": meeting["id"],
            "task": "Write API integration tests",
            "owner": "Maya",
            "priority": "High",
            "due_date": "2020-01-01",
        },
    )
    assert result.status_code == 201, result.text
    item = result.json()
    path = f"/api/action-items/{item['id']}"
    assert item["grounding_status"] == "user_provided" and item["source_type"] == "manual"
    assert client.get("/api/action-items?filter=My%20Tasks", headers=auth).json()["total"] == 1
    assert client.get("/api/action-items?filter=Overdue", headers=auth).json()["total"] == 1
    changed = client.put(
        path,
        headers=auth,
        json={"status": "Completed", "owner": "Rahul", "notes": "Reviewed", "due_date": None},
    )
    assert changed.status_code == 200 and changed.json()["due_date_text"] == "Not specified"
    assert changed.json()["manually_edited"] is True
    assert client.get("/api/action-items?filter=Completed", headers=auth).json()["total"] == 1
    assert client.get("/api/action-items?filter=Overdue", headers=auth).json()["total"] == 0
    assert client.delete(path, headers=auth).status_code == 204
    assert client.put(path, headers=auth, json={"status": "Pending"}).status_code == 404


def test_processing_and_provenance_preservation(client, auth):
    from app.services.processing import process_meeting

    m = processed_meeting(client, auth)
    assert m["summary"] and m["grounding_report"]["verified"] > 0
    assert len(m["decisions"]) == 3 and len(m["action_items"]) == 2
    assert {d["decision_type"] for d in m["decisions"]} == {"Confirmed", "Tentative", "Rejected"}
    assert m["action_items"][0]["owner"] in {"Rahul"}
    action = m["action_items"][0]
    client.put(
        f"/api/action-items/{action['id']}",
        headers=auth,
        json={"status": "Completed", "notes": "Human edit"},
    )
    client.post(f"/api/meetings/{m['id']}/process", headers=auth)
    process_meeting(m["id"])
    fresh = client.get(f"/api/meetings/{m['id']}", headers=auth).json()
    retained = next(a for a in fresh["action_items"] if a["id"] == action["id"])
    assert (
        retained["notes"] == "Human edit" and retained["source_snapshot"]["status"] != "Completed"
    )
    assert len(fresh["action_items"]) == 2


def test_transcript_edits_invalidate_stale_results(client, auth):
    m = processed_meeting(client, auth)
    action = m["action_items"][0]
    client.put(f"/api/action-items/{action['id']}", headers=auth, json={"status": "Completed"})
    result = client.put(
        f"/api/meetings/{m['id']}",
        headers=auth,
        json={"transcript": "Maya: We discussed a completely different topic."},
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["summary"] is None and data["processing_status"] == "draft"
    assert len(data["action_items"]) == 1 and data["action_items"][0]["source_type"] == "manual"
    assert data["action_items"][0]["grounding_status"] == "user_provided"
    assert (
        client.post("/api/search", headers=auth, json={"query": "deployment"}).json()["sources"]
        == []
    )


def test_processing_empty_transcript_and_lock(client, auth):
    empty = make_meeting(client, auth, "")
    assert client.post(f"/api/meetings/{empty['id']}/process", headers=auth).status_code == 422
    m = make_meeting(client, auth)
    assert client.post(f"/api/meetings/{m['id']}/process", headers=auth).status_code == 202
    assert client.post(f"/api/meetings/{m['id']}/process", headers=auth).status_code == 409
    assert (
        client.put(
            f"/api/meetings/{m['id']}", headers=auth, json={"title": "New title"}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/meetings/{m['id']}", headers=auth).status_code == 409
    state = client.get(f"/api/meetings/{m['id']}/processing-status", headers=auth).json()
    assert state["status"] == "queued" and state["progress"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "x", "date": "bad"},
        {"title": "Okay", "date": "2026-10-01", "unknown": True},
        {"title": "Okay", "date": "2026-10-01", "participants": [""]},
    ],
)
def test_malformed_meeting_requests(client, auth, payload):
    result = client.post("/api/meetings", headers=auth, json=payload)
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "validation_error"


def test_malformed_action_and_null_meeting_field(client, auth):
    m = make_meeting(client, auth)
    assert (
        client.post(
            "/api/action-items",
            headers=auth,
            json={"meeting_id": m["id"], "task": "Do work", "priority": "Urgent"},
        ).status_code
        == 422
    )
    assert (
        client.put(f"/api/meetings/{m['id']}", headers=auth, json={"title": None}).status_code
        == 422
    )
    assert client.get("/api/action-items?filter=Invented", headers=auth).status_code == 422


def test_risk_resolution_question_answer_and_notifications(client, auth):
    m = processed_meeting(client, auth)
    risk = m["risks"][0]
    question = m["questions"][0]
    assert (
        client.put(
            f"/api/risks/{risk['id']}", headers=auth, json={"status": "Resolved"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/questions/{question['id']}",
            headers=auth,
            json={"status": "Answered", "answer": "The release lead will approve it."},
        ).status_code
        == 200
    )
    stats = client.get("/api/dashboard/stats", headers=auth).json()
    assert stats["open_risks"] == 0 and stats["unanswered_questions"] == 0
    ns = client.get("/api/notifications", headers=auth).json()
    assert ns["unread"] == 1
    assert (
        client.put(f"/api/notifications/{ns['items'][0]['id']}/read", headers=auth).status_code
        == 200
    )
    assert client.get("/api/notifications", headers=auth).json()["unread"] == 0
