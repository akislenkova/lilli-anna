#!/usr/bin/env python3
"""Triage cluster classifier — training script.

Trains a Random Forest on the prepared parquet dataset and reports
per-class precision/recall/F1 plus overall accuracy on val and test sets.

Usage
-----
    python ml/train.py                       # default paths
    python ml/train.py --data-dir ml/output  # explicit data dir
    python ml/train.py --n-estimators 300    # tune tree count

Output
------
    ml/output/model.joblib      — serialised RandomForestClassifier
    ml/output/metrics.json      — val + test metrics (cite-able)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import MultiLabelBinarizer
from scipy.sparse import hstack, csr_matrix

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Ordered class list (excludes "other" — filtered out by pipeline.py)
TRIAGE_CLUSTERS = [
    "cardiac",
    "dermatological",
    "gastrointestinal",
    "mental_health",
    "musculoskeletal",
    "neurological",
    "preventive",
    "respiratory",
]


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _parse_features(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the extracted_features JSON column into flat fields."""
    parsed = df["extracted_features"].apply(
        lambda s: json.loads(s) if isinstance(s, str) else s
    )
    df = df.copy()
    df["symptom_names"]       = parsed.apply(lambda x: x.get("symptom_names", []))
    df["has_red_flags"]       = parsed.apply(lambda x: int(x.get("has_red_flags", False)))
    df["red_flag_count"]      = parsed.apply(
        lambda x: len(x.get("red_flag_severities", []))
    )
    df["has_critical_flag"]   = parsed.apply(
        lambda x: int("critical" in x.get("red_flag_severities", []))
    )
    df["has_high_flag"]       = parsed.apply(
        lambda x: int("high" in x.get("red_flag_severities", []))
    )
    return df


