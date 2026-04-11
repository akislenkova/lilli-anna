"""SQLAlchemy model for storing patient Epic SMART on FHIR OAuth tokens.

One row per patient per connection attempt.  Only one row per user may be
'active' at a time; pending rows are replaced when a new auth flow is started.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EpicConnection(TimestampMixin, Base):
    __tablename__ = "epic_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'pending' while the OAuth flow is in flight; 'active' after token
    # exchange succeeds; 'revoked' after the patient disconnects.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # PKCE / OAuth handshake values — only populated during pending state
    state: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    code_verifier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tokens — stored AES-256 encrypted via encrypt_phi / decrypt_phi
    access_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Epic's internal FHIR Patient resource id (different from MRN)
    epic_patient_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
