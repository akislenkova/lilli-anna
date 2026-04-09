"""Patient-facing routes: profile, appointments, medications, records."""

from __future__ import annotations

from typing import Optional, Union

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    Role,
    decrypt_phi,
    encrypt_phi,
    get_current_user,
    require_role,
)
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import PatientProfile
from app.models.user import User
from app.schemas.appointment import AppointmentResponse
from app.schemas.patient import (
    MedicationListResponse,
    PatientProfileResponse,
    PatientProfileUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patients/me", tags=["patients"])


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
    """Write an audit log entry."""
    await db.execute(
        __import__("sqlalchemy").text(
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


async def _get_patient_profile(
    db: AsyncSession, user_id: str
) -> PatientProfile:
    """Fetch the patient profile or raise 404."""
    result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )
    return profile


async def _verify_patient_or_proxy(
    db: AsyncSession, current_user: dict, target_patient_id: Optional[str] = None,
) -> str:
    """Return the effective patient_id after verifying access.

    A patient accesses their own data directly.  A proxy user must have an
    active, verified proxy authorization for the target patient.
    """
    user_role = current_user["role"]
    user_id = current_user["user_id"]

    if user_role == Role.PATIENT.value:
        return user_id

    # Check proxy authorization
    if target_patient_id:
        row = await db.execute(
            __import__("sqlalchemy").text(
                "SELECT id FROM proxy_authorizations "
                "WHERE proxy_user_id = :proxy_id AND patient_id = :patient_id "
                "AND verified = true AND is_active = true"
            ),
            {"proxy_id": str(user_id), "patient_id": str(target_patient_id)},
        )
        if row.first() is not None:
            return target_patient_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: not the patient or an authorized proxy",
    )


# ---------------------------------------------------------------------------
# GET /patients/me/profile
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=PatientProfileResponse)
async def get_own_profile(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the authenticated patient's profile.

    Returns the basic profile without encrypted PHI fields; those are
    available through dedicated endpoints with additional access controls.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)
    profile = await _get_patient_profile(db, patient_id)

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_own_profile",
        resource_type="patient_profile",
        resource_id=profile.id,
        success=True,
    )
    await db.commit()

    return PatientProfileResponse.model_validate(profile)


# ---------------------------------------------------------------------------
# PUT /patients/me/profile
# ---------------------------------------------------------------------------

@router.put("/profile", response_model=PatientProfileResponse)
async def update_own_profile(
    body: PatientProfileUpdate,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated patient's profile fields.

    Only the fields provided in the request body are updated.  Encrypted
    fields (emergency_contact, insurance_info) are re-encrypted before
    storage.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)
    profile = await _get_patient_profile(db, patient_id)

    update_data = body.model_dump(exclude_unset=True)

    # Encrypt PHI fields if present
    phi_fields = {"emergency_contact", "insurance_info"}
    for field in phi_fields:
        if field in update_data and update_data[field] is not None:
            update_data[field] = encrypt_phi(update_data[field])

    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.flush()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="update_own_profile",
        resource_type="patient_profile",
        resource_id=profile.id,
        success=True,
    )
    await db.commit()
    await db.refresh(profile)

    return PatientProfileResponse.model_validate(profile)


# ---------------------------------------------------------------------------
# GET /patients/me/appointments
# ---------------------------------------------------------------------------

