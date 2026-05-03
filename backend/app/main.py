import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import agents, observability, workflows
from app.config import get_settings
from app.dependencies import require_api_key
from app.db import Base, SessionLocal, engine
from app.errors import register_exception_handlers
from app.logging import configure_logging
from app.runtime import set_request_id
from app.schemas import HealthResponse
from app.services.seed import seed_demo_data
from app.services.tracing import configure_langsmith


settings = get_settings()
configure_logging(settings.log_level)
configure_langsmith(settings)
logger = logging.getLogger("app.http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    summary="Production-aware governance and observability API for AI agent workflows.",
    description=(
        "FastAPI + LangGraph proof of concept for enterprise AI agent governance. "
        "The API demonstrates registry management, policy enforcement, approvals, kill switches, "
        "structured audit trails, and runtime observability for risky automated actions."
    ),
    contact={"name": "CTO Portfolio Demo", "url": "https://example.internal/agent-governance"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "system", "description": "Operational and readiness endpoints."},
        {"name": "agents", "description": "Agent registry and operator controls."},
        {"name": "workflow-runs", "description": "Workflow execution, approvals, and run state inspection."},
        {"name": "observability", "description": "Runtime logs, events, and usage visibility."},
    ],
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    set_request_id(request_id)
    request.state.request_id = request_id
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(response, "status_code", 500),
                "duration_ms": duration_ms,
            },
        )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(agents.router, prefix=settings.api_base_path, dependencies=[Depends(require_api_key)])
app.include_router(observability.router, prefix=settings.api_base_path, dependencies=[Depends(require_api_key)])
app.include_router(workflows.router, prefix=settings.api_base_path, dependencies=[Depends(require_api_key)])


@app.get("/health", tags=["system"], summary="Service health and readiness probe", response_model=HealthResponse)
def healthcheck() -> dict[str, str | bool]:
    database_status = "ok"
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": database_status,
        "auth_enabled": settings.auth_enabled,
        "langsmith_tracing_enabled": settings.langsmith_tracing and bool(settings.langsmith_api_key),
    }
