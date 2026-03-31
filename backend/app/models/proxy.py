import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ProxyRelationship(str, enum.Enum):
    PARENT_GUARDIAN = "parent_guardian"
    CAREGIVER = "caregiver"
    LEGAL_PROXY = "legal_proxy"


class ProxyAuthorization(TimestampMixin, Base):
    __tablename__ = "proxy_authorizations"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    proxy_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    relationship: Mapped[ProxyRelationship] = mapped_column(
        Enum(ProxyRelationship, name="proxy_relationship", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    consent_document_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # encrypted
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    minor_age_of_consent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    patient: Mapped["User"] = sa_relationship("User", foreign_keys="[ProxyAuthorization.patient_id]")
    proxy_user: Mapped["User"] = sa_relationship("User", foreign_keys="[ProxyAuthorization.proxy_user_id]")
    verified_by_user: Mapped[Optional["User"]] = sa_relationship(
        "User", foreign_keys="[ProxyAuthorization.verified_by]"
    )

    __table_args__ = (
        Index("ix_proxy_patient_active", "patient_id", "is_active"),
        Index("ix_proxy_user_active", "proxy_user_id", "is_active"),
    )
