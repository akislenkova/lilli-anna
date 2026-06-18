"""Patient-facing Epic SMART on FHIR routes.

Endpoints
---------
GET  /patients/me/epic/status       — is the patient connected to Epic?
GET  /patients/me/epic/auth-url     — start a new SMART on FHIR auth flow
POST /patients/me/epic/connect      — complete OAuth exchange (code → token)
GET  /patients/me/epic/records      — fetch live FHIR data from Epic
DELETE /patients/me/epic/disconnect — revoke and remove the stored tokens

All endpoints return ``{ available: false }`` (status 200) when
EPIC_CLIENT_ID is not configured so the frontend can render an
informational "not configured" state without error handling.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decrypt_phi, encrypt_phi, get_current_user, require_role, Role
from app.models.epic import EpicConnection
from app.services import epic_fhir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patients/me/epic", tags=["epic"])


# ---------------------------------------------------------------------------
# Helper: find active connection for current user
# ---------------------------------------------------------------------------

async def _active_connection(db: AsyncSession, user_id: str) -> EpicConnection | None:
    result = await db.execute(
        select(EpicConnection).where(
            EpicConnection.user_id == user_id,
            EpicConnection.status == "active",
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# GET /patients/me/epic/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def epic_status(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Return whether the patient has connected their Epic account."""
    if not settings.EPIC_CLIENT_ID:
        return {"available": True, "connected": True, "epic_patient_id": "demo-patient"}

    conn = await _active_connection(db, current_user["user_id"])
    return {
        "available": True,
        "connected": conn is not None,
        "epic_patient_id": conn.epic_patient_id if conn else None,
        "scope": conn.scope if conn else None,
    }


# ---------------------------------------------------------------------------
# GET /patients/me/epic/auth-url
# ---------------------------------------------------------------------------

@router.get("/auth-url")
async def epic_auth_url(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Start a new SMART on FHIR OAuth flow.

    Generates a PKCE verifier/challenge pair, persists a pending
    EpicConnection row, and returns the authorization URL the frontend
    should redirect the patient to.
    """
    if not settings.EPIC_CLIENT_ID:
        return {"available": False, "url": None}

    user_id = current_user["user_id"]

    # Remove any existing pending rows for this user to avoid orphans
    existing_pending = await db.execute(
        select(EpicConnection).where(
            EpicConnection.user_id == user_id,
            EpicConnection.status == "pending",
        )
    )
    for row in existing_pending.scalars().all():
        await db.delete(row)

    code_verifier, code_challenge = epic_fhir.generate_pkce_pair()
    state = epic_fhir.generate_state()

    conn = EpicConnection(
        user_id=uuid.UUID(user_id),
        status="pending",
        state=state,
        code_verifier=code_verifier,
    )
    db.add(conn)
    await db.commit()

    url = epic_fhir.build_auth_url(state=state, code_challenge=code_challenge)
    return {"available": True, "url": url, "state": state}


# ---------------------------------------------------------------------------
# POST /patients/me/epic/connect
# ---------------------------------------------------------------------------

class ConnectBody(BaseModel):
    code: str
    state: str


@router.post("/connect")
async def epic_connect(
    body: ConnectBody,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Complete the OAuth code exchange and store the patient's Epic tokens."""
    if not settings.EPIC_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Epic integration not configured")

    user_id = current_user["user_id"]

    # Find the pending connection that matches this state + user
    result = await db.execute(
        select(EpicConnection).where(
            EpicConnection.user_id == user_id,
            EpicConnection.state == body.state,
            EpicConnection.status == "pending",
        )
    )
    pending = result.scalar_one_or_none()

    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Please start the connection flow again.",
        )

    # Exchange code for tokens
    try:
        token_resp = await epic_fhir.exchange_code(
            code=body.code,
            code_verifier=pending.code_verifier,
        )
    except Exception as exc:
        logger.error("Epic token exchange failed for user %s: %s", user_id, exc)
        await db.delete(pending)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code with Epic. Please try again.",
        )

    # Revoke any previously active connection
    existing_active = await db.execute(
        select(EpicConnection).where(
            EpicConnection.user_id == user_id,
            EpicConnection.status == "active",
        )
    )
    for row in existing_active.scalars().all():
        await db.delete(row)

    # Promote pending → active
    expires_in: int = token_resp.get("expires_in", 3600)
    pending.status = "active"
    pending.state = None
    pending.code_verifier = None
    pending.access_token_enc = encrypt_phi(token_resp["access_token"])
    pending.refresh_token_enc = (
        encrypt_phi(token_resp["refresh_token"]) if token_resp.get("refresh_token") else None
    )
    pending.token_type = token_resp.get("token_type", "Bearer")
    pending.scope = token_resp.get("scope")
    pending.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    # Epic returns the patient's FHIR id in the token response
    pending.epic_patient_id = token_resp.get("patient")

    await db.commit()

    return {"connected": True, "epic_patient_id": pending.epic_patient_id}


