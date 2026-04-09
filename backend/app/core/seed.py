"""Seed the database with demo accounts on first run.

Only runs when the users table is empty (i.e. fresh database).
Never runs in production (ENVIRONMENT != "development").

Demo accounts
-------------
  Patient   : patient@demo.com   / demo1234
  Physician : physician@demo.com / demo1234  (Internal Medicine)
  Scheduler : scheduler@demo.com / demo1234
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, hash_password
from app.models.user import User

logger = logging.getLogger(__name__)

_DEMO_PASSWORD = "demo1234"

_DEMO_USERS = [
    {
        "email": "patient@demo.com",
        "full_name": "Alex Rivera",
        "role": Role.PATIENT,
    },
    {
        "email": "physician@demo.com",
        "full_name": "Dr. Sarah Chen",
        "role": Role.PHYSICIAN,
        "specialty": "Internal Medicine",
        "license_number": "MD-DEMO-001",
    },
    {
        "email": "scheduler@demo.com",
        "full_name": "Jordan Mills",
        "role": Role.SCHEDULER,
    },
]


async def seed_demo_data(session: AsyncSession) -> None:
    """Create demo accounts if the users table is empty."""
    result = await session.execute(select(func.count()).select_from(User))
    user_count = result.scalar() or 0

    if user_count > 0:
        logger.info("Database already has %d user(s) — skipping seed.", user_count)
        return

    logger.info("Empty database — seeding demo accounts.")
    hashed = hash_password(_DEMO_PASSWORD)

    for data in _DEMO_USERS:
        user = User(
            email=data["email"],
            hashed_password=hashed,
            full_name=data["full_name"],
            role=data["role"],
            is_active=True,
            specialty=data.get("specialty"),
            license_number=data.get("license_number"),
        )
        session.add(user)

    await session.commit()

    logger.info(
        "Demo accounts created (password: %s):\n"
        "  patient@demo.com   — patient\n"
        "  physician@demo.com — physician (Internal Medicine)\n"
        "  scheduler@demo.com — scheduler",
        _DEMO_PASSWORD,
    )
