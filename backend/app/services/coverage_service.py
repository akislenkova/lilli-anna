"""Physician coverage management service.

Handles the creation, revocation, expiry, and verification of coverage
periods where one physician covers for another's patients.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage import PhysicianCoverage as Coverage
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class CoverageService:
    """Manages physician coverage periods."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)
        self._notifications = NotificationService(db)

    async def create_coverage(
        self,
        covering_physician_id: uuid.UUID,
        absent_physician_id: uuid.UUID,
        start_date: date,
        end_date: date,
        assigned_by: uuid.UUID,
    ) -> Coverage:
        """Create a new coverage record and notify the covering physician."""
        if end_date < start_date:
            raise ValueError("end_date must not be before start_date")

        if covering_physician_id == absent_physician_id:
            raise ValueError("A physician cannot cover for themselves")

        coverage = Coverage(
            covering_physician_id=covering_physician_id,
            absent_physician_id=absent_physician_id,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
            assigned_by=assigned_by,
        )
        self._db.add(coverage)
        await self._db.flush()

        await self._notifications.send_coverage_notification(coverage)
        await self._audit.log_modification(
            user_id=assigned_by,
            resource_type="coverage",
            resource_id=coverage.id,
            changes={
                "action": "created",
                "covering": str(covering_physician_id),
                "absent": str(absent_physician_id),
                "start": str(start_date),
                "end": str(end_date),
            },
            ip_address="",
        )

        logger.info(
            "coverage created | id=%s covering=%s absent=%s %s–%s",
            coverage.id,
            covering_physician_id,
            absent_physician_id,
            start_date,
            end_date,
        )
        return coverage

    async def revoke_coverage(self, coverage_id: uuid.UUID) -> Coverage:
        """Revoke an active coverage record."""
        coverage = await self._db.get(Coverage, coverage_id)
        if coverage is None:
            raise ValueError(f"Coverage {coverage_id} not found")

        coverage.is_active = False
        coverage.revoked_at = datetime.now(timezone.utc)
        await self._db.flush()

        logger.info("coverage revoked | id=%s", coverage_id)
        return coverage

    async def check_coverage(
        self,
        physician_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> bool:
        """Check if *physician_id* has active coverage for *patient_id*'s usual physician."""
        from app.models.patient import PatientProfile

        profile_stmt = select(PatientProfile).where(
            PatientProfile.user_id == patient_id
        )
        result = await self._db.execute(profile_stmt)
        profile = result.scalar_one_or_none()

        if profile is None or profile.primary_physician_id is None:
            return False

        today = date.today()
        coverage_stmt = select(Coverage).where(
            Coverage.covering_physician_id == physician_id,
            Coverage.absent_physician_id == profile.primary_physician_id,
            Coverage.is_active == True,  # noqa: E712
            Coverage.start_date <= today,
            Coverage.end_date >= today,
        )
        cov_result = await self._db.execute(coverage_stmt)
        return cov_result.scalar_one_or_none() is not None

    async def auto_expire_coverages(self) -> int:
        """Expire all coverage records whose end_date has passed."""
        today = date.today()
        stmt = (
            update(Coverage)
            .where(
                Coverage.is_active == True,  # noqa: E712
                Coverage.end_date < today,
            )
            .values(is_active=False)
        )
        result = await self._db.execute(stmt)
        await self._db.flush()

        count = result.rowcount
        if count > 0:
            logger.info("auto-expired %d coverage record(s)", count)
        return count

    async def get_active_coverages(self) -> list[Coverage]:
        """Return all currently active coverage records."""
        stmt = (
            select(Coverage)
            .where(Coverage.is_active == True)  # noqa: E712
            .order_by(Coverage.start_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
