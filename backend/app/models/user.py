import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import Role
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.patient import PatientProfile


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Physician-specific
    specialty: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Patient-specific
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # encrypted
    medical_record_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )

    # Relationships
    patient_profile: Mapped[Optional["PatientProfile"]] = relationship(
        "PatientProfile",
        back_populates="user",
        foreign_keys="PatientProfile.user_id",
        uselist=False,
    )
    appointments_as_patient: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="patient", foreign_keys="Appointment.patient_id"
    )
    appointments_as_physician: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="physician", foreign_keys="Appointment.physician_id"
    )

    __table_args__ = (
        Index("ix_users_role_active", "role", "is_active"),
    )
