"""Demo reset endpoint — clears transient appointment data for the demo patient.

Only active when ENVIRONMENT != 'production'. Safe to call any number of times;
user accounts and profiles are preserved so login still works immediately after.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_non_production() -> None:
    """Raise 404 when called from a production deployment."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_demo_data(
    _: None = Depends(_require_non_production),
    db: AsyncSession = Depends(get_db),
):
    """Delete all transient demo data (appointments, sessions, red flags, messages).

    User accounts and patient profiles are left intact so demo logins keep
    working immediately after the reset. Scoped to the demo patient email only.
    """

    # Resolve demo patient ID
    result = await db.execute(
        select(User.id).where(User.email == "patient@demo.com")
    )
    patient_id = result.scalar_one_or_none()
    if patient_id is None:
        return {"deleted": 0, "message": "Demo patient not found — nothing to reset."}

    # Delete in dependency order so FK constraints don't fire.
    # red_flag_alerts and conversation_messages cascade off appointments /
    # conversation_sessions which are tied to the patient.
    deleted = {}

    r = await db.execute(
        text("DELETE FROM red_flag_alerts WHERE patient_id = :pid"),
        {"pid": str(patient_id)},
    )
    deleted["red_flag_alerts"] = r.rowcount

    r = await db.execute(
        text(
            "DELETE FROM conversation_messages WHERE session_id IN "
            "(SELECT id FROM conversation_sessions WHERE patient_id = :pid)"
        ),
        {"pid": str(patient_id)},
    )
    deleted["conversation_messages"] = r.rowcount

    r = await db.execute(
        text("DELETE FROM conversation_sessions WHERE patient_id = :pid"),
        {"pid": str(patient_id)},
    )
    deleted["conversation_sessions"] = r.rowcount

    r = await db.execute(
        text("DELETE FROM ai_reports WHERE appointment_id IN "
             "(SELECT id FROM appointments WHERE patient_id = :pid)"),
        {"pid": str(patient_id)},
    )
    deleted["ai_reports"] = r.rowcount

    r = await db.execute(
        text("DELETE FROM appointments WHERE patient_id = :pid"),
        {"pid": str(patient_id)},
    )
    deleted["appointments"] = r.rowcount

    await db.commit()

    total = sum(deleted.values())
    return {
        "message": f"Demo data cleared ({total} rows deleted).",
        "deleted": deleted,
    }


@router.post("/dismiss-flags", status_code=status.HTTP_200_OK)
async def dismiss_all_flags(
    _: None = Depends(_require_non_production),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge all unacknowledged red flag alerts for the demo patient.

    Use this to clean up duplicate flags from repeated demo runs without
    deleting appointment or session data.
    """
    result = await db.execute(
        select(User.id).where(User.email == "patient@demo.com")
    )
    patient_id = result.scalar_one_or_none()
    if patient_id is None:
        return {"dismissed": 0, "message": "Demo patient not found."}

    now = datetime.now(timezone.utc).isoformat()
    r = await db.execute(
        text(
            "UPDATE red_flag_alerts SET acknowledged_at = :now "
            "WHERE patient_id = :pid AND acknowledged_at IS NULL"
        ),
        {"now": now, "pid": str(patient_id)},
    )
    await db.commit()
    return {"dismissed": r.rowcount, "message": f"{r.rowcount} flag(s) dismissed."}
