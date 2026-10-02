import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import RevokedToken, User
from app.schemas.api import (
    LoginRequest,
    PasswordUpdate,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.utils.access import audit
from app.utils.rate_limit import rate_limit
from app.utils.security import (
    bearer,
    create_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


def token_response(user: User) -> TokenResponse:
    token, expires = create_token(user)
    return TokenResponse(
        access_token=token, expires_in=expires, user=UserResponse.model_validate(user)
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "register", 10)
    user = User(
        email=str(data.email).casefold(),
        name=data.name,
        password_hash=hash_password(data.password),
        timezone=data.timezone,
    )
    db.add(user)
    try:
        db.flush()
        audit(db, user.id, "auth.register", "user", user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from None
    return token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "login", 15)
    user = db.scalar(select(User).where(User.email == str(data.email).casefold()))
    if not verify_password(data.password, user.password_hash if user else None):
        logger.warning(
            "authentication_failed", extra={"request_id": getattr(request.state, "request_id", "")}
        )
        raise HTTPException(401, "Incorrect email or password")
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))
    audit(db, user.id, "auth.login", "user", user.id)
    db.commit()
    return token_response(user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserResponse)
def update_profile(
    data: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    for key, value in data.model_dump().items():
        setattr(user, key, value)
    audit(db, user.id, "user.updated", "user", user.id, {"fields": list(data.model_fields_set)})
    db.commit()
    return user


@router.put("/password", status_code=204)
def change_password(
    data: PasswordUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_limit(request, "password", 8)
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    audit(db, user.id, "auth.password_changed", "user", user.id)
    db.commit()


@router.post("/logout", status_code=204)
def logout(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    credentials=Depends(bearer),
):
    payload = decode_token(credentials.credentials)
    db.add(
        RevokedToken(
            jti=payload["jti"], expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc)
        )
    )
    audit(db, user.id, "auth.logout", "user", user.id)
    db.commit()


@router.get("/configuration")
def configuration(user: User = Depends(get_current_user)):
    settings = get_settings()
    return {
        "provider": settings.active_provider,
        "model": settings.openai_model
        if settings.active_provider == "openai"
        else "Conservative extractive engine",
        "embedding_model": settings.openai_embedding_model
        if settings.active_provider == "openai"
        else "lexical-hash-v1-384",
        "demo_enabled": settings.allow_demo_data and settings.app_env == "development",
        "max_upload_size": settings.max_upload_size,
        "max_transcript_chars": settings.max_transcript_chars,
        "smtp_configured": bool(settings.smtp_host),
        "token_lifetime_minutes": settings.access_token_expire_minutes,
        "environment": settings.app_env,
    }
