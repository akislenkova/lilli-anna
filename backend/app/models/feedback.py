import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.user import User


class TimeAccuracy(str, enum.Enum):
    ACCURATE = "accurate"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"


class PhysicianFeedback(Base):
    __tablename__ = "physician_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    time_accuracy: Mapped[TimeAccuracy] = mapped_column(
        Enum(TimeAccuracy, name="time_accuracy", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    actual_vs_suggested_delta: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visit_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    appointment: Mapped["Appointment"] = relationship("Appointment", foreign_keys=[appointment_id])
    physician: Mapped["User"] = relationship("User", foreign_keys=[physician_id])


class SchedulerOverride(Base):
    __tablename__ = "scheduler_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    scheduler_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    original_ai_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    overridden_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    appointment: Mapped["Appointment"] = relationship("Appointment", foreign_keys=[appointment_id])
    scheduler: Mapped["User"] = relationship("User", foreign_keys=[scheduler_id])
