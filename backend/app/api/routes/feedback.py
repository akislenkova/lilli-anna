"""Physician feedback and scheduler override pattern routes."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_role
from app.models.appointment import Appointment
from app.schemas.feedback import (
    PhysicianFeedbackCreate,
    PhysicianFeedbackResponse,
    SchedulerOverrideResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _audit_log(
    db: AsyncSession,
    *,
    user_id: Union[str, uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: Union[str, uuid.UUID],
    success: bool,
) -> None:
    await db.execute(
        text(
            "INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, success, created_at) "
            "VALUES (:id, :user_id, :action, :resource_type, :resource_id, :success, now())"
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "success": success,
        },
    )


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------

@router.post("/", response_model=PhysicianFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: PhysicianFeedbackCreate,
    current_user: dict = Depends(require_role(Role.PHYSICIAN)),
    db: AsyncSession = Depends(get_db),
):
    """Submit post-appointment feedback on time-estimate accuracy.

    Only the assigned physician for the appointment can submit feedback.
    This data feeds back into the AI model to improve future duration
    estimates.
    """
    user_id = current_user["user_id"]

    # Verify appointment exists and belongs to this physician
    result = await db.execute(
        select(Appointment).where(Appointment.id == body.appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if str(appointment.physician_id) != str(user_id):
        # Check covering physician access
        covering = await db.execute(
            text(
                "SELECT id FROM physician_coverages "
                "WHERE covering_physician_id = :cov_id "
                "AND absent_physician_id = :abs_id "
                "AND is_active = true "
                "AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE"
            ),
            {"cov_id": str(user_id), "abs_id": str(appointment.physician_id)},
        )
        if covering.first() is None:
            await _audit_log(
                db, user_id=user_id, action="feedback_access_denied",
                resource_type="physician_feedback", resource_id=body.appointment_id, success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the assigned or covering physician can submit feedback",
            )

    if appointment.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback can only be submitted for completed appointments",
        )

    # Check for duplicate feedback
    existing = await db.execute(
        text(
            "SELECT id FROM physician_feedbacks "
            "WHERE appointment_id = :appt_id AND physician_id = :phys_id"
        ),
        {"appt_id": str(body.appointment_id), "phys_id": str(user_id)},
    )
    if existing.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback has already been submitted for this appointment",
        )

    feedback_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            "INSERT INTO physician_feedbacks "
            "(id, appointment_id, physician_id, time_accuracy, actual_vs_suggested_delta, reason_text, created_at) "
            "VALUES (:id, :appt_id, :phys_id, :accuracy, :delta, :reason, :created_at)"
        ),
        {
            "id": str(feedback_id),
            "appt_id": str(body.appointment_id),
            "phys_id": str(user_id),
            "accuracy": body.time_accuracy,
            "delta": body.actual_vs_suggested_delta,
            "reason": body.reason_text,
            "created_at": now.isoformat(),
        },
    )

    # Update actual duration on the appointment if we can compute it
    if appointment.ai_suggested_duration:
        appointment.actual_duration = appointment.ai_suggested_duration + body.actual_vs_suggested_delta

    await db.flush()

    await _audit_log(
        db,
        user_id=user_id,
        action="submit_feedback",
        resource_type="physician_feedback",
        resource_id=feedback_id,
        success=True,
    )

    logger.info(
        "Physician %s submitted feedback for appointment %s: %s (delta=%d min)",
        user_id, body.appointment_id, body.time_accuracy, body.actual_vs_suggested_delta,
    )

    return PhysicianFeedbackResponse(
        id=feedback_id,
        appointment_id=body.appointment_id,
        time_accuracy=body.time_accuracy,
        actual_vs_suggested_delta=body.actual_vs_suggested_delta,
        created_at=now,
    )


# ---------------------------------------------------------------------------
# GET /feedback/appointment/{appointment_id}
# ---------------------------------------------------------------------------

@router.get("/appointment/{appointment_id}", response_model=PhysicianFeedbackResponse)
async def get_feedback(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(require_role(Role.PHYSICIAN, Role.SCHEDULER, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PhysicianFeedbackResponse:
    """Get physician feedback for a specific appointment.

    Accessible by the assigned physician, schedulers, and admins.
    """
    role = current_user["role"]
    user_id = current_user["user_id"]

    # Verify appointment access
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = appt_result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if role == Role.PHYSICIAN.value and str(appointment.physician_id) != str(user_id):
        covering = await db.execute(
            text(
                "SELECT id FROM physician_coverages "
                "WHERE covering_physician_id = :cov_id AND absent_physician_id = :abs_id "
                "AND is_active = true AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE"
            ),
            {"cov_id": str(user_id), "abs_id": str(appointment.physician_id)},
        )
        if covering.first() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        text(
            "SELECT id, appointment_id, time_accuracy, actual_vs_suggested_delta, created_at "
            "FROM physician_feedbacks WHERE appointment_id = :appt_id "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"appt_id": str(appointment_id)},
    )
    feedback = result.mappings().first()

    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No feedback found for this appointment",
        )

    await _audit_log(
        db,
        user_id=user_id,
        action="read_feedback",
        resource_type="physician_feedback",
        resource_id=feedback["id"],
        success=True,
    )

    return PhysicianFeedbackResponse(
        id=feedback["id"],
        appointment_id=feedback["appointment_id"],
        time_accuracy=feedback["time_accuracy"],
        actual_vs_suggested_delta=feedback["actual_vs_suggested_delta"],
        created_at=feedback["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /feedback/override-patterns
# ---------------------------------------------------------------------------

@router.get("/override-patterns", response_model=list[SchedulerOverrideResponse])
async def get_override_patterns(
    scheduler_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[SchedulerOverrideResponse]:
    """Return scheduler override patterns for admin review.

    Implements spec section 6.3: when schedulers consistently override
    AI-suggested durations, this endpoint surfaces those patterns so
    admins can review whether the AI model needs recalibration or the
    scheduler needs guidance.
    """
    params: dict = {"offset": (page - 1) * per_page, "limit": per_page}
    where_clause = ""

    if scheduler_id:
        where_clause = "AND a.scheduler_id = :scheduler_id"
        params["scheduler_id"] = str(scheduler_id)

    result = await db.execute(
        text(
            f"SELECT av.id, a.ai_suggested_duration AS original_duration, "
            f"a.scheduler_approved_duration AS overridden_duration, "
            f"a.scheduler_override_reason AS reason "
            f"FROM appointment_versions av "
            f"JOIN appointments a ON a.id = av.appointment_id "
            f"WHERE a.scheduler_approved_duration IS NOT NULL "
            f"AND a.ai_suggested_duration IS NOT NULL "
            f"AND a.scheduler_approved_duration != a.ai_suggested_duration "
            f"{where_clause} "
            f"ORDER BY av.changed_at DESC "
            f"OFFSET :offset LIMIT :limit"
        ),
        params,
    )
    overrides = result.mappings().all()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_override_patterns",
        resource_type="scheduler_override",
        resource_id=current_user["user_id"],
        success=True,
    )

    return [
        SchedulerOverrideResponse(
            id=o["id"],
            original_duration=o["original_duration"],
            overridden_duration=o["overridden_duration"],
            reason=o["reason"] or "No reason provided",
        )
        for o in overrides
    ]
