"""Appointment management routes with role-based filtering."""

from __future__ import annotations

from typing import Optional, Union

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_role
from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    AppointmentVersion,
    VisitType,
)
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentNurseView,
    AppointmentPhysicianView,
    AppointmentResponse,
    AppointmentSchedulerView,
    AppointmentUpdate,
    AppointmentVersionResponse,
    PriorityRanking,
    RankedPatient,
    SchedulingConflict,
    SuggestedAlternative,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/appointments", tags=["appointments"])


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


async def _verify_physician_access(
    db: AsyncSession, current_user: dict, physician_id: uuid.UUID
) -> bool:
    """Return True if the user is the physician or an active covering physician."""
    user_id = current_user["user_id"]
    if str(physician_id) == str(user_id):
        return True

    result = await db.execute(
        text(
            "SELECT id FROM physician_coverages "
            "WHERE covering_physician_id = :cov_id "
            "AND absent_physician_id = :abs_id "
            "AND is_active = true "
            "AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE"
        ),
        {"cov_id": str(user_id), "abs_id": str(physician_id)},
    )
    return result.first() is not None


async def _get_appointment_or_404(
    db: AsyncSession, appointment_id: uuid.UUID
) -> Appointment:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.patient))
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return appointment


def _role_filtered_view(appointment: Appointment, role: str, patient_name: Optional[str] = None) -> dict:
    """Return the appropriate schema based on the caller's role."""
    if role == Role.PHYSICIAN.value:
        view = AppointmentPhysicianView.model_validate(appointment)
        view.patient_name = patient_name or (
            appointment.patient.full_name if appointment.patient else None
        )
        return view.model_dump()
    if role == Role.NURSE.value:
        return AppointmentNurseView.model_validate(appointment).model_dump()
    if role == Role.SCHEDULER.value:
        return AppointmentSchedulerView.model_validate(appointment).model_dump()
    # Patient and admin get the standard response
    return AppointmentResponse.model_validate(appointment).model_dump()


# ---------------------------------------------------------------------------
# GET /appointments
# ---------------------------------------------------------------------------

