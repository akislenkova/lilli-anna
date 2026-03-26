"""Audit log schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    success: bool
    created_at: datetime


class AuditLogQuery(BaseModel):
    """Query parameters for filtering audit logs."""

    user_id: Optional[UUID] = None
    patient_id: Optional[UUID] = None
    action_type: Optional[str] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)
