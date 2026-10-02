"""Bcrypt passwords and short-lived, revocable JWT access tokens."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import RevokedToken, User

bearer = HTTPBearer(auto_error=False)
# A random dummy hash ensures missing-email logins still perform bcrypt work.
_DUMMY_HASH = bcrypt.hashpw(bcrypt.gensalt(), bcrypt.gensalt(rounds=12))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, stored_hash: str | None) -> bool:
    value = password.encode("utf-8")
    if len(value) > 72:
        return False
    return (
        bcrypt.checkpw(value, stored_hash.encode("ascii") if stored_hash else _DUMMY_HASH)
        and stored_hash is not None
    )


def create_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    seconds = settings.access_token_expire_minutes * 60
    payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + timedelta(seconds=seconds),
        "jti": str(uuid4()),
        "ver": user.token_version,
        "iss": "grounded-meeting-ai",
        "aud": "grounded-api",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256"), seconds


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            get_settings().jwt_secret_key,
            algorithms=["HS256"],
            audience="grounded-api",
            issuer="grounded-meeting-ai",
            options={"require": ["sub", "exp", "iat", "jti", "ver"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}
        ) from None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(credentials.credentials)
    if db.get(RevokedToken, payload["jti"]):
        raise HTTPException(401, "Access token has been revoked")
    user = db.get(User, payload["sub"])
    if not user or user.token_version != payload["ver"]:
        raise HTTPException(401, "Invalid session; please sign in again")
    return user
