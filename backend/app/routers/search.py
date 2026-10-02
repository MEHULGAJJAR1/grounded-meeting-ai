from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.api import AskRequest, SearchRequest
from app.services.rag import answer_question, retrieve
from app.utils.rate_limit import rate_limit
from app.utils.security import get_current_user

router = APIRouter(prefix="/api", tags=["Search & grounded assistant"])


@router.post("/search")
def search(
    data: SearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_limit(request, "search", 40)
    return retrieve(db, user, data.query, data.limit, data.meeting_id)


@router.post("/ask")
def ask(
    data: AskRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_limit(request, "ask", 20)
    return answer_question(db, user, data.query, data.limit, data.meeting_id, data.history)
