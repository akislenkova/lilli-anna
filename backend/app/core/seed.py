"""Seed the database with a demo patient account on first run.

Only creates the patient if no users exist yet. Provider accounts
(physician, scheduler, nurse) must be created by an administrator
to comply with HIPAA access controls.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, hash_password
from app.models.user import User

logger = logging.getLogger(__name__)

DEMO_PATIENT = {
    "email": "anna@test.com",
    "password": "password123",
    "full_name": "Anna K",
    "role": Role.PATIENT,
}


async def seed_demo_data(session: AsyncSession) -> None:
    """Create a demo patient account if the users table is empty."""
    result = await session.execute(select(func.count()).select_from(User))
    user_count = result.scalar() or 0

    if user_count > 0:
        logger.info("Database already has %d user(s) — skipping seed.", user_count)
        return

    logger.info("Empty database detected — creating demo patient account.")

    patient = User(
        email=DEMO_PATIENT["email"],
        hashed_password=hash_password(DEMO_PATIENT["password"]),
        full_name=DEMO_PATIENT["full_name"],
        role=DEMO_PATIENT["role"],
        is_active=True,
    )
    session.add(patient)
    await session.commit()

    logger.info(
        "Demo patient created: %s (email: %s). "
        "Provider accounts must be created by an administrator via POST /api/auth/register.",
        patient.full_name,
        patient.email,
    )
