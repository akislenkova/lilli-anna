"""Proxy authorization service for minor / dependent access.

Manages proxy relationships (e.g., parent accessing a minor's data),
consent verification, age-of-consent threshold checking, and deactivation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy import ProxyAuthorization
from app.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class ProxyService:
    """Manages proxy / guardian authorization for dependent patients."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    async def create_proxy(
        self,
        patient_id: uuid.UUID,
        proxy_user_id: uuid.UUID,
        relationship: str,
        consent_path: str,
        state_code: str,
        age_of_consent: int | None = None,
    ) -> ProxyAuthorization:
        """Create a new proxy authorization record.

        The proxy is not active until verified by authorized staff via
        :meth:`verify_proxy`.
        """
        if patient_id == proxy_user_id:
            raise ValueError("A user cannot be their own proxy")

        # Check for existing active proxy
        existing_stmt = select(ProxyAuthorization).where(
            ProxyAuthorization.patient_id == patient_id,
            ProxyAuthorization.proxy_user_id == proxy_user_id,
            ProxyAuthorization.is_active == True,  # noqa: E712
        )
        existing_result = await self._db.execute(existing_stmt)
        if existing_result.scalar_one_or_none() is not None:
            raise ValueError("An active proxy already exists for this patient/proxy pair")

        proxy = ProxyAuthorization(
            patient_id=patient_id,
            proxy_user_id=proxy_user_id,
            relationship=relationship,
            consent_document_path=consent_path,
            state_code=state_code.upper(),
            minor_age_of_consent=age_of_consent,
            is_active=True,
            verified=False,
        )
        self._db.add(proxy)
        await self._db.flush()

        await self._audit.log_modification(
            user_id=proxy_user_id,
            resource_type="proxy_authorization",
            resource_id=proxy.id,
            changes={
                "action": "created",
                "patient_id": str(patient_id),
                "relationship": relationship,
                "state_code": state_code.upper(),
            },
            ip_address="",
        )

        logger.info(
            "proxy created | id=%s patient=%s proxy_user=%s relationship=%s",
            proxy.id,
            patient_id,
            proxy_user_id,
            relationship,
        )
        return proxy

    async def verify_proxy(
        self,
        proxy_id: uuid.UUID,
        verified_by: uuid.UUID,
    ) -> ProxyAuthorization:
        """Mark a proxy authorization as verified by authorized staff."""
        proxy = await self._db.get(ProxyAuthorization, proxy_id)
        if proxy is None:
            raise ValueError(f"Proxy authorization {proxy_id} not found")

        if not proxy.is_active:
            raise ValueError("Cannot verify an inactive proxy authorization")

        proxy.verified = True
        proxy.verified_by = verified_by
        proxy.verified_at = datetime.now(timezone.utc)
        await self._db.flush()

        await self._audit.log_modification(
            user_id=verified_by,
            resource_type="proxy_authorization",
            resource_id=proxy.id,
            changes={"action": "verified"},
            ip_address="",
        )

        logger.info("proxy verified | id=%s by=%s", proxy_id, verified_by)
        return proxy

    async def check_proxy_access(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> bool:
        """Check whether *user_id* has active, verified proxy access to *patient_id*."""
        stmt = select(ProxyAuthorization).where(
            ProxyAuthorization.proxy_user_id == user_id,
            ProxyAuthorization.patient_id == patient_id,
            ProxyAuthorization.is_active == True,  # noqa: E712
            ProxyAuthorization.verified == True,  # noqa: E712
        )
        result = await self._db.execute(stmt)
        proxy = result.scalar_one_or_none()

        if proxy is None:
            return False

        # Additional check: if age_of_consent is set, verify the patient
        # hasn't reached that age
        if proxy.age_of_consent is not None:
            age_check = await self.check_age_of_consent(patient_id)
            if age_check.get("has_reached_consent_age", False):
                logger.warning(
                    "proxy access denied: patient %s has reached age of consent",
                    patient_id,
                )
                return False

        return True

    async def check_age_of_consent(
        self,
        patient_id: uuid.UUID,
    ) -> dict:
        """Check if a patient is approaching or has reached the age of consent.

        Returns a dict with:
        - has_reached_consent_age: bool
        - approaching (within 6 months): bool
        - patient_age: current age in years
        - consent_age: the configured threshold
        """
        from app.models.patient import PatientProfile

        # Look up patient DOB
        user = await self._db.get(User, patient_id)
        profile_stmt = select(PatientProfile).where(
            PatientProfile.user_id == patient_id
        )
        profile_result = await self._db.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()

        dob = None
        if profile and profile.date_of_birth:
            dob = profile.date_of_birth
        elif user and user.date_of_birth:
            dob = user.date_of_birth

        if dob is None:
            return {
                "has_reached_consent_age": False,
                "approaching": False,
                "patient_age": None,
                "consent_age": None,
                "error": "Date of birth not available",
            }

        # Find the consent age from the proxy records
        proxy_stmt = select(ProxyAuthorization).where(
            ProxyAuthorization.patient_id == patient_id,
            ProxyAuthorization.is_active == True,  # noqa: E712
            ProxyAuthorization.age_of_consent.isnot(None),
        ).limit(1)
        proxy_result = await self._db.execute(proxy_stmt)
        proxy = proxy_result.scalar_one_or_none()

        if proxy is None:
            return {
                "has_reached_consent_age": False,
                "approaching": False,
                "patient_age": self._calculate_age(dob),
                "consent_age": None,
                "info": "No proxy with age_of_consent found",
            }

        current_age = self._calculate_age(dob)
        consent_age = proxy.age_of_consent
        has_reached = current_age >= consent_age

        # "Approaching" = within 6 months of the birthday that hits consent age
        approaching = False
        if not has_reached:
            consent_birthday = date(
                dob.year + consent_age, dob.month, dob.day
            )
            days_until = (consent_birthday - date.today()).days
            approaching = 0 < days_until <= 180

        if approaching:
            logger.warning(
                "patient %s is approaching age of consent (%d) — current age %d",
                patient_id,
                consent_age,
                current_age,
            )

        return {
            "has_reached_consent_age": has_reached,
            "approaching": approaching,
            "patient_age": current_age,
            "consent_age": consent_age,
        }

    async def deactivate_proxy(self, proxy_id: uuid.UUID) -> ProxyAuthorization:
        """Deactivate a proxy authorization."""
        proxy = await self._db.get(ProxyAuthorization, proxy_id)
        if proxy is None:
            raise ValueError(f"Proxy authorization {proxy_id} not found")

        proxy.is_active = False
        proxy.deactivated_at = datetime.now(timezone.utc)
        await self._db.flush()

        await self._audit.log_modification(
            user_id=proxy.proxy_user_id,
            resource_type="proxy_authorization",
            resource_id=proxy.id,
            changes={"action": "deactivated"},
            ip_address="",
        )

        logger.info("proxy deactivated | id=%s", proxy_id)
        return proxy

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_age(dob: date) -> int:
        today = date.today()
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age
