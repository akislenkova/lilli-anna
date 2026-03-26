"""Main API router aggregating all route modules."""

from fastapi import APIRouter

from backend.app.api.routes import (
    admin,
    ai_reports,
    appointments,
    auth,
    conversations,
    feedback,
    patients,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(
    conversations.router, prefix="/conversations", tags=["Conversations"]
)
api_router.include_router(
    appointments.router, prefix="/appointments", tags=["Appointments"]
)
api_router.include_router(ai_reports.router, prefix="/reports", tags=["AI Reports"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(admin.router)
