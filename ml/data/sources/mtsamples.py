"""Load and clean the MTSamples dataset.

MTSamples CSV can be obtained two ways:
  A) Kaggle (recommended):
       kaggle datasets download -d tboyle10/medicaltranscriptions
       unzip medicaltranscriptions.zip -d ml/data/raw/
  B) Manual download from Kaggle UI → save to ml/data/raw/mtsamples.csv

Expected columns: description, medical_specialty, sample_name,
                  transcription, keywords
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Specialties to skip — surgical/procedure notes, not useful for intake triage
_SKIP_SPECIALTIES = {
    "Surgery",
    "Radiology",
    "Pathology",
    "Lab Medicine - Pathology",
    "Consult - History and Phy.",
    "Discharge Summary",
    "SOAP / Chart / Progress Notes",
    "Letters",
    "Office Notes",
    "Autopsy",
    "Chiropractic",
    "Diets and Nutritions",
    "Hospice - Palliative Care",
}

_MIN_TEXT_LEN = 50  # drop rows with very short transcriptions


def load(csv_path: str | Path) -> pd.DataFrame:
    """Load MTSamples CSV and return a cleaned DataFrame.

    Returns columns: source_id, raw_text, specialty
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"MTSamples CSV not found at {path}.\n"
            "Download it with:\n"
            "  kaggle datasets download -d tboyle10/medicaltranscriptions\n"
            "  unzip medicaltranscriptions.zip -d ml/data/raw/\n"
            "Or download manually from Kaggle and save to ml/data/raw/mtsamples.csv"
        )

    df = pd.read_csv(path)
    logger.info("Loaded %d rows from MTSamples", len(df))

    # Normalise column names (kaggle download may have an index column)
    df.columns = [c.lower().strip() for c in df.columns]
    if "unnamed: 0" in df.columns:
        df = df.drop(columns=["unnamed: 0"])

    # Drop rows with missing transcription or specialty
    df = df.dropna(subset=["transcription", "medical_specialty"])

    # Filter out non-intake specialties
    df = df[~df["medical_specialty"].isin(_SKIP_SPECIALTIES)]

    # Drop very short texts
    df = df[df["transcription"].str.len() >= _MIN_TEXT_LEN]

    # Extract chief complaint from transcription when possible.
    # Many MTSamples notes start with "CHIEF COMPLAINT:" — use that as raw_text
    # if present; otherwise fall back to the description field.
    df["raw_text"] = df.apply(_extract_chief_complaint, axis=1)

    # Drop rows where we still couldn't get usable text
    df = df[df["raw_text"].str.len() >= _MIN_TEXT_LEN]

    df = df.reset_index(drop=True)
    df["source_id"] = "mtsamples_" + df.index.astype(str)

    logger.info("Retained %d rows after cleaning", len(df))

    return df[["source_id", "raw_text", "medical_specialty"]].rename(
        columns={"medical_specialty": "specialty"}
    )


def _extract_chief_complaint(row: pd.Series) -> str:
    """Pull chief complaint section if present; else use description."""
    text: str = row.get("transcription", "") or ""

    # Look for CHIEF COMPLAINT section
    lower = text.lower()
    for marker in ("chief complaint:", "chief complaint\n", "cc:", "reason for visit:"):
        idx = lower.find(marker)
        if idx != -1:
            start = idx + len(marker)
            # Take up to the next section header or 500 chars
            excerpt = text[start:start + 500].strip()
            # Truncate at next all-caps section header
            for line in excerpt.split("\n"):
                stripped = line.strip()
                if stripped and stripped == stripped.upper() and len(stripped) > 5:
                    break
                return stripped if stripped else excerpt[:200]

    # Fall back to description (shorter, more like a chief complaint)
    description = str(row.get("description", "")).strip()
    if len(description) >= _MIN_TEXT_LEN:
        return description

    # Last resort: first 300 chars of transcription
    return text[:300].strip()
