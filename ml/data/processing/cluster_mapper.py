"""Maps specialty labels and extracted symptoms to triage clusters.

Priority order:
  1. Symptom-based match  — if extracted symptoms map to a single dominant cluster
  2. Specialty-based match — MTSamples medical_specialty or Synthea description keywords
  3. Fallback             — "other"
"""
from __future__ import annotations

import yaml
from pathlib import Path


def _load_config() -> dict:
    config_path = Path(__file__).parents[2] / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class ClusterMapper:
    """Maps specialty strings and symptom lists to triage clusters."""

    def __init__(self) -> None:
        cfg = _load_config()
        self._clusters: dict[str, dict] = cfg["triage_clusters"]

        # Build reverse lookups
        self._specialty_to_cluster: dict[str, str] = {}
        self._symptom_to_clusters: dict[str, list[str]] = {}

        for cluster_name, cluster_cfg in self._clusters.items():
            for spec in cluster_cfg.get("mtsamples_specialties", []):
                self._specialty_to_cluster[spec.lower()] = cluster_name
            for symptom in cluster_cfg.get("symptoms", []):
                self._symptom_to_clusters.setdefault(symptom, []).append(cluster_name)

    def from_specialty(self, specialty: str) -> str:
        """Map an MTSamples medical_specialty string to a triage cluster."""
        return self._specialty_to_cluster.get(specialty.lower().strip(), "other")

    def from_symptoms(self, symptom_names: list[str]) -> str:
        """Map a list of canonical symptom names to the most likely triage cluster."""
        if not symptom_names:
            return "other"

        scores: dict[str, int] = {}
        for sym in symptom_names:
            for cluster in self._symptom_to_clusters.get(sym, []):
                scores[cluster] = scores.get(cluster, 0) + 1

        if not scores:
            return "other"
        return max(scores, key=lambda c: scores[c])

    def from_synthea_description(self, description: str) -> str:
        """Map a Synthea condition/encounter description to a triage cluster."""
        desc_lower = str(description).lower() if description and description == description else ""
        scores: dict[str, int] = {}
        for cluster_name, cluster_cfg in self._clusters.items():
            for kw in cluster_cfg.get("synthea_keywords", []):
                if kw.lower() in desc_lower:
                    scores[cluster_name] = scores.get(cluster_name, 0) + 1

        if not scores:
            return "other"
        return max(scores, key=lambda c: scores[c])

    def resolve(
        self,
        symptom_names: list[str],
        specialty: str = "",
        description: str = "",
    ) -> str:
        """Best-effort cluster resolution using all available signals.

        Symptom-based match wins if unambiguous; falls back to specialty,
        then description keywords, then 'other'.
        """
        # Try symptoms first
        symptom_cluster = self.from_symptoms(symptom_names)
        if symptom_cluster != "other":
            return symptom_cluster

        # Try specialty label
        if specialty:
            spec_cluster = self.from_specialty(specialty)
            if spec_cluster != "other":
                return spec_cluster

        # Try description keywords (Synthea)
        if description:
            return self.from_synthea_description(description)

        return "other"
