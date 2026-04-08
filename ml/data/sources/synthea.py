"""Load and clean Synthea CSV output.

Generate Synthea data:
  1. Download:  https://github.com/synthetichealth/synthea/releases
                → synthea-with-dependencies.jar
  2. Run:
       java -jar synthea-with-dependencies.jar \
         -p 5000 \
         --exporter.csv.export=true \
         --exporter.fhir.export=false \
         -o ml/data/raw/synthea

  This produces ml/data/raw/synthea/csv/ with encounters.csv,
  conditions.csv, patients.csv, etc.

We join encounters + conditions to get one row per encounter with:
  - chief complaint (encounter REASONDESCRIPTION)
  - primary condition description (conditions.DESCRIPTION)
  - encounter class (ambulatory / wellness / urgentcare / emergency)
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Only keep encounter classes relevant to primary-care scheduling
_KEEP_ENCOUNTER_CLASSES = {
    "ambulatory",
    "wellness",
    "urgentcare",
    "outpatient",
    "virtual",
}

_MIN_TEXT_LEN = 10


def load(synthea_csv_dir: str | Path) -> pd.DataFrame:
    """Load Synthea CSV output and return a cleaned DataFrame.

    Returns columns: source_id, raw_text, specialty
    (specialty is set to the encounter class for downstream cluster mapping)
    """
    csv_dir = Path(synthea_csv_dir)
    if not csv_dir.exists():
        raise FileNotFoundError(
            f"Synthea CSV directory not found at {csv_dir}.\n"
            "Generate it with:\n"
            "  java -jar synthea-with-dependencies.jar -p 5000 "
            "--exporter.csv.export=true -o ml/data/raw/synthea"
        )

    encounters_path = csv_dir / "encounters.csv"
    conditions_path = csv_dir / "conditions.csv"

    if not encounters_path.exists():
        raise FileNotFoundError(f"encounters.csv not found in {csv_dir}")

    encounters = pd.read_csv(encounters_path, low_memory=False)
    encounters.columns = [c.lower().strip() for c in encounters.columns]
    logger.info("Loaded %d Synthea encounters", len(encounters))

    # Filter to relevant encounter classes
    if "encounterclass" in encounters.columns:
        encounters = encounters[
            encounters["encounterclass"].str.lower().isin(_KEEP_ENCOUNTER_CLASSES)
        ]

    # Join conditions if available — adds primary condition per encounter
    if conditions_path.exists():
        conditions = pd.read_csv(conditions_path, low_memory=False)
        conditions.columns = [c.lower().strip() for c in conditions.columns]

        # One condition per encounter (take the first/most recent)
        conditions_deduped = (
            conditions
            .sort_values("start", ascending=False)
            .groupby("encounter")
            .first()
            .reset_index()[["encounter", "description"]]
            .rename(columns={"description": "condition_description"})
        )
        encounters = encounters.merge(
            conditions_deduped,
            left_on="id",
            right_on="encounter",
            how="left",
        )
    else:
        encounters["condition_description"] = ""
        logger.warning("conditions.csv not found — condition descriptions unavailable")

    # Build raw_text: prefer REASONDESCRIPTION (chief complaint equivalent),
    # fall back to condition_description
    reason_col = next(
        (c for c in encounters.columns if "reason" in c and "description" in c), None
    )
    if reason_col:
        encounters["raw_text"] = encounters[reason_col].fillna(
            encounters.get("condition_description", "")
        )
    else:
        encounters["raw_text"] = encounters.get("condition_description", "")

    encounters["raw_text"] = encounters["raw_text"].fillna("").astype(str)

    # Drop rows with no usable text
    encounters = encounters[encounters["raw_text"].str.len() >= _MIN_TEXT_LEN]

    # specialty = encounter class (used by ClusterMapper as a weak signal)
    class_col = next((c for c in encounters.columns if "encounterclass" in c), None)
    encounters["specialty"] = (
        encounters[class_col].str.lower() if class_col else "ambulatory"
    )

    encounters = encounters.reset_index(drop=True)
    encounters["source_id"] = "synthea_" + encounters.index.astype(str)

    logger.info("Retained %d Synthea encounters after cleaning", len(encounters))

    return encounters[["source_id", "raw_text", "specialty", "condition_description"]].copy()
