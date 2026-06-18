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


async def _delete_patient_transient_data(
    db: AsyncSession, patient_id: str
) -> dict[str, int]:
    """Delete all transient data for one patient and return row counts."""
    deleted: dict[str, int] = {}

    r = await db.execute(
        text("DELETE FROM red_flag_alerts WHERE patient_id = :pid"),
        {"pid": patient_id},
    )
    deleted["red_flag_alerts"] = r.rowcount

    r = await db.execute(
        text(
            "DELETE FROM conversation_messages WHERE session_id IN "
            "(SELECT id FROM conversation_sessions WHERE patient_id = :pid)"
        ),
        {"pid": patient_id},
    )
    deleted["conversation_messages"] = r.rowcount

    r = await db.execute(
        text("DELETE FROM conversation_sessions WHERE patient_id = :pid"),
        {"pid": patient_id},
    )
    deleted["conversation_sessions"] = r.rowcount

    r = await db.execute(
        text(
            "DELETE FROM ai_reports WHERE appointment_id IN "
            "(SELECT id FROM appointments WHERE patient_id = :pid)"
        ),
        {"pid": patient_id},
    )
    deleted["ai_reports"] = r.rowcount

    r = await db.execute(
        text("DELETE FROM appointments WHERE patient_id = :pid"),
        {"pid": patient_id},
    )
    deleted["appointments"] = r.rowcount

    return deleted


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_demo_data(
    _: None = Depends(_require_non_production),
    db: AsyncSession = Depends(get_db),
):
    """Delete all transient demo data (appointments, sessions, red flags, messages).

    User accounts and patient profiles are left intact so demo logins keep
    working immediately after the reset. Covers all demo patient accounts.
    """
    demo_emails = ["patient@demo.com", "patient2@demo.com"]
    totals: dict[str, int] = {}

    for email in demo_emails:
        result = await db.execute(select(User.id).where(User.email == email))
        patient_id = result.scalar_one_or_none()
        if patient_id is None:
            continue
        counts = await _delete_patient_transient_data(db, str(patient_id))
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v

    await db.commit()

    if not totals:
        return {"deleted": 0, "message": "No demo patients found — nothing to reset."}

    total = sum(totals.values())
    return {
        "message": f"Demo data cleared ({total} rows deleted).",
        "deleted": totals,
    }


@router.post("/dismiss-flags", status_code=status.HTTP_200_OK)
async def dismiss_all_flags(
    _: None = Depends(_require_non_production),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge all unacknowledged red flag alerts for all demo patients.

    Use this to clean up duplicate flags from repeated demo runs without
    deleting appointment or session data.
    """
    demo_emails = ["patient@demo.com", "patient2@demo.com"]
    total_dismissed = 0
    now = datetime.now(timezone.utc).isoformat()

    for email in demo_emails:
        result = await db.execute(select(User.id).where(User.email == email))
        patient_id = result.scalar_one_or_none()
        if patient_id is None:
            continue
        r = await db.execute(
            text(
                "UPDATE red_flag_alerts SET acknowledged_at = :now "
                "WHERE patient_id = :pid AND acknowledged_at IS NULL"
            ),
            {"now": now, "pid": str(patient_id)},
        )
        total_dismissed += r.rowcount

    await db.commit()
    return {"dismissed": total_dismissed, "message": f"{total_dismissed} flag(s) dismissed."}
