"""Anilla - AI-Powered Clinic Scheduling System API."""

import logging
import logging.config
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.core.limiter import limiter
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.session_middleware import SessionMiddleware

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
        "loggers": {
            # Suppress noisy SQLAlchemy query logs unless DEBUG
            "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
            "sqlalchemy.pool": {"level": "WARNING", "propagate": True},
        },
    }
)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is idempotent — safe to run on every startup in all environments
    await init_db()

    from app.core.seed import seed_demo_data
    async with async_session_factory() as session:
        await seed_demo_data(session)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered clinic scheduling system for primary care practices. "
    "Collects structured pre-visit information, estimates appointment duration, "
    "and provides comprehensive reports — all HIPAA-compliant.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.add_middleware(SessionMiddleware)

app.include_router(api_router, prefix="/api")


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Convert service-layer ValueError to 422 instead of leaking a 500."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
    """Convert service-layer PermissionError to 403 instead of leaking a 500."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def _check_http(url: str, timeout: float = 2.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
        return "ok" if r.status_code < 500 else "error"
    except Exception:
        return "unreachable"


@app.get("/health")
async def health_check():
    checks: dict[str, str] = {}

    # Database
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # External service stubs
    checks["ehr"] = await _check_http(settings.EHR_BASE_URL.rstrip("/") + "/health")
    checks["transcription"] = await _check_http(
        settings.TRANSCRIPTION_SERVICE_URL.rstrip("/") + "/health"
    )

    # Only the database is required; external stubs being unreachable is expected in dev
    db_ok = checks["database"] == "ok"
    overall = "healthy" if db_ok else "unhealthy"

    return JSONResponse(
        status_code=200 if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": overall,
            "service": settings.APP_NAME,
            "version": "2.0.0",
            "checks": checks,
        },
    )