def _build_feature_matrix(
    df: pd.DataFrame,
    mlb: MultiLabelBinarizer | None = None,
    tfidf: TfidfVectorizer | None = None,
    fit: bool = False,
):
    """Return (X_sparse, fitted_mlb, fitted_tfidf).

    Combines three feature groups:
    - TF-IDF on raw_text (up to 3000 unigram+bigram features, sublinear TF)
    - Multi-hot symptom indicators
    - 4 scalar red-flag features

    Parameters
    ----------
    df      : DataFrame with raw_text, symptom_names + scalar columns parsed.
    mlb     : pre-fitted MultiLabelBinarizer; None if ``fit=True``.
    tfidf   : pre-fitted TfidfVectorizer; None if ``fit=True``.
    fit     : if True, fit mlb and tfidf on this split.
    """
    if mlb is None:
        mlb = MultiLabelBinarizer(sparse_output=False)
    if tfidf is None:
        tfidf = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=3000,
            sublinear_tf=True,
            min_df=2,
        )

    if fit:
        symptom_arr = mlb.fit_transform(df["symptom_names"])
        text_arr = tfidf.fit_transform(df["raw_text"].fillna(""))
    else:
        symptom_arr = mlb.transform(df["symptom_names"])
        text_arr = tfidf.transform(df["raw_text"].fillna(""))

    scalar_arr = csr_matrix(
        df[["has_red_flags", "red_flag_count", "has_critical_flag", "has_high_flag"]].values
    )

    X = hstack([text_arr, csr_matrix(symptom_arr), scalar_arr])
    return X, mlb, tfidf


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def _evaluate(
    clf: RandomForestClassifier,
    X,
    y: pd.Series,
    split_name: str,
) -> dict:
    preds = clf.predict(X)
    acc = accuracy_score(y, preds)
    report = classification_report(
        y,
        preds,
        labels=TRIAGE_CLUSTERS,
        output_dict=True,
        zero_division=0,
    )

    # Pretty-print
    print(f"\n{'─'*52}")
    print(f"  {split_name.upper()} SET  (n={len(y)})")
    print(f"{'─'*52}")
    print(f"  Overall accuracy : {acc:.4f}  ({acc*100:.1f}%)")
    print(f"\n  {'Class':<22} {'Prec':>6} {'Rec':>6} {'F1':>6} {'N':>6}")
    print(f"  {'─'*22} {'─'*6} {'─'*6} {'─'*6} {'─'*6}")
    for cls in TRIAGE_CLUSTERS:
        r = report.get(cls, {})
        print(
            f"  {cls:<22} {r.get('precision', 0):>6.3f} "
            f"{r.get('recall', 0):>6.3f} {r.get('f1-score', 0):>6.3f} "
            f"{int(r.get('support', 0)):>6}"
        )
    macro = report.get("macro avg", {})
    print(
        f"\n  {'macro avg':<22} {macro.get('precision', 0):>6.3f} "
        f"{macro.get('recall', 0):>6.3f} {macro.get('f1-score', 0):>6.3f}"
    )
    print(f"{'─'*52}\n")

    return {
        "accuracy": round(acc, 4),
        "per_class": {
            cls: {
                "precision": round(report.get(cls, {}).get("precision", 0), 4),
                "recall":    round(report.get(cls, {}).get("recall", 0), 4),
                "f1":        round(report.get(cls, {}).get("f1-score", 0), 4),
                "support":   int(report.get(cls, {}).get("support", 0)),
            }
            for cls in TRIAGE_CLUSTERS
        },
        "macro_avg": {
            "precision": round(macro.get("precision", 0), 4),
            "recall":    round(macro.get("recall", 0), 4),
            "f1":        round(macro.get("f1-score", 0), 4),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train triage cluster classifier")
    parser.add_argument(
        "--data-dir",
        default="ml/output",
        help="Directory containing train/val/test parquet files (default: ml/output)",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=200,
        help="Number of trees in the Random Forest (default: 200)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Max tree depth; None = grow until pure (default: None)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    # Resolve data_dir relative to project root (works when invoked from any cwd)
    _script_dir = Path(__file__).parent
    data_dir = (_script_dir / args.data_dir) if not Path(args.data_dir).is_absolute() else Path(args.data_dir)
    # Also try direct path if the default relative path doesn't resolve
    if not data_dir.exists():
        data_dir = _script_dir / "output"

    for fname in ("train.parquet", "val.parquet", "test.parquet"):
        if not (data_dir / fname).exists():
            logger.error(
                "Missing %s — run `python ml/pipeline.py` first.", data_dir / fname
            )
            sys.exit(1)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    logger.info("Loading data from %s …", data_dir)
    train_df = pd.read_parquet(data_dir / "train.parquet")
    val_df   = pd.read_parquet(data_dir / "val.parquet")
    test_df  = pd.read_parquet(data_dir / "test.parquet")

    for split, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        logger.info("  %s: %d rows, clusters: %s", split, len(df),
                    dict(df["triage_cluster"].value_counts()))

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------
    logger.info("Parsing extracted_features …")
    train_df = _parse_features(train_df)
    val_df   = _parse_features(val_df)
    test_df  = _parse_features(test_df)

    logger.info("Building feature matrices …")
    X_train, mlb, tfidf = _build_feature_matrix(train_df, fit=True)
    X_val,   _,   _     = _build_feature_matrix(val_df,   mlb=mlb, tfidf=tfidf, fit=False)
    X_test,  _,   _     = _build_feature_matrix(test_df,  mlb=mlb, tfidf=tfidf, fit=False)

    y_train = train_df["triage_cluster"]
    y_val   = val_df["triage_cluster"]
    y_test  = test_df["triage_cluster"]

    logger.info(
        "Feature matrix: %d train rows × %d features "
        "(%d TF-IDF + %d symptom indicators + 4 scalar)",
        X_train.shape[0], X_train.shape[1], len(tfidf.vocabulary_), len(mlb.classes_),
    )

    # ------------------------------------------------------------------
    # Train
    # ------------------------------------------------------------------
    logger.info(
        "Training RandomForest (n_estimators=%d, max_depth=%s, class_weight=balanced) …",
        args.n_estimators, args.max_depth,
    )
    clf = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        class_weight="balanced",   # counteracts respiratory/mental_health dominance
        random_state=args.seed,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    logger.info("Training complete.")

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------
    val_metrics  = _evaluate(clf, X_val,  y_val,  "validation")
    test_metrics = _evaluate(clf, X_test, y_test, "test")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    model_path   = data_dir / "model.joblib"
    metrics_path = data_dir / "metrics.json"

    joblib.dump({"classifier": clf, "mlb": mlb, "tfidf": tfidf}, model_path)
    logger.info("Model saved → %s", model_path)

    metrics = {
        "model": "RandomForestClassifier",
        "hyperparameters": {
            "n_estimators": args.n_estimators,
            "max_depth": args.max_depth,
            "class_weight": "balanced",
            "random_seed": args.seed,
        },
        "training_rows": X_train.shape[0],
        "feature_count": X_train.shape[1],
        "validation": val_metrics,
        "test": test_metrics,
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Metrics saved → %s", metrics_path)

    # Print headline numbers
    print("── Headline metrics ──────────────────────────────")
    print(f"  Val  accuracy : {val_metrics['accuracy']*100:.1f}%"
          f"  |  macro F1 : {val_metrics['macro_avg']['f1']*100:.1f}%")
    print(f"  Test accuracy : {test_metrics['accuracy']*100:.1f}%"
          f"  |  macro F1 : {test_metrics['macro_avg']['f1']*100:.1f}%")
    print("──────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
