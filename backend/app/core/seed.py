"""Seed the database with demo accounts on first run.

Development only: creates a patient demo account plus provider accounts so
the full workflow can be tested locally.

Production: only the patient demo accounts are seeded (provider accounts must
be created via the admin interface). Provider credentials are NEVER logged.

Demo accounts
-------------
  Patient   : patient@demo.com   / demo1234          (all environments)
  Patient 2 : patient2@demo.com  / demo1234          (all environments)
  Physician : physician@demo.com / <set via env>      (non-production only)
  Scheduler : scheduler@demo.com / <set via env>      (non-production only)
  Nurse     : nurse@demo.com     / <set via env>      (non-production only)
"""

import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, encrypt_phi, hash_password
from app.models.patient import PatientProfile
from app.models.user import User

logger = logging.getLogger(__name__)

_DEMO_PASSWORD = "demo1234"

# Patient accounts — safe to seed in all environments (no HIPAA role)
_PATIENT_ACCOUNT = {
    "email": "patient@demo.com",
    "full_name": "Alex Rivera",
    "role": Role.PATIENT,
}

_PATIENT2_ACCOUNT = {
    "email": "patient2@demo.com",
    "full_name": "Morgan Lee",
    "role": Role.PATIENT,
}

# Provider accounts — development / staging only.
# In production these must be created by an admin; never auto-seeded.
_PROVIDER_ACCOUNTS = [
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
    """Create demo accounts if they don't already exist.

    In production only the patient account is created — provider accounts
    must be provisioned through the admin interface to comply with HIPAA
    access-control requirements.  Passwords are never written to logs.
    """
    from app.core.config import settings

    is_production = settings.ENVIRONMENT == "production"

    accounts_to_seed = [_PATIENT_ACCOUNT, _PATIENT2_ACCOUNT]
    if not is_production:
        accounts_to_seed += _PROVIDER_ACCOUNTS

    hashed = hash_password(_DEMO_PASSWORD)

    created = []
    for data in accounts_to_seed:
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
        # Log which accounts were created but never log the password
        logger.info("Demo accounts seeded: %s", ", ".join(created))
    else:
        logger.info("Demo accounts already exist — skipping seed.")

    # Ensure the demo patient has a PatientProfile (required by /patients/me/profile)
    patient_row = await session.execute(
        select(User).where(User.email == "patient@demo.com")
    )
    patient_user = patient_row.scalar_one_or_none()

    physician_user = None
    if not is_production:
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
            logger.info("Demo PatientProfile created.")

    # Second demo patient — herniated disc L4 with road-vibration sensitivity
    patient2_row = await session.execute(
        select(User).where(User.email == "patient2@demo.com")
    )
    patient2_user = patient2_row.scalar_one_or_none()

    if patient2_user:
        existing_profile2 = await session.execute(
            select(PatientProfile).where(PatientProfile.user_id == patient2_user.id)
        )
        if existing_profile2.scalar_one_or_none() is None:
            profile2 = PatientProfile(
                user_id=patient2_user.id,
                date_of_birth=date(1979, 8, 22),
                primary_physician_id=physician_user.id if physician_user else None,
                language_preference="en",
                medical_history=encrypt_phi(
                    "Diagnosed with herniated disc at L4-L5 (confirmed MRI 2023). "
                    "Reports significant pain exacerbation when driving over potholes, "
                    "speed bumps, or any road obstructions — jarring/vibration greatly "
                    "worsens lumbar pain. Previously completed 8 weeks of physical "
                    "therapy with partial improvement. No prior spinal surgery."
                ),
                chronic_conditions=encrypt_phi(
                    json.dumps(["Herniated disc L4-L5", "Lumbar radiculopathy"])
                ),
                current_medications=encrypt_phi(
                    json.dumps(["Ibuprofen 400mg as needed", "Cyclobenzaprine 5mg at night"])
                ),
            )
            session.add(profile2)
            await session.commit()
            logger.info("Demo PatientProfile 2 (Morgan Lee) created.")
