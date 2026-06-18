"""Epic SMART on FHIR R4 client for patient-facing health record access.

Handles:
- PKCE code-verifier / challenge generation
- OAuth 2.0 authorization URL construction (standalone launch, public client)
- Authorization code → token exchange
- Access token refresh
- FHIR R4 resource fetching: Patient, Condition, MedicationRequest,
  AllergyIntolerance, Observation (vitals)

All methods return empty / graceful results when EPIC_CLIENT_ID is not
configured so the UI can render a "not connected" state without raising.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def generate_pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for PKCE-S256.

    The verifier is a cryptographically random URL-safe string.
    The challenge is BASE64URL(SHA-256(verifier)) per RFC 7636.
    """
    verifier = secrets.token_urlsafe(96)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def generate_state() -> str:
    """Return a random opaque state token for CSRF protection."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

_PATIENT_SCOPES = (
    "openid fhirUser launch/patient "
    "patient/Patient.read "
    "patient/Condition.read "
    "patient/MedicationRequest.read "
    "patient/AllergyIntolerance.read "
    "patient/Observation.read"
)


def build_auth_url(state: str, code_challenge: str) -> str | None:
    """Return the Epic OAuth authorization URL, or None if not configured."""
    if not settings.EPIC_CLIENT_ID:
        return None

    base = settings.EPIC_FHIR_BASE_URL.rstrip("/")
    redirect_uri = f"{settings.FRONTEND_URL.rstrip('/')}/epic-callback"

    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": settings.EPIC_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": _PATIENT_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "iss": f"{base}/api/FHIR/R4",
    })
    return f"{base}/oauth2/authorize?{params}"


async def exchange_code(code: str, code_verifier: str) -> dict[str, Any]:
    """Exchange an authorization code for tokens.

    Returns the token response dict, or raises ``httpx.HTTPStatusError`` on
    failure.
    """
    base = settings.EPIC_FHIR_BASE_URL.rstrip("/")
    redirect_uri = f"{settings.FRONTEND_URL.rstrip('/')}/epic-callback"

    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.EPIC_CLIENT_ID,
        "code_verifier": code_verifier,
    }
    # If a client secret is configured (confidential client), include it.
    if settings.EPIC_CLIENT_SECRET:
        payload["client_secret"] = settings.EPIC_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/oauth2/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_token(refresh_tok: str) -> dict[str, Any]:
    """Use a refresh token to obtain a new access token."""
    base = settings.EPIC_FHIR_BASE_URL.rstrip("/")

    payload: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
        "client_id": settings.EPIC_CLIENT_ID,
    }
    if settings.EPIC_CLIENT_SECRET:
        payload["client_secret"] = settings.EPIC_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/oauth2/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# FHIR helpers
# ---------------------------------------------------------------------------

def _fhir_r4_base() -> str:
    return settings.EPIC_FHIR_BASE_URL.rstrip("/") + "/api/FHIR/R4"


def _coding_display(cc: dict | None) -> str:
    """Extract the best display string from a FHIR CodeableConcept."""
    if not cc:
        return ""
    if cc.get("text"):
        return cc["text"]
    for coding in cc.get("coding", []):
        if coding.get("display"):
            return coding["display"]
    return ""


# ---------------------------------------------------------------------------
# Demo / mock data (used when EPIC_CLIENT_ID is not configured)
# ---------------------------------------------------------------------------

def mock_patient_records_morgan() -> dict[str, Any]:
    """Synthetic FHIR summary for demo patient 2 (Morgan Lee)."""
    return {
        "connected": True,
        "patient": {
            "name": "Morgan Lee",
            "birth_date": "1979-08-22",
            "gender": "female",
        },
        "conditions": [
            {
                "id": "demo2-cond-1",
                "code_display": "Herniated disc L4",
                "clinical_status": "active",
                "onset_date": "2023-01-15",
            },
            {
                "id": "demo2-cond-2",
                "code_display": "Lumbar radiculopathy",
                "clinical_status": "active",
                "onset_date": "2023-01-15",
            },
        ],
        "medications": [
            {
                "id": "demo2-med-1",
                "medication_display": "Ibuprofen 400 mg oral tablet",
                "status": "active",
                "dosage": "Take 1 tablet by mouth as needed for pain",
                "authored_on": "2023-02-01",
            },
            {
                "id": "demo2-med-2",
                "medication_display": "Cyclobenzaprine 5 mg oral tablet",
                "status": "active",
                "dosage": "Take 1 tablet by mouth at bedtime",
                "authored_on": "2023-02-01",
            },
        ],
        "allergies": [],
        "observations": [
            {
                "id": "demo2-obs-1",
                "code_display": "Blood pressure",
                "value": "118 / 74 mmHg",
                "effective_date": "2026-03-10",
            },
            {
                "id": "demo2-obs-2",
                "code_display": "Body weight",
                "value": "72 kg",
                "effective_date": "2026-03-10",
            },
        ],
        "last_synced": datetime.now(timezone.utc).isoformat(),
    }


def mock_patient_records() -> dict[str, Any]:
    """Return a realistic but synthetic FHIR summary for demo purposes.

    Called automatically when EPIC_CLIENT_ID is not set so the UI can show
    a fully populated Medical Records page without a live Epic sandbox.
    The patient matches the seeded demo account (Alex Rivera).
    """
    return {
        "connected": True,
        "patient": {
            "name": "Alex Rivera",
            "birth_date": "1987-03-14",
            "gender": "female",
        },
        "conditions": [
            {
                "id": "demo-cond-1",
                "code_display": "Essential hypertension",
                "clinical_status": "active",
                "onset_date": "2019-06-01",
            },
            {
                "id": "demo-cond-2",
                "code_display": "Type 2 diabetes mellitus",
                "clinical_status": "active",
                "onset_date": "2021-11-15",
            },
            {
                "id": "demo-cond-3",
                "code_display": "Seasonal allergic rhinitis",
                "clinical_status": "active",
                "onset_date": "2015-04-20",
            },
        ],
        "medications": [
            {
                "id": "demo-med-1",
                "medication_display": "Lisinopril 10 mg oral tablet",
                "status": "active",
                "dosage": "Take 1 tablet by mouth once daily",
                "authored_on": "2022-01-10",
            },
            {
                "id": "demo-med-2",
                "medication_display": "Metformin 500 mg oral tablet",
                "status": "active",
                "dosage": "Take 1 tablet by mouth twice daily with meals",
                "authored_on": "2021-11-20",
            },
        ],
        "allergies": [
            {
                "id": "demo-allergy-1",
                "substance_display": "Penicillin",
                "criticality": "high",
                "reaction": "Anaphylaxis",
            },
        ],
        "observations": [
            {
                "id": "demo-obs-1",
                "code_display": "Blood pressure",
                "value": "128 / 82 mmHg",
                "effective_date": "2026-03-10",
            },
            {
                "id": "demo-obs-2",
                "code_display": "Body weight",
                "value": "68 kg",
                "effective_date": "2026-03-10",
            },
            {
                "id": "demo-obs-3",
                "code_display": "Hemoglobin A1c",
                "value": "7.1 %",
                "effective_date": "2026-02-28",
            },
        ],
        "last_synced": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# FHIR resource fetchers
# ---------------------------------------------------------------------------

async def fetch_patient_records(
    access_token: str,
    epic_patient_id: str,
) -> dict[str, Any]:
    """Fetch a summary of FHIR R4 resources for the patient.

    Returns a dict with keys: patient, conditions, medications, allergies,
    observations.  Any resource that fails to fetch is returned as an empty
    list rather than raising.
    """
    base = _fhir_r4_base()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/fhir+json",
    }

    async def _get(url: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            return r.json()

    async def _bundle_entries(url: str, params: dict | None = None) -> list[dict]:
        try:
            bundle = await _get(url, params)
            return [e["resource"] for e in bundle.get("entry", []) if "resource" in e]
        except Exception as exc:
            logger.warning("FHIR fetch failed for %s: %s", url, exc)
            return []

    # Patient demographics
    patient_demo: dict = {}
    try:
        raw = await _get(f"{base}/Patient/{epic_patient_id}")
        name_parts = raw.get("name", [{}])[0]
        given = " ".join(name_parts.get("given", []))
        family = name_parts.get("family", "")
        patient_demo = {
            "name": f"{given} {family}".strip() or None,
            "birth_date": raw.get("birthDate"),
            "gender": raw.get("gender"),
        }
    except Exception as exc:
        logger.warning("FHIR Patient fetch failed: %s", exc)

    # Active conditions
    raw_conditions = await _bundle_entries(
        f"{base}/Condition",
        {"patient": epic_patient_id, "clinical-status": "active"},
    )
    conditions = [
        {
            "id": r.get("id", ""),
            "code_display": _coding_display(r.get("code")),
            "clinical_status": (
                r.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "")
            ),
            "onset_date": r.get("onsetDateTime", r.get("onsetPeriod", {}).get("start")),
        }
        for r in raw_conditions
        if _coding_display(r.get("code"))
    ]

    # Active medication requests
    raw_meds = await _bundle_entries(
        f"{base}/MedicationRequest",
        {"patient": epic_patient_id, "status": "active"},
    )
    medications = [
        {
            "id": r.get("id", ""),
            "medication_display": _coding_display(
                r.get("medicationCodeableConcept")
                or r.get("contained", [{}])[0].get("code")
            ),
            "status": r.get("status", ""),
            "dosage": (r.get("dosageInstruction") or [{}])[0].get("text"),
            "authored_on": r.get("authoredOn"),
        }
        for r in raw_meds
        if _coding_display(r.get("medicationCodeableConcept"))
    ]

    # Allergies
    raw_allergies = await _bundle_entries(
        f"{base}/AllergyIntolerance",
        {"patient": epic_patient_id},
    )
    allergies = [
        {
            "id": r.get("id", ""),
            "substance_display": _coding_display(r.get("code")),
            "criticality": r.get("criticality"),
            "reaction": (
                _coding_display(
                    (r.get("reaction") or [{}])[0]
                    .get("manifestation", [{}])[0]
                )
                or None
            ),
        }
        for r in raw_allergies
        if _coding_display(r.get("code"))
    ]

    # Recent vital-sign observations
    raw_obs = await _bundle_entries(
        f"{base}/Observation",
        {
            "patient": epic_patient_id,
            "category": "vital-signs",
            "_sort": "-date",
            "_count": "8",
        },
    )
    observations = []
    for r in raw_obs:
        display = _coding_display(r.get("code"))
        if not display:
            continue
        # Simple scalar value
        vq = r.get("valueQuantity")
        value = (
            f"{vq.get('value')} {vq.get('unit', '')}".strip()
            if vq
            else r.get("valueString", "")
        )
        # BP and similar: components
        if not value and r.get("component"):
            parts = []
            for comp in r["component"]:
                cvq = comp.get("valueQuantity", {})
                parts.append(f"{cvq.get('value', '')} {cvq.get('unit', '')}".strip())
            value = " / ".join(p for p in parts if p)
        if value:
            observations.append({
                "id": r.get("id", ""),
                "code_display": display,
                "value": value,
                "effective_date": r.get("effectiveDateTime"),
            })

    return {
        "connected": True,
        "patient": patient_demo or None,
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies,
        "observations": observations,
        "last_synced": datetime.now(timezone.utc).isoformat(),
    }
