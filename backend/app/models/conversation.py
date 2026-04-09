import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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
    from app.models.ai_report import AIReport
    from app.models.appointment import Appointment
    from app.models.user import User


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    PATIENT = "patient"
    AI = "ai"


class ContentType(str, enum.Enum):
    TEXT = "text"
    VOICE_TRANSCRIPT = "voice_transcript"


class ConversationSession(TimestampMixin, Base):
    __tablename__ = "conversation_sessions"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", values_callable=lambda e: [m.value for m in e]),
        default=SessionStatus.IN_PROGRESS,
        nullable=False,
    )
    visit_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    concerns_ranked: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    questions_asked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_questions: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    disclaimer_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disclaimer_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="conversation_sessions"
    )
    patient: Mapped["User"] = relationship("User", foreign_keys=[patient_id])
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage", back_populates="session", cascade="all, delete-orphan"
    )
    ai_reports: Mapped[list["AIReport"]] = relationship(
        "AIReport", back_populates="session"
    )

    __table_args__ = (
        Index("ix_sessions_patient_status", "patient_id", "status"),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_sessions.id"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type", values_callable=lambda e: [m.value for m in e]),
        default=ContentType.TEXT,
        nullable=False,
    )
    voice_note_retained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language_detected: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession", back_populates="messages"
    )

    __table_args__ = (
        Index("ix_messages_session_seq", "session_id", "sequence_number"),
    )
