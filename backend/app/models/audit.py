import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    SESSION_TIMEOUT = "session_timeout"
    DATA_ACCESS = "data_access"
    DATA_ACCESS_DENIED = "data_access_denied"
    DATA_EXPORT = "data_export"
    DATA_MODIFY = "data_modify"
    APPOINTMENT_CHANGE = "appointment_change"
    OVERRIDE = "override"
    COVERAGE_ACCESS = "coverage_access"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    patient_id_accessed: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    denial_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    patient_accessed: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[patient_id_accessed]
    )

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_patient_accessed", "patient_id_accessed", "created_at"),
    )
