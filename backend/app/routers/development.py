import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.routers.auth import token_response
from app.schemas.api import TokenResponse
from app.services.seed_data import load_demo_data
from app.utils.rate_limit import rate_limit
from app.utils.security import get_current_user, hash_password

router = APIRouter(prefix="/api/dev", tags=["Development data"])


def require_development():
    settings = get_settings()
    if not settings.allow_demo_data or settings.app_env != "development":
        raise HTTPException(404, "Not found")


@router.post("/demo-session", response_model=TokenResponse, status_code=201)
def demo_session(request: Request, db: Session = Depends(get_db)):
    require_development()
    rate_limit(request, "demo", 4, 300)
    # Every click gets an isolated user, not a shared public account.
    user = User(
        email=f"demo-{uuid4().hex[:16]}@example.com",
        name="Alex Morgan",
        password_hash=hash_password(secrets.token_urlsafe(36)),
        is_demo=True,
    )
    db.add(user)
    db.commit()
    load_demo_data(db, user)
    return token_response(user)


@router.post("/demo-data")
def demo_data(
    request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    require_development()
    rate_limit(request, "seed", 4, 300)
    identities = load_demo_data(db, user)
    return {
        "created": len(identities),
        "meeting_ids": identities,
        "message": "Five labelled sample meetings are available. Existing demo meetings were not duplicated.",
    }
