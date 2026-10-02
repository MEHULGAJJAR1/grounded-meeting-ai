from app.database import SessionLocal
from app.models import User
from sqlalchemy import select


def test_registration_login_and_hash(client):
    values = {"email": "Maya@example.com", "name": "Maya", "password": "ValidPassword123"}
    result = client.post("/api/auth/register", json=values)
    assert result.status_code == 201
    assert "password_hash" not in result.json()["user"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "maya@example.com"))
        assert user.password_hash.startswith("$2b$") and user.password_hash != values["password"]
    assert client.post("/api/auth/register", json=values).status_code == 409
    assert (
        client.post(
            "/api/auth/login", json={"email": values["email"], "password": "incorrect"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "absent@example.com", "password": "incorrect"}
        ).status_code
        == 401
    )
    login = client.post(
        "/api/auth/login", json={"email": values["email"], "password": values["password"]}
    )
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/api/auth/me", headers=headers).json()["email"] == "maya@example.com"


def test_logout_revokes_access_token(client, auth):
    assert client.post("/api/auth/logout", headers=auth).status_code == 204
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_password_change_invalidates_sessions(client, auth):
    changed = client.put(
        "/api/auth/password",
        headers=auth,
        json={"current_password": "ValidPassword123", "new_password": "EvenStronger456"},
    )
    assert changed.status_code == 204
    assert client.get("/api/auth/me", headers=auth).status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "maya@example.com", "password": "EvenStronger456"}
        ).status_code
        == 200
    )


def test_profile_validation(client, auth):
    invalid = client.put(
        "/api/auth/me",
        headers=auth,
        json={"name": "Maya", "timezone": "Made/Up", "notifications_enabled": True},
    )
    assert invalid.status_code == 422
    changed = client.put(
        "/api/auth/me",
        headers=auth,
        json={"name": "Maya Shah", "timezone": "UTC", "notifications_enabled": False},
    )
    assert changed.status_code == 200
    assert changed.json()["timezone"] == "UTC" and changed.json()["notifications_enabled"] is False


def test_password_validation_and_safe_error(client):
    result = client.post(
        "/api/auth/register", json={"email": "test@example.com", "name": "Test", "password": "weak"}
    )
    assert result.status_code == 422
    assert "weak" not in result.text
    assert result.json()["error"]["code"] == "validation_error"
    # Bcrypt's byte limit must not silently truncate multi-byte passwords.
    result = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "name": "Test", "password": "é" * 40 + "1"},
    )
    assert result.status_code == 422


def test_unauthorized_and_invalid_tokens(client):
    assert client.get("/api/meetings").status_code == 401
    assert (
        client.get(
            "/api/dashboard/stats", headers={"Authorization": "Bearer invalid-token"}
        ).status_code
        == 401
    )


def test_rate_limit(client):
    responses = [
        client.post("/api/auth/login", json={"email": "test@example.com", "password": "incorrect"})
        for _ in range(16)
    ]
    assert responses[-1].status_code == 429
    assert responses[-1].headers["Retry-After"]
