#!/usr/bin/env python3
"""Phase 2 training data pipeline.

Pulls MTSamples and/or Synthea data, runs feature extraction using the
existing SymptomExtractor, maps to triage clusters, and writes a train/val/test
parquet (or CSV) dataset.

Usage
-----
    # Both sources
    python ml/pipeline.py

    # MTSamples only
    python ml/pipeline.py --source mtsamples

    # Synthea only
    python ml/pipeline.py --source synthea

    # Output as CSV instead of parquet
    python ml/pipeline.py --format csv

Output
------
    ml/output/train.parquet
    ml/output/val.parquet
    ml/output/test.parquet
    ml/output/stats.json   — cluster distribution and row counts

Schema (per row)
----------------
    source              "mtsamples" | "synthea"
    source_id           original row ID
    raw_text            chief complaint / intake free-text
    extracted_features  JSON — SymptomExtractor output
    triage_cluster      one of 8 clusters or "other"
    specialty           original specialty label (audit trail)
    split               "train" | "val" | "test"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
from sklearn.model_selection import train_test_split
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Make the backend and ml packages importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
_BACKEND_PATH = _PROJECT_ROOT / "backend"
for _p in (_PROJECT_ROOT, _BACKEND_PATH):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.ai.symptom_extractor import SymptomExtractor  # noqa: E402
from app.ai.question_engine import QuestionEngine       # noqa: E402

from ml.data.processing.cluster_mapper import ClusterMapper   # noqa: E402
from ml.data.schema import TrainingRow, SCHEMA_COLUMNS        # noqa: E402

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

_extractor = SymptomExtractor()
_engine = QuestionEngine()


def extract_features(text: str) -> str:
    """Run SymptomExtractor + red-flag check; return JSON string."""
    symptoms = _extractor.extract(text)
    symptom_names = [s.symptom_name for s in symptoms]
    red_flags = _engine.check_red_flags(symptom_names, {})

    features = {
        "symptoms": [
            {
                "symptom_name": s.symptom_name,
                "severity": s.severity,
                "duration_mentioned": s.duration_mentioned,
                "body_location": s.body_location,
            }
            for s in symptoms
        ],
        "symptom_names": symptom_names,
        "has_red_flags": len(red_flags) > 0,
        "red_flag_severities": [f.severity for f in red_flags],
    }
    return json.dumps(features)


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------

def _load_mtsamples(cfg: dict, mapper: ClusterMapper) -> list[TrainingRow]:
    from ml.data.sources.mtsamples import load as load_mtsamples

    csv_path = _PROJECT_ROOT / cfg["paths"]["mtsamples_csv"]
    df = load_mtsamples(csv_path)

    rows: list[TrainingRow] = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="MTSamples"):
        features_json = extract_features(row["raw_text"])
        symptom_names = json.loads(features_json)["symptom_names"]
        cluster = mapper.resolve(
            symptom_names=symptom_names,
            specialty=row.get("specialty", ""),
        )
        rows.append(TrainingRow(
            source="mtsamples",
            source_id=row["source_id"],
            raw_text=row["raw_text"],
            extracted_features=features_json,
            triage_cluster=cluster,
            specialty=row.get("specialty", ""),
        ))
    return rows


def _load_synthea(cfg: dict, mapper: ClusterMapper) -> list[TrainingRow]:
    from ml.data.sources.synthea import load as load_synthea

    synthea_dir = _PROJECT_ROOT / cfg["paths"]["synthea_output"]
    df = load_synthea(synthea_dir)

    rows: list[TrainingRow] = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Synthea"):
        features_json = extract_features(row["raw_text"])
        symptom_names = json.loads(features_json)["symptom_names"]
        cluster = mapper.resolve(
            symptom_names=symptom_names,
            specialty=row.get("specialty", ""),
            description=row.get("condition_description", ""),
        )
        rows.append(TrainingRow(
            source="synthea",
            source_id=row["source_id"],
            raw_text=row["raw_text"],
            extracted_features=features_json,
            triage_cluster=cluster,
            specialty=row.get("specialty", ""),
        ))
    return rows


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def _assign_splits(
    df: pd.DataFrame,
    train: float,
    val: float,
    seed: int,
) -> pd.DataFrame:
    """Stratified split by triage_cluster."""
    test = 1.0 - train - val

    train_df, temp_df = train_test_split(
        df,
        test_size=(val + test),
        stratify=df["triage_cluster"],
        random_state=seed,
    )
    val_df, test_df = train_test_split(
        temp_df,
        test_size=test / (val + test),
        stratify=temp_df["triage_cluster"],
        random_state=seed,
    )
    train_df = train_df.copy()
    val_df = val_df.copy()
    test_df = test_df.copy()

    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"

    return pd.concat([train_df, val_df, test_df], ignore_index=True)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _write_stats(df: pd.DataFrame, output_dir: Path) -> None:
    stats = {
        "total_rows": len(df),
        "by_split": df.groupby("split").size().to_dict(),
        "by_cluster": df.groupby("triage_cluster").size().to_dict(),
        "by_source": df.groupby("source").size().to_dict(),
        "cluster_by_split": (
            df.groupby(["split", "triage_cluster"])
            .size()
            .unstack(fill_value=0)
            .to_dict()
        ),
    }
    stats_path = output_dir / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info("Stats written to %s", stats_path)

    # Print summary
    print("\n── Dataset summary ──────────────────────────")
    print(f"  Total rows : {stats['total_rows']}")
    print(f"  By split   : {stats['by_split']}")
    print(f"  By cluster :")
    for cluster, count in sorted(stats["by_cluster"].items()):
        print(f"    {cluster:<20} {count}")
    print("─────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 2 training dataset")
    parser.add_argument(
        "--source",
        choices=["mtsamples", "synthea", "both"],
        default="both",
        help="Which data source(s) to include (default: both)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv"],
        default="parquet",
        help="Output format (default: parquet)",
    )
    args = parser.parse_args()

    cfg = _load_config()
    mapper = ClusterMapper()

    output_dir = _PROJECT_ROOT / cfg["output"]["path"]
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[TrainingRow] = []

    if args.source in ("mtsamples", "both"):
        try:
            all_rows.extend(_load_mtsamples(cfg, mapper))
        except FileNotFoundError as e:
            logger.warning("Skipping MTSamples: %s", e)

    if args.source in ("synthea", "both"):
        try:
            all_rows.extend(_load_synthea(cfg, mapper))
        except FileNotFoundError as e:
            logger.warning("Skipping Synthea: %s", e)

    if not all_rows:
        logger.error("No data loaded. Check that source files exist.")
        sys.exit(1)

    df = pd.DataFrame([vars(r) for r in all_rows])[SCHEMA_COLUMNS]
    logger.info("Total rows before filtering: %d", len(df))

    # Drop "other" — not a useful training label; model should abstain at
    # inference time rather than learn to predict a catch-all class.
    before = len(df)
    df = df[df["triage_cluster"] != "other"].reset_index(drop=True)
    logger.info("Dropped %d 'other' rows, %d remaining", before - len(df), len(df))

    # Assign train/val/test splits
    out_cfg = cfg["output"]
    df = _assign_splits(
        df,
        train=out_cfg["train_split"],
        val=out_cfg["val_split"],
        seed=out_cfg["random_seed"],
    )

    # Write output
    for split in ("train", "val", "test"):
        split_df = df[df["split"] == split]
        if args.format == "parquet":
            out_path = output_dir / f"{split}.parquet"
            split_df.to_parquet(out_path, index=False)
        else:
            out_path = output_dir / f"{split}.csv"
            split_df.to_csv(out_path, index=False)
        logger.info("Wrote %d rows to %s", len(split_df), out_path)

    _write_stats(df, output_dir)


if __name__ == "__main__":
    main()
