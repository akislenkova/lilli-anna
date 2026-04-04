"""Immutable audit logging service for HIPAA compliance.

All log operations are INSERT-only -- no UPDATE or DELETE is ever issued
against the ``audit_logs`` table.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.schemas.audit import AuditLogQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class AuditService:
    """Provides immutable audit trail operations.

    Every public method performs an INSERT and flushes immediately so the
    log entry is persisted even if the caller's transaction later rolls back
    (in production you would use a separate "audit" DB connection for true
    independence).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ----- core insert helper ------------------------------------------------

    async def _insert(self, **kwargs) -> AuditLog:
        entry = AuditLog(**kwargs)
        self._db.add(entry)
        await self._db.flush()
        logger.info(
            "audit | action=%s user=%s resource=%s/%s success=%s",
            kwargs.get("action"),
            kwargs.get("user_id"),
            kwargs.get("resource_type"),
            kwargs.get("resource_id"),
            kwargs.get("success", True),
        )
        return entry

    # ----- public logging methods -------------------------------------------

    async def log_access(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        action: str,
        success: bool,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        denial_reason: str | None = None,
    ) -> AuditLog:
        """Record an access attempt against a protected resource."""
        return await self._insert(
            user_id=user_id,
            patient_id_accessed=patient_id,
            resource_type=resource_type,
            resource_id=str(resource_id),
            action=action,
            success=success,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            denial_reason=denial_reason,
        )

    async def log_login(
        self,
        user_id: uuid.UUID,
        ip_address: str,
        user_agent: str,
        success: bool,
    ) -> AuditLog:
        """Record a login attempt (successful or failed)."""
        return await self._insert(
            user_id=user_id,
            action="login",
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"event": "login"},
        )

    async def log_session_event(
        self,
        user_id: uuid.UUID,
        event_type: str,
        ip_address: str,
    ) -> AuditLog:
        """Record session lifecycle events (timeout, logout, etc.)."""
        return await self._insert(
            user_id=user_id,
            action="logout" if event_type == "logout" else "session_timeout",
            ip_address=ip_address,
            details={"event_type": event_type},
        )

    async def log_data_export(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        resource_type: str,
        details: dict | None = None,
    ) -> AuditLog:
        """Record when a user exports/downloads patient data."""
        return await self._insert(
            user_id=user_id,
            patient_id_accessed=patient_id,
            action="data_export",
            resource_type=resource_type,
            details=details,
        )

    async def log_modification(
        self,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        changes: dict,
        ip_address: str,
    ) -> AuditLog:
        """Record a modification (create/update) of a resource."""
        return await self._insert(
            user_id=user_id,
            action="data_modify",
            resource_type=resource_type,
            resource_id=str(resource_id),
            details={"changes": changes},
            ip_address=ip_address,
        )

    # ----- query methods ----------------------------------------------------

    async def query_logs(self, filters: AuditLogQuery) -> list[AuditLog]:
        """Return audit log entries matching the given filters.

        Supports pagination via ``page`` / ``per_page`` on the query object.
        """
        stmt = select(AuditLog)
        conditions = []

        if filters.user_id is not None:
            conditions.append(AuditLog.user_id == filters.user_id)
        if filters.patient_id is not None:
            conditions.append(AuditLog.patient_id_accessed == filters.patient_id)
        if filters.action_type is not None:
            conditions.append(AuditLog.action == filters.action_type)
        if filters.date_range_start is not None:
            conditions.append(AuditLog.created_at >= filters.date_range_start)
        if filters.date_range_end is not None:
            conditions.append(AuditLog.created_at <= filters.date_range_end)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = (
            stmt.order_by(AuditLog.created_at.desc())
            .offset((filters.page - 1) * filters.per_page)
            .limit(filters.per_page)
        )

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_override_patterns(
        self,
        scheduler_id: uuid.UUID | None = None,
        date_range: tuple[datetime, datetime] | None = None,
    ) -> dict:
        """Analyse scheduler override patterns against post-visit feedback.

        Returns a summary dict with:
        - total_overrides: count of overrides in the period
        - overrides_too_short: how many resulted in physician "too_short" feedback
        - overrides_too_long: how many resulted in "too_long" feedback
        - overrides_accurate: how many were confirmed accurate
        - average_delta_minutes: mean difference between override and actual
        - scheduler_breakdown: per-scheduler stats (if scheduler_id is None)

        This is a read-only analytical query; no data is modified.
        """
        from app.models.feedback import SchedulerOverride, PhysicianFeedback

        # Build override query
        override_stmt = select(SchedulerOverride)
        if scheduler_id is not None:
            override_stmt = override_stmt.where(
                SchedulerOverride.scheduler_id == scheduler_id
            )
        if date_range is not None:
            override_stmt = override_stmt.where(
                SchedulerOverride.created_at >= date_range[0],
                SchedulerOverride.created_at <= date_range[1],
            )

        override_result = await self._db.execute(override_stmt)
        overrides = list(override_result.scalars().all())

        if not overrides:
            return {
                "total_overrides": 0,
                "overrides_too_short": 0,
                "overrides_too_long": 0,
                "overrides_accurate": 0,
                "average_delta_minutes": 0.0,
                "scheduler_breakdown": {},
            }

        # Gather associated feedback
        appointment_ids = [o.appointment_id for o in overrides]
        feedback_stmt = select(PhysicianFeedback).where(
            PhysicianFeedback.appointment_id.in_(appointment_ids)
        )
        feedback_result = await self._db.execute(feedback_stmt)
        feedback_map: dict[uuid.UUID, PhysicianFeedback] = {
            fb.appointment_id: fb for fb in feedback_result.scalars().all()
        }

        too_short = 0
        too_long = 0
        accurate = 0
        deltas: list[int] = []
        scheduler_stats: dict[str, dict] = {}

        for ovr in overrides:
            fb = feedback_map.get(ovr.appointment_id)
            sid = str(ovr.scheduler_id)
            if sid not in scheduler_stats:
                scheduler_stats[sid] = {
                    "total": 0,
                    "too_short": 0,
                    "too_long": 0,
                    "accurate": 0,
                }
            scheduler_stats[sid]["total"] += 1

            if fb is not None:
                if fb.time_accuracy.value == "too_short":
                    too_short += 1
                    scheduler_stats[sid]["too_short"] += 1
                elif fb.time_accuracy.value == "too_long":
                    too_long += 1
                    scheduler_stats[sid]["too_long"] += 1
                else:
                    accurate += 1
                    scheduler_stats[sid]["accurate"] += 1
                if fb.actual_vs_suggested_delta is not None:
                    deltas.append(fb.actual_vs_suggested_delta)

        return {
            "total_overrides": len(overrides),
            "overrides_too_short": too_short,
            "overrides_too_long": too_long,
            "overrides_accurate": accurate,
            "average_delta_minutes": (
                sum(deltas) / len(deltas) if deltas else 0.0
            ),
            "scheduler_breakdown": scheduler_stats,
        }
