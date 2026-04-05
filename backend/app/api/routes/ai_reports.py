"""AI report and red-flag alert routes with role-filtered views."""

from typing import Optional, Union

import logging
import uuid
from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_role
from app.models.appointment import Appointment
from app.schemas.ai_report import (
    AIReportPhysicianView,
    AIReportResponse,
    RedFlagAlertResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["ai_reports"])


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


async def _verify_appointment_access(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    current_user: dict,
) -> Appointment:
    """Load the appointment and verify role-based access."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    role = current_user["role"]
    user_id = current_user["user_id"]

    if role == Role.PATIENT.value:
        # Patients cannot view AI reports (only physician-facing)
        await _audit_log(
            db, user_id=user_id, action="report_access_denied",
            resource_type="ai_report", resource_id=appointment_id, success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients do not have access to AI reports",
        )

    if role == Role.PHYSICIAN.value:
        # Must be assigned physician or covering physician
        if str(appointment.physician_id) != str(user_id):
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
                    db, user_id=user_id, action="report_access_denied",
                    resource_type="ai_report", resource_id=appointment_id, success=False,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not the assigned or covering physician",
                )
            # Log covering physician access
            await _audit_log(
                db, user_id=user_id, action="covering_physician_report_access",
                resource_type="ai_report", resource_id=appointment_id, success=True,
            )

    elif role == Role.NURSE.value:
        # Must be assigned to the physician
        nurse_check = await db.execute(
            text(
                "SELECT id FROM nurse_physician_assignments "
                "WHERE nurse_id = :nurse_id AND physician_id = :phys_id AND is_active = true"
            ),
            {"nurse_id": str(user_id), "phys_id": str(appointment.physician_id)},
        )
        if nurse_check.first() is None:
            await _audit_log(
                db, user_id=user_id, action="report_access_denied",
                resource_type="ai_report", resource_id=appointment_id, success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this physician",
            )

    elif role not in (Role.SCHEDULER.value, Role.ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return appointment


# ---------------------------------------------------------------------------
# GET /reports/{appointment_id}
# ---------------------------------------------------------------------------

@router.get("/{appointment_id}")
async def get_report(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the AI-generated report for an appointment.

    Returns a role-filtered view:
    - Physician: full report with diagnoses, medication interactions, and
      complete transcript analysis.
    - Nurse: summary with red flags and duration estimate (no transcript).
    - Scheduler: duration estimate and confidence only.
    - Admin: full report.
    """
    appointment = await _verify_appointment_access(db, appointment_id, current_user)
    role = current_user["role"]

    # Fetch the report
    report_row = await db.execute(
        text(
            "SELECT id, appointment_id, session_id, status, "
            "suggested_duration, confidence_level, duration_range_min, duration_range_max, "
            "red_flags, complexity_score, summary, full_report, "
            "probable_diagnoses, medication_interactions, created_at "
            "FROM ai_reports WHERE appointment_id = :appt_id "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"appt_id": str(appointment_id)},
    )
    report = report_row.mappings().first()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No AI report found for this appointment",
        )

    if report["status"] == "pending":
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="AI report is still being generated",
        )

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_ai_report",
        resource_type="ai_report",
        resource_id=report["id"],
        success=True,
    )

    # Role-filtered response
    if role in (Role.PHYSICIAN.value, Role.ADMIN.value):
        return {
            "id": report["id"],
            "suggested_duration": report["suggested_duration"],
            "confidence_level": report["confidence_level"],
            "duration_range": (report["duration_range_min"], report["duration_range_max"]),
            "red_flags": report["red_flags"] or [],
            "complexity_score": report["complexity_score"],
            "summary": report["summary"],
            "full_report": report["full_report"],
            "probable_diagnoses": report["probable_diagnoses"] or [],
            "medication_interactions": report["medication_interactions"] or [],
        }

    if role == Role.NURSE.value:
        return {
            "id": report["id"],
            "suggested_duration": report["suggested_duration"],
            "confidence_level": report["confidence_level"],
            "duration_range": (report["duration_range_min"], report["duration_range_max"]),
            "red_flags": report["red_flags"] or [],
            "complexity_score": report["complexity_score"],
            "summary": report["summary"],
        }

    # Scheduler: duration only
    return {
        "id": report["id"],
        "suggested_duration": report["suggested_duration"],
        "confidence_level": report["confidence_level"],
        "duration_range": (report["duration_range_min"], report["duration_range_max"]),
        "complexity_score": report["complexity_score"],
    }


# ---------------------------------------------------------------------------
# GET /reports/{appointment_id}/red-flags
# ---------------------------------------------------------------------------

@router.get("/{appointment_id}/red-flags", response_model=list[RedFlagAlertResponse])
async def get_red_flags(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RedFlagAlertResponse]:
    """Retrieve red-flag alerts for an appointment.

    Accessible by physicians (assigned or covering), nurses (assigned to
    the physician), schedulers, and admins.
    """
    await _verify_appointment_access(db, appointment_id, current_user)

    result = await db.execute(
        text(
            "SELECT id, trigger_description, severity, session_completed, "
            "acknowledged, created_at "
            "FROM red_flag_alerts WHERE appointment_id = :appt_id "
            "ORDER BY created_at DESC"
        ),
        {"appt_id": str(appointment_id)},
    )
    flags = result.mappings().all()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_red_flags",
        resource_type="red_flag_alert",
        resource_id=appointment_id,
        success=True,
    )

    return [
        RedFlagAlertResponse(
            id=f["id"],
            trigger_description=f["trigger_description"],
            severity=f["severity"],
            session_completed=f["session_completed"],
            acknowledged=f["acknowledged"],
            created_at=f["created_at"],
        )
        for f in flags
    ]


# ---------------------------------------------------------------------------
# PUT /reports/{appointment_id}/red-flags/{flag_id}/acknowledge
# ---------------------------------------------------------------------------

@router.put("/{appointment_id}/red-flags/{flag_id}/acknowledge", response_model=RedFlagAlertResponse)
async def acknowledge_red_flag(
    appointment_id: uuid.UUID,
    flag_id: uuid.UUID,
    current_user: dict = Depends(require_role(Role.PHYSICIAN, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RedFlagAlertResponse:
    """Acknowledge a red-flag alert.

    Only physicians (assigned or covering) and admins can acknowledge
    red flags.  This action is audit-logged.
    """
    await _verify_appointment_access(db, appointment_id, current_user)

    # Fetch the flag
    result = await db.execute(
        text(
            "SELECT id, trigger_description, severity, session_completed, "
            "acknowledged, created_at "
            "FROM red_flag_alerts WHERE id = :flag_id AND appointment_id = :appt_id"
        ),
        {"flag_id": str(flag_id), "appt_id": str(appointment_id)},
    )
    flag = result.mappings().first()

    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Red flag alert not found",
        )

    if flag["acknowledged"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Red flag is already acknowledged",
        )

    # Update the flag
    await db.execute(
        text(
            "UPDATE red_flag_alerts SET acknowledged = true, acknowledged_by = :user_id, "
            "acknowledged_at = :now WHERE id = :flag_id"
        ),
        {
            "user_id": str(current_user["user_id"]),
            "now": datetime.now(timezone.utc).isoformat(),
            "flag_id": str(flag_id),
        },
    )

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="acknowledge_red_flag",
        resource_type="red_flag_alert",
        resource_id=flag_id,
        success=True,
    )

    return RedFlagAlertResponse(
        id=flag["id"],
        trigger_description=flag["trigger_description"],
        severity=flag["severity"],
        session_completed=flag["session_completed"],
        acknowledged=True,
        created_at=flag["created_at"],
    )
