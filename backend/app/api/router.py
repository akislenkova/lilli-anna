"""Main API router aggregating all route modules."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai_reports,
    appointments,
    auth,
    conversations,
    feedback,
    messages,
    patients,
)

api_router = APIRouter()

# Each route module defines its own prefix (e.g. /auth, /appointments, etc.)
# so we include them without adding additional prefixes here.
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(patients._physician_router)
api_router.include_router(conversations.router)
api_router.include_router(appointments.router)
api_router.include_router(ai_reports.router)
api_router.include_router(feedback.router)
api_router.include_router(messages.router)
api_router.include_router(admin.router)
