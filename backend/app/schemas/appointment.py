"""Appointment schemas with role-specific views."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    """Payload to create a new appointment."""

    patient_id: UUID
    physician_id: UUID
    visit_type: str = Field(..., min_length=1, max_length=100)
    scheduled_start: datetime


class AppointmentUpdate(BaseModel):
    """Partial update for an existing appointment."""

    status: Optional[str] = Field(default=None, max_length=50)
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    scheduler_approved_duration: Optional[int] = Field(
        default=None, gt=0, description="Approved duration in minutes"
    )
    scheduler_override_reason: Optional[str] = Field(default=None, max_length=1000)


class AppointmentResponse(BaseModel):
    """Full appointment data for authorized roles."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    physician_id: Optional[UUID] = None
    visit_type: str
    status: str
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    ai_suggested_duration: Optional[int] = None
    ai_confidence: Optional[float] = None
    ai_duration_range_min: Optional[int] = None
    ai_duration_range_max: Optional[int] = None
    scheduler_approved_duration: Optional[int] = None
    scheduler_override_reason: Optional[str] = None
    is_new_patient: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    patient_name: Optional[str] = None
    initial_reason: Optional[str] = None


class AppointmentListResponse(BaseModel):
    """Paginated list of appointments."""

    items: list[AppointmentResponse]
    total: int
    page: int
    per_page: int


class AppointmentSchedulerView(BaseModel):
    """View for schedulers — no transcript, no medical history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    physician_id: Optional[UUID] = None
    visit_type: str
    status: str
    scheduled_start: Optional[datetime] = None
    patient_initial_reason: Optional[str] = None
    questionnaire_answers: Optional[dict] = None
    ai_suggested_duration: Optional[int] = None


class AppointmentPhysicianView(BaseModel):
    """View for physicians — includes transcript, AI report, history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    physician_id: Optional[UUID] = None
    visit_type: str
    status: str
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    ai_suggested_duration: Optional[int] = None
    ai_confidence: Optional[float] = None
    ai_duration_range_min: Optional[int] = None
    ai_duration_range_max: Optional[int] = None
    scheduler_approved_duration: Optional[int] = None
    scheduler_override_reason: Optional[str] = None
    is_new_patient: Optional[bool] = None
    initial_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    patient_name: Optional[str] = None
    feedback_submitted: Optional[bool] = None


class AppointmentNurseView(BaseModel):
    """View for nurses — scheduling overview, summary, red flags (no transcript)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    physician_id: Optional[UUID] = None
    visit_type: str
    status: str
    scheduled_start: Optional[datetime] = None
    ai_suggested_duration: Optional[int] = None
    conversation_summary: Optional[str] = None
    red_flags: list[str] = Field(default_factory=list)


class AppointmentVersionResponse(BaseModel):
    """Single version entry in an appointment's audit trail."""

    model_config = ConfigDict(from_attributes=True)

    version_number: int
    changes: dict
    changed_by: UUID
    changed_at: datetime


class SuggestedAlternative(BaseModel):
    """A single suggested alternative slot."""

    physician_id: UUID
    start: datetime
    end: datetime


class SchedulingConflict(BaseModel):
    """Conflict details when a proposed slot overlaps existing bookings."""

    conflicting_appointment_id: UUID
    physician_id: UUID
    conflict_start: datetime
    conflict_end: datetime
    reason: str
    suggested_alternatives: list[SuggestedAlternative] = Field(default_factory=list)


class RankedPatient(BaseModel):
    """A single patient in a priority ranking."""

    patient_id: UUID
    appointment_id: UUID
    urgency_score: float = Field(..., ge=0, le=1)
    reason: str


class PriorityRanking(BaseModel):
    """Patients ranked by urgency for the scheduler."""

    patients: list[RankedPatient]
