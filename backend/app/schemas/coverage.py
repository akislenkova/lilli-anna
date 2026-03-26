"""Coverage and proxy-authorization schemas."""

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoverageCreate(BaseModel):
    """Payload to create a physician coverage period."""

    covering_physician_id: UUID
    absent_physician_id: UUID
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start is not None and v < start:
            raise ValueError("end_date must not be before start_date")
        return v


class CoverageResponse(BaseModel):
    """Physician coverage record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    covering_physician_id: UUID
    absent_physician_id: UUID
    start_date: date
    end_date: date
    is_active: bool


class ProxyAuthCreate(BaseModel):
    """Payload to create a proxy authorization (e.g., parent for minor)."""

    patient_id: UUID
    proxy_user_id: UUID
    relationship: str = Field(..., min_length=1, max_length=100)
    consent_document_path: str = Field(..., min_length=1)
    state_code: str = Field(..., min_length=2, max_length=2)
    minor_age_of_consent: Optional[int] = Field(default=None, ge=0, le=21)


class ProxyAuthResponse(BaseModel):
    """Stored proxy authorization."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    proxy_user_id: UUID
    relationship: str
    verified: bool
    is_active: bool
