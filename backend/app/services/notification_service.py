"""HIPAA-compliant notification service (stub implementation).

In production this would integrate with the EHR messaging system (e.g. Epic
MyChart secure messaging) or a HIPAA-compliant SMS/email gateway.  This stub
logs every notification to the console and records it in the audit trail.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.ai_report import RedFlagAlert
    from app.models.appointment import Appointment
    from app.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Stub notification service backed by console logging + audit trail."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _audit_notification(
        self,
        action: str,
        user_id: uuid.UUID | None,
        patient_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        details: dict | None = None,
    ) -> None:
        """Persist a notification event in the audit log."""
        from app.services.audit_service import AuditService

        audit = AuditService(self._db)
        await audit.log_access(
            user_id=user_id or uuid.UUID(int=0),
            patient_id=patient_id or uuid.UUID(int=0),
            resource_type=resource_type or "notification",
            resource_id=resource_id or uuid.uuid4(),
            action=action,
            success=True,
            details=details,
        )

    # ------------------------------------------------------------------
    # Red-flag alerts
    # ------------------------------------------------------------------

    async def send_red_flag_alert(
        self,
        alert: "RedFlagAlert",
        patient: "User",
        physician: "User",
        nurse: "User | None" = None,
    ) -> None:
        """Dispatch a red-flag alert through the HIPAA-compliant channel.

        In production this would push to the EHR's in-basket or secure
        messaging system.  The stub logs the alert and records it.
        """
        recipients = [f"physician:{physician.id} ({physician.full_name})"]
        if nurse is not None:
            recipients.append(f"nurse:{nurse.id} ({nurse.full_name})")

        logger.warning(
            "RED FLAG ALERT | severity=%s patient=%s alert_id=%s "
            "trigger=%s recipients=%s session_completed=%s",
            alert.severity.value,
            patient.id,
            alert.id,
            alert.trigger_description,
            recipients,
            alert.session_was_completed,
        )

        # Mark the alert as notified
        alert.notification_sent_at = datetime.now(timezone.utc)
        alert.notification_channel = "hipaa_secure_message"
        await self._db.flush()

        await self._audit_notification(
            action="red_flag_alert_sent",
            user_id=physician.id,
            patient_id=patient.id,
            resource_type="red_flag_alert",
            resource_id=alert.id,
            details={
                "severity": alert.severity.value,
                "trigger": alert.trigger_description,
                "recipients": recipients,
                "session_completed": alert.session_was_completed,
            },
        )

    # ------------------------------------------------------------------
    # Appointment updates
    # ------------------------------------------------------------------

    async def send_appointment_update(
        self,
        appointment: "Appointment",
        patient: "User",
        change_type: str,
    ) -> None:
        """Notify a patient about an appointment change (confirmation, update, etc.)."""
        logger.info(
            "APPOINTMENT UPDATE | type=%s appointment=%s patient=%s (%s)",
            change_type,
            appointment.id,
            patient.id,
            patient.full_name,
        )

        await self._audit_notification(
            action=f"appointment_{change_type}_notification",
            user_id=patient.id,
            patient_id=patient.id,
            resource_type="appointment",
            resource_id=appointment.id,
            details={"change_type": change_type},
        )

    # ------------------------------------------------------------------
    # Reschedule
    # ------------------------------------------------------------------

    async def send_reschedule_notification(
        self,
        appointment: "Appointment",
        old_time: datetime,
        new_time: datetime,
    ) -> None:
        """Notify all relevant parties about a reschedule."""
        logger.info(
            "RESCHEDULE | appointment=%s old=%s new=%s patient=%s physician=%s",
            appointment.id,
            old_time.isoformat(),
            new_time.isoformat(),
            appointment.patient_id,
            appointment.physician_id,
        )

        await self._audit_notification(
            action="reschedule_notification",
            user_id=appointment.patient_id,
            patient_id=appointment.patient_id,
            resource_type="appointment",
            resource_id=appointment.id,
            details={
                "old_time": old_time.isoformat(),
                "new_time": new_time.isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    async def send_cancellation_notification(
        self,
        appointment: "Appointment",
    ) -> None:
        """Notify physician, nurse, and scheduler of a cancellation."""
        logger.info(
            "CANCELLATION | appointment=%s patient=%s physician=%s",
            appointment.id,
            appointment.patient_id,
            appointment.physician_id,
        )

        await self._audit_notification(
            action="cancellation_notification",
            user_id=appointment.physician_id,
            patient_id=appointment.patient_id,
            resource_type="appointment",
            resource_id=appointment.id,
            details={
                "physician_id": str(appointment.physician_id),
                "scheduler_id": str(appointment.scheduler_id) if appointment.scheduler_id else None,
            },
        )

    # ------------------------------------------------------------------
    # Coverage
    # ------------------------------------------------------------------

    async def send_coverage_notification(
        self,
        coverage,  # Coverage model instance
    ) -> None:
        """Notify the covering physician about a new coverage assignment."""
        logger.info(
            "COVERAGE ASSIGNED | coverage=%s covering=%s absent=%s %s–%s",
            coverage.id,
            coverage.covering_physician_id,
            coverage.absent_physician_id,
            coverage.start_date,
            coverage.end_date,
        )

        await self._audit_notification(
            action="coverage_notification",
            user_id=coverage.covering_physician_id,
            resource_type="coverage",
            resource_id=coverage.id,
            details={
                "absent_physician_id": str(coverage.absent_physician_id),
                "start_date": str(coverage.start_date),
                "end_date": str(coverage.end_date),
            },
        )
