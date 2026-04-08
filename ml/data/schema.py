"""Output schema for the Phase 2 training dataset.

Each row is one patient intake / clinical encounter.

Columns
-------
source          : "mtsamples" | "synthea"
source_id       : original row identifier from the source
raw_text        : chief complaint or intake free-text (patient language)
extracted_features : JSON string — output of SymptomExtractor
                    {
                      "symptoms": [{"symptom_name": str, "severity": str,
                                    "duration_mentioned": str|null,
                                    "body_location": str|null}],
                      "symptom_names": [str],   # flat list for convenience
                      "has_red_flags": bool
                    }
triage_cluster  : one of the clusters defined in config.yaml, or "other"
specialty       : original specialty label from the source (audit trail)
split           : "train" | "val" | "test"
"""

from dataclasses import dataclass


TRIAGE_CLUSTERS = [
    "cardiac",
    "respiratory",
    "neurological",
    "musculoskeletal",
    "gastrointestinal",
    "mental_health",
    "dermatological",
    "preventive",
    "other",
]

SCHEMA_COLUMNS = [
    "source",
    "source_id",
    "raw_text",
    "extracted_features",
    "triage_cluster",
    "specialty",
    "split",
]


@dataclass
class TrainingRow:
    source: str
    source_id: str
    raw_text: str
    extracted_features: str  # JSON
    triage_cluster: str
    specialty: str
    split: str = "unassigned"
