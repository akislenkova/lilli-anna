"""Patient profile and medical-history schemas."""

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientProfileCreate(BaseModel):
    """Payload to create a patient profile."""

    date_of_birth: date
    language_preference: str = Field(default="en", max_length=10)
    emergency_contact: str = Field(..., min_length=1, max_length=500)
    insurance_info: str = Field(..., min_length=1, max_length=1000)


class PatientProfileUpdate(BaseModel):
    """Partial update — every field is optional."""

    date_of_birth: Optional[date] = None
    language_preference: Optional[str] = Field(default=None, max_length=10)
    emergency_contact: Optional[str] = Field(default=None, max_length=500)
    insurance_info: Optional[str] = Field(default=None, max_length=1000)


class PatientProfileResponse(BaseModel):
    """Patient profile returned to authorized callers.

    Encrypted fields (emergency_contact, insurance_info) are NOT included
    here — they are served through dedicated endpoints with extra access
    controls.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    date_of_birth: date
    primary_physician_id: Optional[UUID] = None
    language_preference: str


class MedicationListResponse(BaseModel):
    """List of current medications."""

    medications: list[str]


class MedicalHistoryResponse(BaseModel):
    """Aggregated medical history."""

    conditions: list[str]
    medications: list[str]
    allergies: list[str]
