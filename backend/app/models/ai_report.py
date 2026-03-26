import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.conversation import ConversationSession
    from app.models.user import User


class RedFlagSeverity(str, enum.Enum):
    ELEVATED = "elevated"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class AIReport(TimestampMixin, Base):
    __tablename__ = "ai_reports"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_sessions.id"), nullable=False, index=True
    )

    # Encrypted JSON fields
    probable_diagnoses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medication_interactions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Duration suggestion
    suggested_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_range_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_range_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Plaintext JSON
    red_flags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    complexity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Encrypted text views
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # nurse view
    full_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # physician view

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="ai_reports"
    )
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession", back_populates="ai_reports"
    )


class RedFlagAlert(TimestampMixin, Base):
    __tablename__ = "red_flag_alerts"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    nurse_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    trigger_description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RedFlagSeverity] = mapped_column(
        Enum(RedFlagSeverity, name="red_flag_severity", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    session_was_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notification_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="red_flag_alerts"
    )
    patient: Mapped["User"] = relationship("User", foreign_keys=[patient_id])
    physician: Mapped["User"] = relationship("User", foreign_keys=[physician_id])
    nurse: Mapped[Optional["User"]] = relationship("User", foreign_keys=[nurse_id])
    acknowledged_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[acknowledged_by]
    )

    __table_args__ = (
        Index("ix_red_flags_severity_unack", "severity", "acknowledged_at"),
    )
