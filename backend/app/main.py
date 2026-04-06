"""Anilla - AI-Powered Clinic Scheduling System API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.session_middleware import SessionMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered clinic scheduling system for primary care practices. "
    "Collects structured pre-visit information, estimates appointment duration, "
    "and provides comprehensive reports — all HIPAA-compliant.",
    version="2.0.0",
    lifespan=lifespan,
)

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


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME, "version": "2.0.0"}
