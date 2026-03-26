"""Physician feedback and scheduler override schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PhysicianFeedbackCreate(BaseModel):
    """Physician submits feedback on appointment time accuracy."""

    appointment_id: UUID
    time_accuracy: str = Field(
        ..., pattern=r"^(accurate|too_short|too_long)$"
    )
    actual_vs_suggested_delta: int = Field(
        ..., description="Difference in minutes (positive = ran over)"
    )
    reason_text: Optional[str] = Field(default=None, max_length=2000)


class PhysicianFeedbackResponse(BaseModel):
    """Stored physician feedback."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    time_accuracy: str
    actual_vs_suggested_delta: int
    created_at: datetime


class SchedulerOverrideResponse(BaseModel):
    """Record of a scheduler overriding the AI-suggested duration."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_duration: int = Field(..., gt=0, description="Minutes")
    overridden_duration: int = Field(..., gt=0, description="Minutes")
    reason: str
