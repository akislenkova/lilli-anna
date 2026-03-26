"""Authentication and user schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenData(BaseModel):
    """JWT token payload."""

    sub: UUID = Field(..., description="User ID")
    role: str
    exp: datetime


class TokenResponse(BaseModel):
    """Response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Credentials for login."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class UserCreate(BaseModel):
    """Payload to register a new user."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., pattern=r"^(patient|physician|nurse|scheduler|admin)$")


class UserResponse(BaseModel):
    """Public user representation (never includes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
