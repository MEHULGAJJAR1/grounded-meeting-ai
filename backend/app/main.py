"""FastAPI entrypoint, migrations, queue lifecycle and the integrated React host."""

from contextlib import asynccontextmanager
import logging
from time import monotonic
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import ROOT, get_settings
from app.database import engine
from app.routers import actions, auth, dashboard, development, documents, exports, meetings, search
from app.services.processing import ProcessingWorker
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            too_large = int(headers.get(b"content-length", b"0")) > self.max_bytes
        except ValueError:
            too_large = True
        if too_large:
            return await JSONResponse(
                {
                    "error": {
                        "code": "payload_too_large",
                        "message": "Request exceeds the upload limit",
                        "details": [],
                    }
                },
                413,
            )(scope, receive, send)
        used = 0

        async def limited_receive():
            nonlocal used
            message = await receive()
            used += len(message.get("body", b""))
            if used > self.max_bytes:
                raise HTTPException(413, "Request exceeds the upload limit")
            return message

        await self.app(scope, limited_receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = ProcessingWorker()
    if settings.app_env != "test":
        cfg = Config(str(ROOT / "backend" / "alembic.ini"))
        command.upgrade(cfg, "head")
        settings.upload_path.mkdir(parents=True, exist_ok=True)
        await worker.start()
    app.state.worker = worker
    logger.info("application_started", extra={"stage": settings.active_provider})
    yield
    if settings.app_env != "test":
        await worker.stop()
    logger.info("application_stopped")


app = FastAPI(
    title="Grounded AI Meeting Notes Summariser & Action Tracker",
    version="1.0.0",
    description="Authenticated meeting intelligence with explicit evidence, independent grounding and user-scoped RAG.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    BodyLimitMiddleware,
    max_bytes=max(
        settings.max_upload_size + 128 * 1024, settings.max_transcript_chars * 4 + 128 * 1024
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if settings.app_env == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'"
        )
    logger.info(
        "http_request",
        extra={
            "request_id": request.state.request_id,
            "method": request.method,
            "path": getattr(request.scope.get("route"), "path", "/unmatched"),
            "status": response.status_code,
            "duration_ms": round((monotonic() - start) * 1000),
        },
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, error: StarletteHTTPException):
    detail = error.detail
    message = detail.get("message", "Request failed") if isinstance(detail, dict) else str(detail)
    details = (
        {key: value for key, value in detail.items() if key != "message"}
        if isinstance(detail, dict)
        else []
    )
    code = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        415: "unsupported_file",
        422: "validation_error",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(error.status_code, "request_failed")
    return JSONResponse(
        status_code=error.status_code,
        headers=error.headers,
        content={
            "error": {"code": code, "message": message, "details": details},
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    details = [
        {
            "field": ".".join(str(part) for part in entry["loc"]),
            "message": entry["msg"],
            "type": entry["type"],
        }
        for entry in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Check your input and try again",
                "details": details,
            },
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, error: Exception):
    logger.error(
        "unhandled_exception",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "error_type": type(error).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. Please try again",
                "details": [],
            },
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


for router in (
    auth.router,
    meetings.router,
    actions.router,
    documents.router,
    dashboard.router,
    search.router,
    exports.router,
    development.router,
):
    app.include_router(router)


@app.get("/api/health", tags=["Health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database is unavailable") from None
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": "connected",
        "ai_provider": settings.active_provider,
        "demo_enabled": settings.allow_demo_data and settings.app_env == "development",
    }


WEB_ROOT = ROOT / "frontend" / "web"


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if path.startswith("api/") or path == "api":
        raise HTTPException(404, "API route not found")
    target = (WEB_ROOT / path).resolve()
    if target.is_relative_to(WEB_ROOT.resolve()) and target.is_file():
        return FileResponse(target)
    index = WEB_ROOT / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(
        404, "Frontend is not built. Run python scripts/run.py or npm run build in frontend"
    )
