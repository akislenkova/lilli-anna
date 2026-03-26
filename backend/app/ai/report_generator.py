"""
Anilla AI Report Generator
============================

Generates structured clinical reports from intake session data. Produces
two views:

- **Nurse summary** -- concise, action-oriented, no diagnostic probabilities.
- **Physician full report** -- includes differential diagnosis ranking,
  confidence scores, medication interactions, and complexity assessment.

All output is structured data (dataclasses + formatted strings), never
raw LLM text, so it can be reliably stored, displayed, and audited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.ai.knowledge_base import (
    MEDICATION_INTERACTION_FLAGS,
    SYMPTOM_CONDITION_MAP,
)
from backend.app.ai.question_engine import QuestionEngine, RedFlag
from backend.app.ai.time_estimator import EstimationContext, TimeEstimator


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DiagnosisProbability:
    """A single candidate diagnosis with its confidence and reasoning."""

    condition: str
    confidence: float
    reasoning: str


@dataclass
class MedicationInteraction:
    """A detected potential medication interaction."""

    drugs: list[str]
    severity: str  # "critical" | "high" | "moderate"
    description: str
    recommendation: str


@dataclass
class GeneratedReport:
    """Complete report output from a session analysis."""

    probable_diagnoses: list[DiagnosisProbability] = field(default_factory=list)
    """Ranked list of candidate diagnoses (physician-only)."""

    suggested_duration: int = 20
    """Recommended appointment duration in minutes."""

    confidence: float = 0.5
    """Overall confidence in the duration estimate (0-1)."""

    duration_range: tuple[int, int] = (15, 25)
    """(min, max) range for appointment duration."""

    red_flags: list[RedFlag] = field(default_factory=list)
    """Matched red-flag patterns from the session."""

    complexity_score: float = 0.0
    """Visit complexity score (0-1). Used for scheduling and billing guidance."""

    medication_interactions: list[MedicationInteraction] = field(default_factory=list)
    """Detected potential drug interactions."""

    summary: str = ""
    """Nurse-visible summary (no diagnostic details)."""

    full_report: str = ""
    """Physician-visible full report with diagnostic probabilities."""


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """
    Generates clinical intake reports by synthesizing symptom extraction,
    question-engine results, time estimation, and knowledge-base lookups.

    Example::

        generator = ReportGenerator()
        report = generator.generate_report(
            session=session_context,
            symptoms=["headache", "nausea"],
            answers={"mi_one_side": True, "mi_nausea": True},
            patient_profile={"age": 35, "medications": ["sumatriptan"]},
        )
        print(report.summary)
    """

    def __init__(self) -> None:
        self._question_engine = QuestionEngine()
        self._time_estimator = TimeEstimator()

    def generate_report(
        self,
        session: Any,
        symptoms: list[str],
        answers: dict[str, Any],
        patient_profile: dict[str, Any],
    ) -> GeneratedReport:
        """
        Generate a complete intake report.

        Parameters
        ----------
        session : SessionContext (or compatible dict)
            The intake session state.
        symptoms : list[str]
            Canonical symptom names extracted during the session.
        answers : dict[str, Any]
            All question answers collected during intake.
        patient_profile : dict[str, Any]
            Patient demographic and medical data. Expected keys:
            ``age``, ``is_new_patient``, ``medications`` (list[str]),
            ``chronic_conditions`` (list[str]),
            ``historical_durations`` (list[float]),
            ``physician_feedback`` (list[str]).

        Returns
        -------
        GeneratedReport
        """
        # 1. Build diagnosis probabilities
        diagnoses = self._build_diagnoses(symptoms, answers)

        # 2. Check red flags
        red_flags = self._question_engine.check_red_flags(symptoms, answers)

        # 3. Check medication interactions
        medications = patient_profile.get("medications", [])
        interactions = self.check_medication_interactions(medications, symptoms)

        # 4. Calculate complexity
        chronic_conditions = patient_profile.get("chronic_conditions", [])
        age = patient_profile.get("age")
        complexity = self.calculate_complexity_score(
            concerns_count=len(symptoms),
            medication_count=len(medications),
            chronic_conditions=len(chronic_conditions),
            age=age,
            red_flags=red_flags,
        )

        # 5. Estimate duration
        concerns = [{"name": s, "severity": "moderate"} for s in symptoms]
        est_ctx = EstimationContext(
            visit_type="new_patient_intake" if patient_profile.get("is_new_patient") else "specific_concern",
            concerns=concerns,
            patient_age=age,
            is_new_patient=patient_profile.get("is_new_patient", False),
            medication_count=len(medications),
            chronic_condition_count=len(chronic_conditions),
            historical_durations=patient_profile.get("historical_durations", []),
            physician_feedback_history=patient_profile.get("physician_feedback", []),
        )
        time_est = self._time_estimator.estimate(est_ctx)

        # 6. Assemble report
        report = GeneratedReport(
            probable_diagnoses=diagnoses,
            suggested_duration=time_est.recommended_minutes,
            confidence=time_est.confidence,
            duration_range=(time_est.range_min, time_est.range_max),
            red_flags=red_flags,
            complexity_score=complexity,
            medication_interactions=interactions,
        )

        # 7. Generate text summaries
        report.summary = self.generate_summary(report)
        report.full_report = self.generate_full_report(report)

        return report

    # ------------------------------------------------------------------
    # Summary generators
    # ------------------------------------------------------------------

    def generate_summary(self, report: GeneratedReport) -> str:
        """
        Generate a nurse-visible summary.

        This summary is action-oriented and does NOT include diagnostic
        probabilities or confidence scores. It focuses on:
        - Red flags requiring immediate attention
        - Suggested appointment duration
        - Medication interaction warnings
        - Visit complexity level

        Parameters
        ----------
        report : GeneratedReport

        Returns
        -------
        str
            Formatted plain-text summary suitable for display in a nurse dashboard.
        """
        lines: list[str] = []
        lines.append("=== INTAKE SUMMARY (Nurse View) ===")
        lines.append("")

        # Red flags
        if report.red_flags:
            lines.append("** RED FLAGS **")
            for rf in report.red_flags:
                lines.append(f"  [{rf.severity.upper()}] {rf.trigger_description}")
                if rf.action:
                    lines.append(f"    Action: {rf.action}")
            lines.append("")

        # Duration
        lo, hi = report.duration_range
        lines.append(f"Suggested appointment duration: {report.suggested_duration} min (range: {lo}-{hi} min)")

        # Complexity
        complexity_label = self._complexity_label(report.complexity_score)
        lines.append(f"Visit complexity: {complexity_label} ({report.complexity_score:.2f})")
        lines.append("")

        # Medication interactions
        if report.medication_interactions:
            lines.append("Medication interaction alerts:")
            for ix in report.medication_interactions:
                lines.append(f"  [{ix.severity.upper()}] {' + '.join(ix.drugs)}: {ix.description}")
                lines.append(f"    Recommendation: {ix.recommendation}")
            lines.append("")

        # Concern count
        concern_count = len(report.probable_diagnoses)
        lines.append(f"Number of concerns identified: {concern_count}")

        return "\n".join(lines)

    def generate_full_report(self, report: GeneratedReport) -> str:
        """
        Generate a physician-visible full report.

        Includes everything in the nurse summary plus:
        - Ranked differential diagnoses with confidence and reasoning
        - Detailed complexity breakdown

        Parameters
        ----------
        report : GeneratedReport

        Returns
        -------
        str
            Formatted plain-text report for physician review.
        """
        lines: list[str] = []
        lines.append("=== FULL INTAKE REPORT (Physician View) ===")
        lines.append("")

        # Red flags (same as nurse view)
        if report.red_flags:
            lines.append("** RED FLAGS **")
            for rf in report.red_flags:
                lines.append(f"  [{rf.severity.upper()}] {rf.trigger_description}")
                if rf.action:
                    lines.append(f"    Action: {rf.action}")
            lines.append("")

        # Differential diagnosis
        lines.append("DIFFERENTIAL DIAGNOSIS (ranked by probability):")
        if report.probable_diagnoses:
            for i, dx in enumerate(report.probable_diagnoses, 1):
                pct = dx.confidence * 100
                lines.append(f"  {i}. {dx.condition.replace('_', ' ').title()} "
                             f"({pct:.0f}% confidence)")
                lines.append(f"     Reasoning: {dx.reasoning}")
        else:
            lines.append("  No specific diagnoses identified from intake data.")
        lines.append("")

        # Duration
        lo, hi = report.duration_range
        lines.append(
            f"Suggested duration: {report.suggested_duration} min "
            f"(range: {lo}-{hi}, confidence: {report.confidence:.0%})"
        )

        # Complexity
        complexity_label = self._complexity_label(report.complexity_score)
        lines.append(f"Complexity score: {report.complexity_score:.2f} ({complexity_label})")
        lines.append("")

        # Medication interactions
        if report.medication_interactions:
            lines.append("MEDICATION INTERACTIONS:")
            for ix in report.medication_interactions:
                lines.append(f"  [{ix.severity.upper()}] {' + '.join(ix.drugs)}")
                lines.append(f"    {ix.description}")
                lines.append(f"    Recommendation: {ix.recommendation}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Medication interaction check
    # ------------------------------------------------------------------

    def check_medication_interactions(
        self,
        medications: list[str],
        symptoms: list[str],
    ) -> list[MedicationInteraction]:
        """
        Check a patient's medication list against known interaction patterns.

        Matching is case-insensitive and uses substring matching so that both
        generic names and common brand-name abbreviations can trigger a flag.
        Symptom data is used to surface interactions that may be *causing*
        the reported symptoms (e.g., NSAIDs + warfarin -> bleeding).

        Parameters
        ----------
        medications : list[str]
            Patient's current medications (names or drug classes).
        symptoms : list[str]
            Current symptom list for context-aware flagging.

        Returns
        -------
        list[MedicationInteraction]
            Detected interactions, sorted by severity (critical first).
        """
        if not medications:
            return []

        med_lower = [m.lower() for m in medications]
        interactions: list[MedicationInteraction] = []

        # Common drug-class keyword mappings for fuzzy matching
        class_keywords: dict[str, list[str]] = {
            "nsaid": ["ibuprofen", "naproxen", "diclofenac", "meloxicam", "celecoxib", "nsaid", "advil", "motrin", "aleve"],
            "ssri": ["sertraline", "fluoxetine", "paroxetine", "citalopram", "escitalopram", "ssri", "zoloft", "prozac", "lexapro", "paxil"],
            "maoi": ["phenelzine", "tranylcypromine", "selegiline", "isocarboxazid", "maoi", "nardil", "parnate"],
            "ace_inhibitor": ["lisinopril", "enalapril", "ramipril", "benazepril", "captopril", "ace inhibitor"],
            "beta_blocker": ["metoprolol", "atenolol", "propranolol", "carvedilol", "bisoprolol", "beta blocker"],
            "calcium_channel_blocker": ["amlodipine", "diltiazem", "verapamil", "nifedipine", "calcium channel blocker"],
            "statin": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin", "statin", "lipitor", "crestor"],
            "fibrate": ["gemfibrozil", "fenofibrate", "fibrate"],
            "opioid": ["oxycodone", "hydrocodone", "morphine", "fentanyl", "codeine", "tramadol", "opioid", "percocet", "vicodin"],
            "benzodiazepine": ["alprazolam", "lorazepam", "diazepam", "clonazepam", "benzodiazepine", "xanax", "ativan", "valium", "klonopin"],
            "warfarin": ["warfarin", "coumadin"],
            "aspirin": ["aspirin"],
            "potassium_supplement": ["potassium", "k-dur", "klor-con"],
            "spironolactone": ["spironolactone", "aldactone"],
            "metformin": ["metformin", "glucophage"],
            "lithium": ["lithium"],
            "digoxin": ["digoxin", "lanoxin"],
            "amiodarone": ["amiodarone", "cordarone"],
            "methotrexate": ["methotrexate"],
            "trimethoprim": ["trimethoprim", "bactrim", "sulfamethoxazole"],
            "clopidogrel": ["clopidogrel", "plavix"],
            "omeprazole": ["omeprazole", "prilosec"],
            "fluoroquinolone": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "fluoroquinolone", "cipro", "levaquin"],
            "antacid": ["antacid", "tums", "maalox", "calcium carbonate", "magnesium hydroxide"],
            "thyroid_hormone": ["levothyroxine", "synthroid", "thyroid"],
            "calcium_supplement": ["calcium supplement", "calcium citrate", "calcium carbonate", "caltrate", "os-cal"],
            "contrast_dye": ["contrast", "contrast dye"],
            "tramadol": ["tramadol", "ultram"],
        }

        def _patient_has(drug_class: str) -> bool:
            """Check if patient is taking a medication matching the drug class."""
            keywords = class_keywords.get(drug_class, [drug_class])
            return any(
                kw in med_text
                for kw in keywords
                for med_text in med_lower
            )

        for flag in MEDICATION_INTERACTION_FLAGS:
            drug_a, drug_b = flag["drugs"]
            if _patient_has(drug_a) and _patient_has(drug_b):
                interactions.append(MedicationInteraction(
                    drugs=flag["drugs"],
                    severity=flag["severity"],
                    description=flag["description"],
                    recommendation=flag["recommendation"],
                ))

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "moderate": 2}
        interactions.sort(key=lambda ix: severity_order.get(ix.severity, 3))
        return interactions

    # ------------------------------------------------------------------
    # Complexity scoring
    # ------------------------------------------------------------------

    def calculate_complexity_score(
        self,
        concerns_count: int,
        medication_count: int,
        chronic_conditions: int,
        age: int | None,
        red_flags: list[RedFlag],
    ) -> float:
        """
        Calculate a visit complexity score between 0.0 and 1.0.

        The score aggregates multiple dimensions of visit complexity and is
        used for scheduling optimization and billing-level guidance (E&M
        code selection support).

        Scoring rubric:
        - Concerns: 0.15 per concern (max contribution 0.45)
        - Medications: 0.02 per medication (max contribution 0.20)
        - Chronic conditions: 0.05 per condition (max contribution 0.25)
        - Age >= 65: +0.10
        - Red flags: +0.15 per critical, +0.10 per high, +0.05 per moderate

        Parameters
        ----------
        concerns_count : int
        medication_count : int
        chronic_conditions : int
        age : int | None
        red_flags : list[RedFlag]

        Returns
        -------
        float
            Complexity score clamped to [0.0, 1.0].
        """
        score = 0.0

        # Concerns
        score += min(0.45, concerns_count * 0.15)

        # Medications
        score += min(0.20, medication_count * 0.02)

        # Chronic conditions
        score += min(0.25, chronic_conditions * 0.05)

        # Age
        if age is not None and age >= 65:
            score += 0.10

        # Red flags
        rf_severity_weight = {"critical": 0.15, "high": 0.10, "moderate": 0.05}
        for rf in red_flags:
            score += rf_severity_weight.get(rf.severity, 0.05)

        return round(min(1.0, score), 2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_diagnoses(
        self,
        symptoms: list[str],
        answers: dict[str, Any],
    ) -> list[DiagnosisProbability]:
        """
        Build a ranked list of probable diagnoses from symptoms and answers.

        Uses the same scoring logic as QuestionEngine._rank_conditions but
        normalizes scores to produce a pseudo-probability.
        """
        from backend.app.ai.knowledge_base import CONDITION_QUESTIONS

        raw_scores: dict[str, float] = {}
        condition_symptoms: dict[str, list[str]] = {}

        for symptom in symptoms:
            for condition, prob in SYMPTOM_CONDITION_MAP.get(symptom, []):
                raw_scores[condition] = raw_scores.get(condition, 0.0) + prob
                condition_symptoms.setdefault(condition, []).append(symptom)

        # Adjust with answers
        for condition in list(raw_scores.keys()):
            for q in CONDITION_QUESTIONS.get(condition, []):
                qid = q["id"]
                if qid in answers:
                    answer = answers[qid]
                    weight = q.get("weight", 0.5)
                    if answer is True or (isinstance(answer, str) and answer.strip().lower() in ("yes", "y")):
                        raw_scores[condition] *= (1.0 + weight * 0.5)
                    elif answer is False or (isinstance(answer, str) and answer.strip().lower() in ("no", "n")):
                        raw_scores[condition] *= (1.0 - weight * 0.3)

        if not raw_scores:
            return []

        # Normalize to pseudo-probabilities (top candidate gets highest share)
        total = sum(raw_scores.values())
        if total <= 0:
            return []

        ranked = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)

        # Keep top 5 diagnoses
        results: list[DiagnosisProbability] = []
        for condition, score in ranked[:5]:
            confidence = round(score / total, 2)
            linked_symptoms = condition_symptoms.get(condition, [])
            reasoning = (
                f"Associated with reported symptom(s): "
                f"{', '.join(s.replace('_', ' ') for s in linked_symptoms)}. "
                f"Score {score:.2f} based on symptom priors and answer adjustments."
            )
            results.append(DiagnosisProbability(
                condition=condition,
                confidence=confidence,
                reasoning=reasoning,
            ))

        return results

    @staticmethod
    def _complexity_label(score: float) -> str:
        """Convert numeric complexity score to a human-readable label."""
        if score < 0.25:
            return "Low"
        elif score < 0.50:
            return "Moderate"
        elif score < 0.75:
            return "High"
        else:
            return "Very High"
