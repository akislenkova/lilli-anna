"""Appointment lifecycle service.

Handles creation, updates, cancellation, scheduling conflicts, priority
ranking, and duration approval (with scheduler-override logging).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import Role
from app.models.ai_report import AIReport, RedFlagAlert
from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    AppointmentVersion,
    VisitType,
)
from app.models.feedback import SchedulerOverride
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class AppointmentService:
    """Full appointment lifecycle management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)
        self._notifications = NotificationService(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_appointment(
        self,
        data: dict,
        patient_id: uuid.UUID,
        physician_id: uuid.UUID,
    ) -> Appointment:
        """Create a new appointment and log an audit entry."""
        visit_type_str = data.get("visit_type", "specific_concern")
        try:
            visit_type = VisitType(visit_type_str)
        except ValueError:
            visit_type = VisitType.SPECIFIC_CONCERN

        appointment = Appointment(
            patient_id=patient_id,
            physician_id=physician_id,
            visit_type=visit_type,
            status=AppointmentStatus.PENDING_INTAKE,
            scheduled_start=data.get("scheduled_start"),
            scheduled_end=data.get("scheduled_end"),
            is_new_patient=data.get("is_new_patient", False),
            version=1,
        )
        self._db.add(appointment)
        await self._db.flush()

        # Create initial version record
        version = AppointmentVersion(
            appointment_id=appointment.id,
            version_number=1,
            changes_json={"action": "created", "visit_type": visit_type_str},
            changed_by=patient_id,
        )
        self._db.add(version)
        await self._db.flush()

        logger.info("appointment created | id=%s patient=%s physician=%s", appointment.id, patient_id, physician_id)
        return appointment

    # ------------------------------------------------------------------
    # Update (versioned)
    # ------------------------------------------------------------------

    async def update_appointment(
        self,
        appointment_id: uuid.UUID,
        data: dict,
        user_id: uuid.UUID,
        user_role: str,
    ) -> Appointment:
        """Apply a partial update and create a version record."""
        appointment = await self._get_appointment_or_raise(appointment_id)
        self._check_write_permission(appointment, user_id, user_role)

        changes: dict = {}
        updatable_fields = [
            "status",
            "scheduled_start",
            "scheduled_end",
            "scheduler_approved_duration",
            "scheduler_override_reason",
        ]
        for field in updatable_fields:
            if field in data and data[field] is not None:
                old_val = getattr(appointment, field)
                new_val = data[field]
                if field == "status":
                    try:
                        new_val = AppointmentStatus(new_val)
                    except ValueError:
                        raise ValueError(f"Invalid status: {new_val}")
                setattr(appointment, field, new_val)
                changes[field] = {"old": str(old_val), "new": str(new_val)}

        if not changes:
            return appointment

        appointment.version += 1
        version = AppointmentVersion(
            appointment_id=appointment.id,
            version_number=appointment.version,
            changes_json=changes,
            changed_by=user_id,
        )
        self._db.add(version)
        await self._db.flush()

        await self._audit.log_modification(
            user_id=user_id,
            resource_type="appointment",
            resource_id=appointment.id,
            changes=changes,
            ip_address="",
        )

        logger.info("appointment updated | id=%s version=%d by=%s", appointment.id, appointment.version, user_id)
        return appointment

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def cancel_appointment(
        self,
        appointment_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
    ) -> Appointment:
        """Cancel an appointment and notify all parties."""
        appointment = await self._get_appointment_or_raise(appointment_id)

        old_status = appointment.status
        appointment.status = AppointmentStatus.CANCELLED
        appointment.version += 1

        version = AppointmentVersion(
            appointment_id=appointment.id,
            version_number=appointment.version,
            changes_json={
                "action": "cancelled",
                "reason": reason,
                "old_status": old_status.value,
            },
            changed_by=user_id,
        )
        self._db.add(version)
        await self._db.flush()

        await self._notifications.send_cancellation_notification(appointment)

        logger.info("appointment cancelled | id=%s by=%s reason=%s", appointment.id, user_id, reason)
        return appointment

    # ------------------------------------------------------------------
    # Read (role-filtered)
    # ------------------------------------------------------------------

    async def get_appointment(
        self,
        appointment_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
    ) -> dict:
        """Return role-appropriate appointment data."""
        appointment = await self._get_appointment_or_raise(appointment_id)
        return self._to_role_view(appointment, user_id, user_role)

    async def list_appointments(
        self,
        user_id: uuid.UUID,
        user_role: str,
        filters: dict | None = None,
    ) -> list[dict]:
        """Return filtered appointment list scoped to the caller's role."""
        filters = filters or {}
        stmt = select(Appointment)

        # Scope by role
        if user_role == Role.PATIENT.value:
            stmt = stmt.where(Appointment.patient_id == user_id)
        elif user_role == Role.PHYSICIAN.value:
            stmt = stmt.where(Appointment.physician_id == user_id)
        # scheduler / admin / nurse see all (filtered below)

        if "status" in filters:
            try:
                stmt = stmt.where(Appointment.status == AppointmentStatus(filters["status"]))
            except ValueError:
                pass
        if "patient_id" in filters and user_role != Role.PATIENT.value:
            stmt = stmt.where(Appointment.patient_id == filters["patient_id"])
        if "physician_id" in filters:
            stmt = stmt.where(Appointment.physician_id == filters["physician_id"])
        if "date_from" in filters:
            stmt = stmt.where(Appointment.scheduled_start >= filters["date_from"])
        if "date_to" in filters:
            stmt = stmt.where(Appointment.scheduled_start <= filters["date_to"])

        stmt = stmt.order_by(Appointment.scheduled_start.desc())

        if "limit" in filters:
            stmt = stmt.limit(min(int(filters["limit"]), 200))
        else:
            stmt = stmt.limit(50)

        if "offset" in filters:
            stmt = stmt.offset(int(filters["offset"]))

        result = await self._db.execute(stmt)
        appointments = list(result.scalars().all())
        return [self._to_role_view(a, user_id, user_role) for a in appointments]

    # ------------------------------------------------------------------
    # Calendar view
    # ------------------------------------------------------------------

    async def get_calendar(
        self,
        user_id: uuid.UUID,
        user_role: str,
        view_type: str = "week",
    ) -> list[dict]:
        """Return calendar data for the requested view (day/week/month)."""
        now = datetime.now(timezone.utc)
        if view_type == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif view_type == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (start.month % 12) + 1
            year = start.year + (1 if next_month == 1 else 0)
            end = start.replace(year=year, month=next_month)
        else:  # week (default)
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(weeks=1)

        stmt = select(Appointment).where(
            Appointment.scheduled_start >= start,
            Appointment.scheduled_start < end,
            Appointment.status != AppointmentStatus.CANCELLED,
        )

        if user_role == Role.PATIENT.value:
            stmt = stmt.where(Appointment.patient_id == user_id)
        elif user_role == Role.PHYSICIAN.value:
            stmt = stmt.where(Appointment.physician_id == user_id)

        stmt = stmt.order_by(Appointment.scheduled_start)
        result = await self._db.execute(stmt)
        appointments = list(result.scalars().all())
        return [self._to_role_view(a, user_id, user_role) for a in appointments]

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    async def check_conflicts(
        self,
        physician_id: uuid.UUID,
        duration: int,
        date_range: tuple[datetime, datetime],
    ) -> list[dict]:
        """Check for scheduling conflicts and suggest alternatives.

        If the AI suggests 45 min but only 20-min slots are available,
        the conflict is flagged with a split-visit suggestion.
        """
        start, end = date_range
        stmt = select(Appointment).where(
            Appointment.physician_id == physician_id,
            Appointment.status.not_in(
                [AppointmentStatus.CANCELLED, AppointmentStatus.RESCHEDULED]
            ),
            Appointment.scheduled_start < end,
            Appointment.scheduled_end > start,
        ).order_by(Appointment.scheduled_start)

        result = await self._db.execute(stmt)
        existing = list(result.scalars().all())

        conflicts: list[dict] = []
        for appt in existing:
            conflict: dict = {
                "conflicting_appointment_id": str(appt.id),
                "physician_id": str(physician_id),
                "conflict_start": appt.scheduled_start.isoformat() if appt.scheduled_start else None,
                "conflict_end": appt.scheduled_end.isoformat() if appt.scheduled_end else None,
                "reason": "Time slot overlap",
                "suggested_alternatives": [],
            }

            # Check if the available gap is too small for the requested duration
            if appt.scheduled_end:
                gap_before_next = None
                # Find gap after this appointment
                gap_start = appt.scheduled_end
                gap_end = end  # default to end of range
                gap_minutes = int((gap_end - gap_start).total_seconds() / 60)

                if gap_minutes > 0 and gap_minutes < duration:
                    conflict["reason"] = (
                        f"AI suggests {duration} min but only {gap_minutes}-min "
                        f"slot available. Consider split-visit or alternative time."
                    )
                    conflict["split_visit_option"] = {
                        "available_slot_minutes": gap_minutes,
                        "remaining_minutes": duration - gap_minutes,
                        "recommendation": "Split visit across two shorter appointments",
                    }

                if gap_minutes >= duration:
                    conflict["suggested_alternatives"].append(
                        {
                            "physician_id": str(physician_id),
                            "start": gap_start.isoformat(),
                            "end": (gap_start + timedelta(minutes=duration)).isoformat(),
                        }
                    )

            conflicts.append(conflict)

        return conflicts

    # ------------------------------------------------------------------
    # Priority ranking
    # ------------------------------------------------------------------

    async def get_priority_ranking(
        self,
        target_date: date,
        physician_id: uuid.UUID,
    ) -> list[dict]:
        """Rank patients by urgency for a given date and physician.

        Scoring factors:
        - Red-flag status (highest weight)
        - Symptom severity / complexity score
        - Time since last visit
        """
        day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        stmt = (
            select(Appointment)
            .where(
                Appointment.physician_id == physician_id,
                Appointment.scheduled_start >= day_start,
                Appointment.scheduled_start < day_end,
                Appointment.status.not_in([AppointmentStatus.CANCELLED]),
            )
            .order_by(Appointment.scheduled_start)
        )

        result = await self._db.execute(stmt)
        appointments = list(result.scalars().all())

        ranked: list[dict] = []
        for appt in appointments:
            score = 0.0
            reasons: list[str] = []

            # Check red flags
            flag_stmt = select(func.count()).select_from(RedFlagAlert).where(
                RedFlagAlert.appointment_id == appt.id,
                RedFlagAlert.acknowledged_at.is_(None),
            )
            flag_result = await self._db.execute(flag_stmt)
            flag_count = flag_result.scalar() or 0

            if flag_count > 0:
                score += 0.5
                reasons.append(f"{flag_count} unacknowledged red-flag alert(s)")

            # Check AI report complexity
            report_stmt = (
                select(AIReport)
                .where(AIReport.appointment_id == appt.id)
                .order_by(AIReport.created_at.desc())
                .limit(1)
            )
            report_result = await self._db.execute(report_stmt)
            report = report_result.scalar_one_or_none()

            if report and report.complexity_score:
                score += report.complexity_score * 0.3
                reasons.append(f"complexity score: {report.complexity_score:.2f}")

            # New patient bonus
            if appt.is_new_patient:
                score += 0.1
                reasons.append("new patient")

            # Clamp to [0, 1]
            score = min(score, 1.0)

            ranked.append(
                {
                    "patient_id": str(appt.patient_id),
                    "appointment_id": str(appt.id),
                    "urgency_score": round(score, 3),
                    "reason": "; ".join(reasons) if reasons else "standard priority",
                }
            )

        ranked.sort(key=lambda r: r["urgency_score"], reverse=True)
        return ranked

    # ------------------------------------------------------------------
    # Duration approval / scheduler override
    # ------------------------------------------------------------------

    async def approve_duration(
        self,
        appointment_id: uuid.UUID,
        scheduler_id: uuid.UUID,
        approved_duration: int,
        override_reason: str | None = None,
    ) -> Appointment:
        """Approve (or override) the AI-suggested appointment duration.

        If the approved duration differs from the AI suggestion, a
        ``SchedulerOverride`` record is created for feedback analysis.
        """
        appointment = await self._get_appointment_or_raise(appointment_id)

        appointment.scheduler_approved_duration = approved_duration
        appointment.scheduler_id = scheduler_id

        is_override = (
            appointment.ai_suggested_duration is not None
            and approved_duration != appointment.ai_suggested_duration
        )

        if is_override:
            appointment.scheduler_override_reason = override_reason
            override = SchedulerOverride(
                appointment_id=appointment.id,
                scheduler_id=scheduler_id,
                original_ai_duration=appointment.ai_suggested_duration,
                overridden_duration=approved_duration,
                reason=override_reason,
            )
            self._db.add(override)
            logger.info(
                "scheduler override | appointment=%s ai=%d approved=%d reason=%s",
                appointment.id,
                appointment.ai_suggested_duration,
                approved_duration,
                override_reason,
            )

        # Set scheduled_end based on approved duration
        if appointment.scheduled_start:
            appointment.scheduled_end = appointment.scheduled_start + timedelta(
                minutes=approved_duration
            )

        appointment.version += 1
        version = AppointmentVersion(
            appointment_id=appointment.id,
            version_number=appointment.version,
            changes_json={
                "action": "duration_approved",
                "approved_duration": approved_duration,
                "is_override": is_override,
                "override_reason": override_reason,
            },
            changed_by=scheduler_id,
        )
        self._db.add(version)
        await self._db.flush()

        return appointment

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_appointment_or_raise(self, appointment_id: uuid.UUID) -> Appointment:
        appointment = await self._db.get(Appointment, appointment_id)
        if appointment is None:
            raise ValueError(f"Appointment {appointment_id} not found")
        return appointment

    @staticmethod
    def _check_write_permission(
        appointment: Appointment, user_id: uuid.UUID, user_role: str
    ) -> None:
        allowed_roles = {Role.SCHEDULER.value, Role.ADMIN.value, Role.NURSE.value}
        if user_role in allowed_roles:
            return
        if user_role == Role.PHYSICIAN.value and appointment.physician_id == user_id:
            return
        if user_role == Role.PATIENT.value and appointment.patient_id == user_id:
            return
        raise PermissionError("Insufficient permissions to update this appointment")

    @staticmethod
    def _to_role_view(
        appointment: Appointment, user_id: uuid.UUID, user_role: str
    ) -> dict:
        """Build a role-appropriate dict representation."""
        base = {
            "id": str(appointment.id),
            "patient_id": str(appointment.patient_id),
            "physician_id": str(appointment.physician_id),
            "visit_type": appointment.visit_type.value,
            "status": appointment.status.value,
            "scheduled_start": (
                appointment.scheduled_start.isoformat()
                if appointment.scheduled_start
                else None
            ),
            "scheduled_end": (
                appointment.scheduled_end.isoformat()
                if appointment.scheduled_end
                else None
            ),
            "ai_suggested_duration": appointment.ai_suggested_duration,
        }

        if user_role in (Role.PHYSICIAN.value, Role.ADMIN.value):
            base["scheduler_approved_duration"] = appointment.scheduler_approved_duration
            base["scheduler_override_reason"] = appointment.scheduler_override_reason
            base["actual_duration"] = appointment.actual_duration
            base["version"] = appointment.version

        elif user_role == Role.NURSE.value:
            base["scheduler_approved_duration"] = appointment.scheduler_approved_duration

        elif user_role == Role.SCHEDULER.value:
            base["scheduler_approved_duration"] = appointment.scheduler_approved_duration
            base["scheduler_override_reason"] = appointment.scheduler_override_reason
            base["is_new_patient"] = appointment.is_new_patient

        # Patient sees only the base fields

        return base
