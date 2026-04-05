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
    from app.models.ai_report import AIReport, RedFlagAlert
    from app.models.conversation import ConversationSession
    from app.models.user import User


class AppointmentStatus(str, enum.Enum):
    PENDING_INTAKE = "pending_intake"
    INTAKE_COMPLETE = "intake_complete"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class VisitType(str, enum.Enum):
    YEARLY_CHECKUP = "yearly_checkup"
    SPECIFIC_CONCERN = "specific_concern"


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    physician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    scheduler_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status", values_callable=lambda e: [m.value for m in e]),
        default=AppointmentStatus.PENDING_INTAKE,
        nullable=False,
        index=True,
    )
    visit_type: Mapped[VisitType] = mapped_column(
        Enum(VisitType, name="visit_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI duration suggestion
    ai_suggested_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_duration_range_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_duration_range_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Scheduler override
    scheduler_approved_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scheduler_override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Post-visit
    actual_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_new_patient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    patient: Mapped["User"] = relationship(
        "User", back_populates="appointments_as_patient", foreign_keys=[patient_id]
    )
    physician: Mapped["User"] = relationship(
        "User", back_populates="appointments_as_physician", foreign_keys=[physician_id]
    )
    scheduler: Mapped[Optional["User"]] = relationship("User", foreign_keys=[scheduler_id])
    versions: Mapped[list["AppointmentVersion"]] = relationship(
        "AppointmentVersion", back_populates="appointment", cascade="all, delete-orphan"
    )
    conversation_sessions: Mapped[list["ConversationSession"]] = relationship(
        "ConversationSession", back_populates="appointment"
    )
    ai_reports: Mapped[list["AIReport"]] = relationship(
        "AIReport", back_populates="appointment"
    )
    red_flag_alerts: Mapped[list["RedFlagAlert"]] = relationship(
        "RedFlagAlert", back_populates="appointment"
    )

    __table_args__ = (
        Index("ix_appointments_physician_scheduled", "physician_id", "scheduled_start"),
        Index("ix_appointments_patient_status", "patient_id", "status"),
    )


class AppointmentVersion(Base):
    __tablename__ = "appointment_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    changes_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="versions"
    )
    changed_by_user: Mapped["User"] = relationship("User", foreign_keys=[changed_by])
