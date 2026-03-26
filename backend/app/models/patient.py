import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class PatientProfile(TimestampMixin, Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    primary_physician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # Encrypted JSON fields (stored as encrypted strings, decrypted at service layer)
    medical_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_medications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    insurance_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Plaintext fields
    language_preference: Mapped[Optional[str]] = mapped_column(String(10), default="en", nullable=True)
    proxy_authorized_users: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="patient_profile", foreign_keys=[user_id]
    )
    primary_physician: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[primary_physician_id]
    )