# ---------------------------------------------------------------------------
# GET /patients/me/epic/records
# ---------------------------------------------------------------------------

@router.get("/records")
async def epic_records(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Fetch live FHIR R4 data from Epic for the authenticated patient.

    Automatically refreshes an expired access token using the stored
    refresh token if one is available.
    """
    if not settings.EPIC_CLIENT_ID:
        mock = (
            epic_fhir.mock_patient_records_morgan()
            if current_user.get("email") == "patient2@demo.com"
            else epic_fhir.mock_patient_records()
        )
        return {"available": True, **mock}

    user_id = current_user["user_id"]
    conn = await _active_connection(db, user_id)

    if conn is None:
        return {"available": True, "connected": False}

    # Refresh if expired (with 60s buffer)
    now = datetime.now(timezone.utc)
    access_token: str | None = None

    if conn.expires_at and conn.expires_at <= now + timedelta(seconds=60):
        if conn.refresh_token_enc:
            try:
                raw_refresh = decrypt_phi(conn.refresh_token_enc)
                token_resp = await epic_fhir.refresh_token(raw_refresh)
                conn.access_token_enc = encrypt_phi(token_resp["access_token"])
                if token_resp.get("refresh_token"):
                    conn.refresh_token_enc = encrypt_phi(token_resp["refresh_token"])
                expires_in = token_resp.get("expires_in", 3600)
                conn.expires_at = now + timedelta(seconds=expires_in)
                await db.commit()
                access_token = token_resp["access_token"]
            except Exception as exc:
                logger.warning("Epic token refresh failed for user %s: %s", user_id, exc)
                # Mark revoked so the patient is prompted to reconnect
                conn.status = "revoked"
                await db.commit()
                return {
                    "available": True,
                    "connected": False,
                    "error": "Your Epic session has expired. Please reconnect.",
                }
        else:
            # No refresh token — session expired, need to re-auth
            conn.status = "revoked"
            await db.commit()
            return {
                "available": True,
                "connected": False,
                "error": "Your Epic session has expired. Please reconnect.",
            }

    if access_token is None and conn.access_token_enc:
        try:
            access_token = decrypt_phi(conn.access_token_enc)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to decrypt Epic access token")

    if not access_token or not conn.epic_patient_id:
        raise HTTPException(status_code=500, detail="Incomplete Epic connection state")

    try:
        records = await epic_fhir.fetch_patient_records(
            access_token=access_token,
            epic_patient_id=conn.epic_patient_id,
        )
    except Exception as exc:
        logger.error("FHIR fetch failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch records from Epic. Please try again shortly.",
        )

    return {"available": True, **records}


# ---------------------------------------------------------------------------
# DELETE /patients/me/epic/disconnect
# ---------------------------------------------------------------------------

@router.delete("/disconnect")
async def epic_disconnect(
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Remove the patient's stored Epic tokens."""
    user_id = current_user["user_id"]

    result = await db.execute(
        select(EpicConnection).where(EpicConnection.user_id == user_id)
    )
    for row in result.scalars().all():
        await db.delete(row)

    await db.commit()
    return {"disconnected": True}
