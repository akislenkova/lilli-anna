"""Seed the database with demo accounts on first run.

Only runs when the users table is empty (i.e. fresh database).
Never runs in production (ENVIRONMENT != "development").

Demo accounts
-------------
  Patient   : patient@demo.com   / demo1234
  Physician : physician@demo.com / demo1234  (Internal Medicine)
  Scheduler : scheduler@demo.com / demo1234
  Nurse     : nurse@demo.com     / demo1234
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, hash_password
from app.models.patient import PatientProfile
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
    {
        "email": "nurse@demo.com",
        "full_name": "Jamie Torres",
        "role": Role.NURSE,
    },
]


async def seed_demo_data(session: AsyncSession) -> None:
    """Create demo accounts if they don't already exist."""
    hashed = hash_password(_DEMO_PASSWORD)

    created = []
    for data in _DEMO_USERS:
        existing = await session.execute(
            select(User).where(User.email == data["email"])
        )
        if existing.scalar_one_or_none() is not None:
            continue

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
        created.append(data["email"])

    if created:
        await session.commit()
        logger.info("Demo accounts created: %s", ", ".join(created))
    else:
        logger.info("All demo accounts already exist — skipping seed.")

    # Ensure the demo patient has a PatientProfile (required by /patients/me/profile)
    patient_row = await session.execute(
        select(User).where(User.email == "patient@demo.com")
    )
    patient_user = patient_row.scalar_one_or_none()

    physician_row = await session.execute(
        select(User).where(User.email == "physician@demo.com")
    )
    physician_user = physician_row.scalar_one_or_none()

    if patient_user:
        existing_profile = await session.execute(
            select(PatientProfile).where(PatientProfile.user_id == patient_user.id)
        )
        if existing_profile.scalar_one_or_none() is None:
            profile = PatientProfile(
                user_id=patient_user.id,
                date_of_birth=date(1987, 3, 14),
                primary_physician_id=physician_user.id if physician_user else None,
                language_preference="en",
            )
            session.add(profile)
            await session.commit()
            logger.info("Demo PatientProfile created for %s", patient_user.email)

    logger.info(
        "Demo accounts created (password: %s):\n"
        "  patient@demo.com   — patient\n"
        "  physician@demo.com — physician (Internal Medicine)\n"
        "  scheduler@demo.com — scheduler\n"
        "  nurse@demo.com     — nurse",
        _DEMO_PASSWORD,
    )
