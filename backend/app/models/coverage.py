import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class PhysicianCoverage(TimestampMixin, Base):
    __tablename__ = "physician_coverages"

    covering_physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    absent_physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    covering_physician: Mapped["User"] = relationship(
        "User", foreign_keys=[covering_physician_id]
    )
    absent_physician: Mapped["User"] = relationship(
        "User", foreign_keys=[absent_physician_id]
    )
    assigned_by_user: Mapped["User"] = relationship(
        "User", foreign_keys=[assigned_by]
    )

    __table_args__ = (
        Index(
            "ix_coverage_active_dates",
            "absent_physician_id",
            "start_date",
            "end_date",
            "is_active",
        ),
    )