@router.get("/")
async def list_appointments(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    physician_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentListResponse:
    """List appointments filtered by the caller's role.

    - Scheduler: sees all appointments.
    - Physician: sees only appointments where they are the assigned or
      covering physician.
    - Nurse: sees appointments for their assigned physician's patients.
    - Patient: sees only their own appointments.
    - Admin: sees all appointments.
    """
    role = current_user["role"]
    user_id = current_user["user_id"]

    stmt = select(Appointment)

    # Role-based base filter
    if role == Role.PATIENT.value:
        stmt = stmt.where(Appointment.patient_id == user_id)

    elif role == Role.PHYSICIAN.value:
        # Own patients, covering patients, and unassigned appointments
        covering_result = await db.execute(
            text(
                "SELECT absent_physician_id FROM physician_coverages "
                "WHERE covering_physician_id = :cov_id AND is_active = true "
                "AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE"
            ),
            {"cov_id": str(user_id)},
        )
        covered_ids = [str(user_id)] + [str(row[0]) for row in covering_result.fetchall()]
        stmt = stmt.where(
            (Appointment.physician_id.in_(covered_ids)) | (Appointment.physician_id.is_(None))
        )

    elif role == Role.NURSE.value:
        pass  # Nurses see all appointments (no assignment table in this version)

    elif role not in (Role.SCHEDULER.value, Role.ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Optional filters
    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)
    if physician_id:
        stmt = stmt.where(Appointment.physician_id == physician_id)
    if date_from:
        stmt = stmt.where(Appointment.scheduled_start >= date_from)
    if date_to:
        stmt = stmt.where(Appointment.scheduled_start <= date_to)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate — put appointments with no scheduled_start first (pending),
    # then order by scheduled_start descending.
    stmt = stmt.order_by(
        Appointment.scheduled_start.is_(None).desc(),
        Appointment.created_at.desc(),
    )
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    appointments = result.scalars().all()

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_access",
            resource_type="appointment",
            resource_id=user_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for list_appointments")

    # Fetch patient names in one query
    patient_ids = list({a.patient_id for a in appointments})
    patient_names: dict[uuid.UUID, str] = {}
    if patient_ids:
        name_result = await db.execute(
            select(User.id, User.full_name).where(User.id.in_(patient_ids))
        )
        patient_names = {row[0]: row[1] for row in name_result.fetchall()}

    items = []
    for a in appointments:
        response = AppointmentResponse.model_validate(a)
        response.patient_name = patient_names.get(a.patient_id)
        items.append(response)

    await db.commit()
    return AppointmentListResponse(items=items, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# GET /appointments/calendar
# ---------------------------------------------------------------------------

@router.get("/calendar")
async def calendar_view(
    view: str = Query("week", pattern="^(today|week|month)$"),
    physician_id: Optional[uuid.UUID] = None,
    reference_date: Optional[date] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return appointments in a calendar-friendly structure.

    Supports today, this-week, and monthly views.  The reference_date
    parameter defaults to today.
    """
    role = current_user["role"]
    user_id = current_user["user_id"]
    ref = reference_date or date.today()

    if view == "today":
        start = datetime.combine(ref, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
    elif view == "week":
        monday = ref - timedelta(days=ref.weekday())
        start = datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=7)
    else:  # month
        start = datetime.combine(ref.replace(day=1), datetime.min.time(), tzinfo=timezone.utc)
        next_month = (ref.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = datetime.combine(next_month, datetime.min.time(), tzinfo=timezone.utc)

    stmt = select(Appointment).where(
        Appointment.scheduled_start >= start,
        Appointment.scheduled_start < end,
    )

    # Role-based filter
    if role == Role.PATIENT.value:
        stmt = stmt.where(Appointment.patient_id == user_id)
    elif role == Role.PHYSICIAN.value:
        target_phys = physician_id or uuid.UUID(user_id)
        if not await _verify_physician_access(db, current_user, target_phys):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        stmt = stmt.where(Appointment.physician_id == target_phys)
    elif role == Role.NURSE.value:
        if physician_id:
            stmt = stmt.where(Appointment.physician_id == physician_id)
    elif role not in (Role.SCHEDULER.value, Role.ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        if physician_id:
            stmt = stmt.where(Appointment.physician_id == physician_id)

    stmt = stmt.order_by(Appointment.scheduled_start)
    result = await db.execute(stmt)
    appointments = result.scalars().all()

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_access",
            resource_type="appointment",
            resource_id=user_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for calendar_view")

    return [_role_filtered_view(a, role) for a in appointments]


# ---------------------------------------------------------------------------
# GET /appointments/available-slots
# ---------------------------------------------------------------------------

@router.get("/available-slots")
async def get_available_slots(
    date: str,  # YYYY-MM-DD
    duration: int = Query(30, ge=5, le=240),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return available appointment slots for a given date.

    Generates 30-minute blocks between 8am–5pm (UTC), excluding times already
    occupied by scheduled appointments.  Any authenticated user can call this.
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    # Only offer future dates
    if target_date <= datetime.utcnow().date():
        return []

    # Clinic hours 8:00–17:00 UTC, timezone-aware so they compare correctly
    day_start = datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=timezone.utc)
    day_end   = datetime(target_date.year, target_date.month, target_date.day, 17, 0, tzinfo=timezone.utc)

    # Fetch already-booked slots for that day
    booked_result = await db.execute(
        select(Appointment.scheduled_start, Appointment.scheduled_end).where(
            Appointment.scheduled_start >= day_start,
            Appointment.scheduled_start < day_end,
            Appointment.status.notin_(["cancelled", "rescheduled"]),
        )
    )
    booked = [(r[0], r[1]) for r in booked_result.fetchall() if r[0]]

    # Generate candidate slots
    slots = []
    slot_start = day_start
    while slot_start + timedelta(minutes=duration) <= day_end:
        slot_end = slot_start + timedelta(minutes=duration)
        overlaps = any(
            b_start < slot_end and (b_end or b_start + timedelta(minutes=30)) > slot_start
            for b_start, b_end in booked
        )
        if not overlaps:
            hour = slot_start.hour % 12 or 12
            minute = slot_start.minute
            ampm = "AM" if slot_start.hour < 12 else "PM"
            label = f"{hour}:{minute:02d} {ampm}"
            slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat(),
                "label": label,
            })
        slot_start += timedelta(minutes=30)

    return slots


# ---------------------------------------------------------------------------
# GET /appointments/conflicts
# ---------------------------------------------------------------------------

@router.get("/conflicts", response_model=list[SchedulingConflict])
async def get_conflicts(
    physician_id: uuid.UUID,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict = Depends(require_role(Role.SCHEDULER, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[SchedulingConflict]:
    """Return scheduling conflicts for a physician's calendar.

    Detects overlapping appointment time slots and suggests alternative
    windows.
    """
    start = date_from or datetime.now(timezone.utc)
    end = date_to or (start + timedelta(days=7))

    result = await db.execute(
        select(Appointment)
        .where(
            Appointment.physician_id == physician_id,
            Appointment.scheduled_start >= start,
            Appointment.scheduled_start <= end,
            Appointment.status.notin_(["cancelled"]),
        )
        .order_by(Appointment.scheduled_start)
    )
    appointments = result.scalars().all()

    conflicts: list[SchedulingConflict] = []
    for i in range(len(appointments)):
        for j in range(i + 1, len(appointments)):
            a, b = appointments[i], appointments[j]
            a_end = a.scheduled_end or (a.scheduled_start + timedelta(minutes=a.ai_suggested_duration or 30))
            if b.scheduled_start < a_end:
                # Suggest an alternative after the last conflicting appointment
                alt_start = a_end + timedelta(minutes=5)
                alt_end = alt_start + timedelta(minutes=b.ai_suggested_duration or 30)
                conflicts.append(
                    SchedulingConflict(
                        conflicting_appointment_id=b.id,
                        physician_id=physician_id,
                        conflict_start=b.scheduled_start,
                        conflict_end=a_end,
                        reason=f"Overlaps with appointment {a.id}",
                        suggested_alternatives=[
                            SuggestedAlternative(
                                physician_id=physician_id,
                                start=alt_start,
                                end=alt_end,
                            )
                        ],
                    )
                )

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_access",
            resource_type="appointment",
            resource_id=str(physician_id),
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for check_conflicts")

    return conflicts


# ---------------------------------------------------------------------------
# GET /appointments/priority-ranking
# ---------------------------------------------------------------------------

@router.get("/priority-ranking", response_model=PriorityRanking)
async def get_priority_ranking(
    physician_id: Optional[uuid.UUID] = None,
    current_user: dict = Depends(require_role(Role.SCHEDULER, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PriorityRanking:
    """Return urgency-based priority ranking of pending appointments for the scheduler.

    Uses AI-generated urgency scores from red flag alerts and conversation
    analysis to rank patients needing scheduling attention.
    """
    stmt = select(Appointment).where(
        Appointment.status.in_(["pending_intake", "intake_complete"]),
    )
    if physician_id:
        stmt = stmt.where(Appointment.physician_id == physician_id)

    result = await db.execute(stmt)
    appointments = result.scalars().all()

    ranked: list[RankedPatient] = []
    for appt in appointments:
        # Check for red flags to boost urgency
        red_flag_result = await db.execute(
            text(
                "SELECT severity FROM red_flag_alerts "
                "WHERE appointment_id = :appt_id AND acknowledged = false"
            ),
            {"appt_id": str(appt.id)},
        )
        red_flags = red_flag_result.fetchall()

        # Calculate urgency score
        base_score = 0.3
        if appt.is_new_patient:
            base_score += 0.1
        for flag in red_flags:
            severity = flag[0]
            if severity == "critical":
                base_score += 0.4
            elif severity == "high":
                base_score += 0.2
            elif severity == "medium":
                base_score += 0.1
            else:
                base_score += 0.05

        urgency = min(base_score, 1.0)

        reason_parts = []
        if appt.is_new_patient:
            reason_parts.append("new patient")
        if red_flags:
            reason_parts.append(f"{len(red_flags)} unacknowledged red flag(s)")
        if not reason_parts:
            reason_parts.append("standard intake")

        ranked.append(
            RankedPatient(
                patient_id=appt.patient_id,
                appointment_id=appt.id,
                urgency_score=urgency,
                reason="; ".join(reason_parts),
            )
        )

    ranked.sort(key=lambda r: r.urgency_score, reverse=True)

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_access",
            resource_type="appointment",
            resource_id=current_user["user_id"],
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for view_priority_ranking")

    return PriorityRanking(patients=ranked)


# ---------------------------------------------------------------------------
# GET /appointments/{appointment_id}
# ---------------------------------------------------------------------------

@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single appointment with role-filtered detail.

    - Patient: sees own appointment only.
    - Physician: full clinical view including transcript and AI report.
    - Nurse: summary view with red flags, no transcript.
    - Scheduler: scheduling-relevant fields only.
    """
    appointment = await _get_appointment_or_404(db, appointment_id)
    role = current_user["role"]
    user_id = current_user["user_id"]

    # Access control
    if role == Role.PATIENT.value:
        if str(appointment.patient_id) != str(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    elif role == Role.PHYSICIAN.value:
        # Allow access to unassigned appointments and own/covered appointments
        if appointment.physician_id is not None and not await _verify_physician_access(db, current_user, appointment.physician_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    elif role not in (Role.NURSE.value, Role.SCHEDULER.value, Role.ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_access",
            resource_type="appointment",
            resource_id=appointment_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for get_appointment")

    return _role_filtered_view(appointment, role)


# ---------------------------------------------------------------------------
# POST /appointments
# ---------------------------------------------------------------------------

@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    current_user: dict = Depends(require_role(Role.SCHEDULER, Role.ADMIN, Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new appointment.

    Patients can create their own appointments (patient_id must match).
    Schedulers and admins can create for any patient.
    """
    role = current_user["role"]
    user_id = current_user["user_id"]

    # Patient can only create for self
    if role == Role.PATIENT.value and str(payload.patient_id) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only create appointments for themselves",
        )

    # Verify patient exists
    patient = await db.execute(select(User).where(User.id == payload.patient_id, User.role == Role.PATIENT))
    if patient.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # Verify physician exists
    physician = await db.execute(select(User).where(User.id == payload.physician_id, User.role == Role.PHYSICIAN))
    if physician.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physician not found")

    # Check for time conflicts
    proposed_end = payload.scheduled_start + timedelta(minutes=30)  # default 30 min
    conflict = await db.execute(
        select(Appointment).where(
            Appointment.physician_id == payload.physician_id,
            Appointment.status.notin_(["cancelled"]),
            Appointment.scheduled_start < proposed_end,
            Appointment.scheduled_end > payload.scheduled_start if Appointment.scheduled_end is not None
            else Appointment.scheduled_start + timedelta(minutes=30) > payload.scheduled_start,
        ).limit(1)
    )
    if conflict.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot conflicts with an existing appointment",
        )

    # Check if this is a new patient for the physician
    existing_appts = await db.execute(
        select(func.count()).where(
            Appointment.patient_id == payload.patient_id,
            Appointment.physician_id == payload.physician_id,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    )
    is_new = (existing_appts.scalar() or 0) == 0

    appointment = Appointment(
        patient_id=payload.patient_id,
        physician_id=payload.physician_id,
        scheduler_id=uuid.UUID(user_id) if role in (Role.SCHEDULER.value, Role.ADMIN.value) else None,
        visit_type=payload.visit_type,
        status=AppointmentStatus.PENDING_INTAKE,
        scheduled_start=payload.scheduled_start,
        scheduled_end=proposed_end,
        is_new_patient=is_new,
    )
    db.add(appointment)
    await db.flush()

    # Create initial version record
    version = AppointmentVersion(
        appointment_id=appointment.id,
        version_number=1,
        changes_json={"action": "created", "visit_type": payload.visit_type},
        changed_by=uuid.UUID(user_id),
    )
    db.add(version)
    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_modify",
            resource_type="appointment",
            resource_id=appointment.id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for create_appointment")

    await db.commit()
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)


# ---------------------------------------------------------------------------
# PUT /appointments/{appointment_id}
# ---------------------------------------------------------------------------

@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an appointment.

    - Scheduler: can approve time, adjust duration, change status.
    - Patient: can reschedule (change scheduled_start).
    - Physician: can update status.
    - Admin: full access.
    """
    appointment = await _get_appointment_or_404(db, appointment_id)
    role = current_user["role"]
    user_id = current_user["user_id"]

    # Access control
    if role == Role.PATIENT.value:
        if str(appointment.patient_id) != str(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        # Patients can only reschedule
        allowed_fields = {"scheduled_start", "scheduled_end"}
        update_data = payload.model_dump(exclude_unset=True)
        if not set(update_data.keys()).issubset(allowed_fields):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients can only update schedule times",
            )
    elif role == Role.PHYSICIAN.value:
        if not await _verify_physician_access(db, current_user, appointment.physician_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif role not in (Role.SCHEDULER.value, Role.ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    update_data = payload.model_dump(exclude_unset=True)
    changes = {}

    for key, value in update_data.items():
        old_value = getattr(appointment, key, None)
        if old_value != value:
            changes[key] = {"old": str(old_value), "new": str(value)}
            setattr(appointment, key, value)

    if changes:
        appointment.version += 1
        version = AppointmentVersion(
            appointment_id=appointment.id,
            version_number=appointment.version,
            changes_json=changes,
            changed_by=uuid.UUID(user_id),
        )
        db.add(version)

    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_modify",
            resource_type="appointment",
            resource_id=appointment_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for update_appointment")

    await db.commit()
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)


# ---------------------------------------------------------------------------
# PUT /appointments/{appointment_id}/cancel
# ---------------------------------------------------------------------------

@router.put("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an appointment.

    Patients can cancel their own. Schedulers and admins can cancel any.
    Physicians can cancel their own patients' appointments.
    """
    appointment = await _get_appointment_or_404(db, appointment_id)
    role = current_user["role"]
    user_id = current_user["user_id"]

    if role == Role.PATIENT.value and str(appointment.patient_id) != str(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif role == Role.PHYSICIAN.value:
        if not await _verify_physician_access(db, current_user, appointment.physician_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif role not in (Role.SCHEDULER.value, Role.ADMIN.value, Role.PATIENT.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is already cancelled",
        )

    if appointment.status == AppointmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed appointment",
        )

    old_status = appointment.status
    appointment.status = AppointmentStatus.CANCELLED
    appointment.version += 1

    version = AppointmentVersion(
        appointment_id=appointment.id,
        version_number=appointment.version,
        changes_json={"status": {"old": old_status.value, "new": "cancelled"}, "cancelled_by": str(user_id)},
        changed_by=uuid.UUID(user_id),
    )
    db.add(version)
    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_modify",
            resource_type="appointment",
            resource_id=appointment_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for cancel_appointment")

    await db.commit()
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)


# ---------------------------------------------------------------------------
# GET /appointments/{appointment_id}/versions
# ---------------------------------------------------------------------------

@router.get("/{appointment_id}/versions", response_model=list[AppointmentVersionResponse])
async def get_versions(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentVersionResponse]:
    """Retrieve the full version history of an appointment.

    Accessible by the patient (own appointment), assigned physician,
    scheduler, and admin.
    """
    appointment = await _get_appointment_or_404(db, appointment_id)
    role = current_user["role"]
    user_id = current_user["user_id"]

    # Access control
    if role == Role.PATIENT.value and str(appointment.patient_id) != str(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif role == Role.PHYSICIAN.value:
        if not await _verify_physician_access(db, current_user, appointment.physician_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif role not in (Role.SCHEDULER.value, Role.ADMIN.value, Role.PATIENT.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(AppointmentVersion)
        .where(AppointmentVersion.appointment_id == appointment_id)
        .order_by(AppointmentVersion.version_number)
    )
    versions = result.scalars().all()

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_access",
            resource_type="appointment",
            resource_id=appointment_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for get_versions")

    return [
        AppointmentVersionResponse(
            version_number=v.version_number,
            changes=v.changes_json or {},
            changed_by=v.changed_by,
            changed_at=v.changed_at,
        )
        for v in versions
    ]