@router.get("/appointments", response_model=list[AppointmentResponse])
async def list_own_appointments(
    include_past: bool = True,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """List all appointments for the authenticated patient.

    By default returns both past and upcoming appointments.  Set
    ``include_past=false`` to show only upcoming/active appointments.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)

    stmt = select(Appointment).where(Appointment.patient_id == patient_id)
    if not include_past:
        stmt = stmt.where(
            Appointment.status.notin_([
                AppointmentStatus.COMPLETED,
                AppointmentStatus.CANCELLED,
            ])
        )
    stmt = stmt.order_by(Appointment.scheduled_start.desc())

    result = await db.execute(stmt)
    appointments = result.scalars().all()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="list_own_appointments",
        resource_type="appointment",
        resource_id=patient_id,
        success=True,
    )
    await db.commit()

    return [AppointmentResponse.model_validate(a) for a in appointments]


# ---------------------------------------------------------------------------
# GET /patients/me/appointments/{appointment_id}
# ---------------------------------------------------------------------------

@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_own_appointment(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific appointment with an overview for the patient.

    Returns the appointment only if it belongs to the authenticated patient.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)

    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="read_appointment_denied",
            resource_type="appointment",
            resource_id=appointment_id,
            success=False,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_own_appointment",
        resource_type="appointment",
        resource_id=appointment_id,
        success=True,
    )
    await db.commit()

    return AppointmentResponse.model_validate(appointment)


# ---------------------------------------------------------------------------
# GET /patients/me/records
# ---------------------------------------------------------------------------

@router.get("/records", response_model=list[AppointmentResponse])
async def get_own_records(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve past scheduling records for the authenticated patient.

    Returns only completed or cancelled appointments, ordered by date
    descending.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)

    result = await db.execute(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status.in_([
                AppointmentStatus.COMPLETED,
                AppointmentStatus.CANCELLED,
            ]),
        )
        .order_by(Appointment.scheduled_start.desc())
    )
    records = result.scalars().all()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_own_records",
        resource_type="appointment",
        resource_id=patient_id,
        success=True,
    )
    await db.commit()

    return [AppointmentResponse.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# GET /patients/me/medications
# ---------------------------------------------------------------------------

@router.get("/medications", response_model=MedicationListResponse)
async def get_own_medications(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the authenticated patient's current medication list.

    The medication data is stored encrypted; it is decrypted before returning.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)
    profile = await _get_patient_profile(db, patient_id)

    medications: list[str] = []
    if profile.current_medications:
        try:
            decrypted = decrypt_phi(profile.current_medications)
            medications = json.loads(decrypted)
        except Exception:
            logger.exception("Failed to decrypt medications for patient %s", patient_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to retrieve medication data",
            )

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_own_medications",
        resource_type="patient_profile",
        resource_id=profile.id,
        success=True,
    )
    await db.commit()

    return MedicationListResponse(medications=medications)


# ---------------------------------------------------------------------------
# POST /patients/me/medications
# ---------------------------------------------------------------------------

@router.post("/medications", response_model=MedicationListResponse)
async def update_own_medications(
    body: MedicationListResponse,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated patient's medication list.

    Accepts a full replacement list of medication names.  The list is
    encrypted before storage.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)
    profile = await _get_patient_profile(db, patient_id)

    encrypted = encrypt_phi(json.dumps(body.medications))
    profile.current_medications = encrypted
    await db.flush()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="update_own_medications",
        resource_type="patient_profile",
        resource_id=profile.id,
        success=True,
    )
    await db.commit()
    await db.refresh(profile)

    return body


# ---------------------------------------------------------------------------
# GET /patients/me/epic-launch  — patient sees their own MyChart record
# ---------------------------------------------------------------------------

@router.get("/epic-launch")
async def get_epic_launch_url_patient(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Return the Epic MyChart URL for the authenticated patient.

    Opens the patient's own MyChart record in a new browser tab.  The URL
    is constructed from EPIC_MYCHART_BASE_URL so the clinic can point it at
    their own Epic instance via the environment variable.
    """
    patient_id = await _verify_patient_or_proxy(db, current_user)
    profile = await _get_patient_profile(db, patient_id)

    # Build the MyChart deep-link.  If the patient has an MRN we include it
    # as a hint; Epic will still require the patient to authenticate.
    result = await db.execute(
        select(User.medical_record_number).where(User.id == patient_id)
    )
    row = result.first()
    mrn: str | None = row[0] if row else None

    base = settings.EPIC_MYCHART_BASE_URL.rstrip("/")
    url = f"{base}/Authentication/Login"
    if mrn:
        url = f"{base}/chart/opennote?MRN={mrn}"

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="epic_launch_patient",
        resource_type="patient_profile",
        resource_id=profile.id,
        success=True,
    )
    await db.commit()

    return {"url": url, "available": bool(settings.EPIC_FHIR_BASE_URL)}


# ---------------------------------------------------------------------------
# GET /patients/{patient_id}/epic-launch  — physician opens chart in Epic
# ---------------------------------------------------------------------------

_physician_router = APIRouter(prefix="/patients", tags=["patients"])


@_physician_router.get("/{patient_id}/epic-launch")
async def get_epic_launch_url_physician(
    patient_id: uuid.UUID,
    current_user: dict = Depends(require_role(Role.PHYSICIAN)),
    db: AsyncSession = Depends(get_db),
):
    """Return the Epic FHIR launch URL so a physician can open the patient
    chart inside Epic.

    Uses the SMART on FHIR standalone-launch pattern.  Requires
    EPIC_FHIR_BASE_URL and EPIC_CLIENT_ID to be configured; returns
    ``available: false`` when they are absent (e.g. local dev without Epic).
    """
    if not settings.EPIC_CLIENT_ID:
        # No Epic credentials configured — tell the frontend to show a
        # "not configured" state instead of an unusable URL.
        return {"url": None, "available": False}

    result = await db.execute(
        select(User.medical_record_number).where(User.id == patient_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    mrn: str | None = row[0]
    base = settings.EPIC_FHIR_BASE_URL.rstrip("/")
    fhir_r4 = f"{base}/api/FHIR/R4"

    # SMART on FHIR standalone launch
    from urllib.parse import urlencode
    params = urlencode({
        "response_type": "code",
        "client_id": settings.EPIC_CLIENT_ID,
        "redirect_uri": f"{settings.FRONTEND_URL}/epic-callback",
        "scope": "openid fhirUser launch/patient patient/*.read",
        "iss": fhir_r4,
        **({"login_hint": mrn} if mrn else {}),
    })
    url = f"{base}/oauth2/authorize?{params}"

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="epic_launch_physician",
        resource_type="patient",
        resource_id=patient_id,
        success=True,
    )
    await db.commit()

    return {"url": url, "available": True}
