"""AI report and diagnostic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProbableDiagnosis(BaseModel):
    """A single probable diagnosis with confidence score."""

    condition: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str = Field(..., min_length=1)


class AIReportResponse(BaseModel):
    """AI-generated report summary visible to multiple roles."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    suggested_duration: int = Field(..., gt=0, description="Minutes")
    confidence_level: float = Field(..., ge=0, le=1)
    duration_range: tuple[int, int] = Field(
        ..., description="(min_minutes, max_minutes)"
    )
    red_flags: list[str] = Field(default_factory=list)
    complexity_score: float = Field(..., ge=0, le=1)
    summary: str

    @field_validator("duration_range")
    @classmethod
    def valid_range(cls, v: tuple[int, int]) -> tuple[int, int]:
        if v[0] <= 0 or v[1] <= 0:
            raise ValueError("Duration range values must be positive")
        if v[0] > v[1]:
            raise ValueError("Minimum duration must not exceed maximum")
        return v


class AIReportPhysicianView(AIReportResponse):
    """Extended AI report for physicians — includes diagnoses and interactions."""

    probable_diagnoses: list[ProbableDiagnosis] = Field(default_factory=list)
    full_report: str
    medication_interactions: list[str] = Field(default_factory=list)


class RedFlagAlertResponse(BaseModel):
    """Alert raised when the AI detects a red flag during intake."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_description: str
    severity: str = Field(..., pattern=r"^(elevated|urgent|emergency)$")
    session_completed: bool
    acknowledged: bool
    created_at: datetime


class TimeEstimate(BaseModel):
    """Detailed time estimate for an appointment."""

    recommended_duration: int = Field(..., gt=0, description="Minutes")
    minimum_duration: int = Field(..., gt=0, description="Minutes")
    confidence: float = Field(..., ge=0, le=1)
    range_min: int = Field(..., gt=0, description="Minutes")
    range_max: int = Field(..., gt=0, description="Minutes")
    is_new_patient: bool
    reasoning: str

    @field_validator("range_max")
    @classmethod
    def max_gte_min(cls, v: int, info) -> int:
        range_min = info.data.get("range_min")
        if range_min is not None and v < range_min:
            raise ValueError("range_max must be >= range_min")
        return v

    @field_validator("minimum_duration")
    @classmethod
    def min_lte_recommended(cls, v: int, info) -> int:
        recommended = info.data.get("recommended_duration")
        if recommended is not None and v > recommended:
            raise ValueError(
                "minimum_duration must not exceed recommended_duration"
            )
        return v
