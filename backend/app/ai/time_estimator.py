"""
Anilla AI Time Estimator
=========================

Appointment duration estimation model that predicts how long a visit will
take based on visit type, patient demographics, concern complexity, and
historical data.

Two operating modes:
1. **Cold-start heuristic** -- for new patients or those without historical
   appointment data, uses rule-based defaults from spec section 10.3.
2. **History-informed** -- when past appointment durations are available,
   uses a weighted average adjusted for current concern complexity and
   physician feedback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EstimationContext:
    """Input context for appointment duration estimation."""

    visit_type: str = "specific_concern"
    """One of 'routine_checkup', 'new_patient_intake', 'specific_concern', 'follow_up'."""

    concerns: list[dict] = field(default_factory=list)
    """List of concern dicts, each with keys: name (str), severity (str: mild/moderate/severe)."""

    patient_age: int | None = None
    """Patient age in years, if known."""

    is_new_patient: bool = False
    """True if this is the patient's first visit at this clinic."""

    medication_count: int = 0
    """Number of current medications the patient is taking."""

    chronic_condition_count: int = 0
    """Number of known chronic conditions."""

    historical_durations: list[float] = field(default_factory=list)
    """Past appointment durations in minutes (most recent first)."""

    physician_feedback_history: list[str] = field(default_factory=list)
    """
    List of feedback tags from physicians on past appointments.
    Common values: 'too_short', 'just_right', 'too_long', 'ran_over'.
    """


@dataclass
class DurationComponent:
    """A single component contributing to the total duration estimate."""

    name: str
    minutes: float
    reason: str


@dataclass
class TimeEstimate:
    """Output of the duration estimation model."""

    recommended_minutes: int
    """Best single-point recommendation in whole minutes."""

    minimum_minutes: int
    """Minimum viable duration (physician may feel rushed)."""

    range_min: int
    """Lower bound of the predicted range."""

    range_max: int
    """Upper bound of the predicted range."""

    confidence: float
    """Confidence score between 0.0 (no data) and 1.0 (highly confident)."""

    breakdown: list[DurationComponent] = field(default_factory=list)
    """Itemized components that sum to the recommendation."""

    reasoning: str = ""
    """Human-readable explanation of the estimate."""


# ---------------------------------------------------------------------------
# Constants -- cold-start heuristic (spec section 10.3)
# ---------------------------------------------------------------------------

_BASE_MINUTES: dict[str, int] = {
    "routine_checkup": 15,
    "new_patient_intake": 30,
    "specific_concern": 20,
    "follow_up": 15,
}

_ADDITIONAL_CONCERN_MINUTES = 5
_ELDERLY_THRESHOLD_AGE = 65
_ELDERLY_ADDITIONAL_MINUTES = 5
_HIGH_MEDICATION_THRESHOLD = 8
_HIGH_MEDICATION_ADDITIONAL_MINUTES = 5

# Severity multipliers applied to concern time
_SEVERITY_MULTIPLIER: dict[str, float] = {
    "mild": 0.8,
    "moderate": 1.0,
    "severe": 1.3,
}


# ---------------------------------------------------------------------------
# Time Estimator
# ---------------------------------------------------------------------------

class TimeEstimator:
    """
    Predicts appointment duration using a hybrid of cold-start heuristics
    and historical data when available.

    Cold-start rules (spec 10.3):
    - Base: 15 min routine, 30 min new patient, 20 min specific concern
    - +5 min per additional concern beyond the first
    - +5 min for patients over 65
    - +5 min if medication count > 8
    - New patients get a range instead of point estimate, with low confidence

    History-informed mode:
    - Uses weighted average of historical durations as baseline
    - Adjusts for current concern count and severity
    - Biases longer when physician feedback indicates 'too_short'
    - Confidence increases with more historical data points

    Example::

        estimator = TimeEstimator()
        ctx = EstimationContext(
            visit_type="specific_concern",
            concerns=[{"name": "headache", "severity": "severe"}],
            patient_age=70,
            medication_count=10,
        )
        est = estimator.estimate(ctx)
        # TimeEstimate(recommended_minutes=30, range_min=25, range_max=40, ...)
    """

    def estimate(self, context: EstimationContext) -> TimeEstimate:
        """
        Produce a duration estimate for the given context.

        Automatically selects cold-start or history-informed mode based on
        whether ``context.historical_durations`` is populated.

        Parameters
        ----------
        context : EstimationContext

        Returns
        -------
        TimeEstimate
        """
        if context.historical_durations:
            return self._history_informed_estimate(context)
        return self._cold_start_estimate(context)

    # ------------------------------------------------------------------
    # Cold-start heuristic
    # ------------------------------------------------------------------

    def _cold_start_estimate(self, ctx: EstimationContext) -> TimeEstimate:
        components: list[DurationComponent] = []
        reasoning_parts: list[str] = []

        # Base time
        base = _BASE_MINUTES.get(ctx.visit_type, 20)
        components.append(DurationComponent(
            name="base_time",
            minutes=base,
            reason=f"Base time for {ctx.visit_type.replace('_', ' ')}",
        ))
        reasoning_parts.append(f"Base: {base} min ({ctx.visit_type})")

        # Additional concerns
        extra_concerns = max(0, len(ctx.concerns) - 1)
        if extra_concerns > 0:
            extra_min = extra_concerns * _ADDITIONAL_CONCERN_MINUTES
            components.append(DurationComponent(
                name="additional_concerns",
                minutes=extra_min,
                reason=f"{extra_concerns} additional concern(s) at {_ADDITIONAL_CONCERN_MINUTES} min each",
            ))
            reasoning_parts.append(f"+{extra_min} min for {extra_concerns} extra concern(s)")

        # Severity adjustment for primary concern
        if ctx.concerns:
            primary_severity = ctx.concerns[0].get("severity", "moderate")
            multiplier = _SEVERITY_MULTIPLIER.get(primary_severity, 1.0)
            if multiplier != 1.0:
                # Apply to base only (not the whole sum)
                severity_delta = base * (multiplier - 1.0)
                if abs(severity_delta) >= 0.5:
                    components.append(DurationComponent(
                        name="severity_adjustment",
                        minutes=round(severity_delta, 1),
                        reason=f"Severity adjustment ({primary_severity}): x{multiplier}",
                    ))
                    reasoning_parts.append(
                        f"Severity ({primary_severity}): {'+' if severity_delta > 0 else ''}"
                        f"{severity_delta:.0f} min"
                    )

        # Elderly patient
        if ctx.patient_age is not None and ctx.patient_age >= _ELDERLY_THRESHOLD_AGE:
            components.append(DurationComponent(
                name="elderly_adjustment",
                minutes=_ELDERLY_ADDITIONAL_MINUTES,
                reason=f"Patient age {ctx.patient_age} >= {_ELDERLY_THRESHOLD_AGE}",
            ))
            reasoning_parts.append(f"+{_ELDERLY_ADDITIONAL_MINUTES} min (age >= {_ELDERLY_THRESHOLD_AGE})")

        # High medication count
        if ctx.medication_count > _HIGH_MEDICATION_THRESHOLD:
            components.append(DurationComponent(
                name="medication_review",
                minutes=_HIGH_MEDICATION_ADDITIONAL_MINUTES,
                reason=f"Medication count {ctx.medication_count} > {_HIGH_MEDICATION_THRESHOLD}",
            ))
            reasoning_parts.append(
                f"+{_HIGH_MEDICATION_ADDITIONAL_MINUTES} min "
                f"(medications: {ctx.medication_count} > {_HIGH_MEDICATION_THRESHOLD})"
            )

        # Chronic conditions add a small amount per condition beyond 2
        extra_chronic = max(0, ctx.chronic_condition_count - 2)
        if extra_chronic > 0:
            chronic_min = extra_chronic * 2
            components.append(DurationComponent(
                name="chronic_conditions",
                minutes=chronic_min,
                reason=f"{extra_chronic} chronic conditions beyond baseline 2",
            ))
            reasoning_parts.append(f"+{chronic_min} min (chronic conditions)")

        total = sum(c.minutes for c in components)
        recommended = max(10, round(round(total / 5) * 5))

        # New patients: wider range, lower confidence
        if ctx.is_new_patient:
            range_min = max(10, recommended - 5)
            range_max = recommended + 10
            confidence = 0.35
            reasoning_parts.append("New patient: wider range, lower confidence")
        else:
            range_min = max(10, recommended - 5)
            range_max = recommended + 5
            confidence = 0.50

        minimum = max(10, range_min - 2)

        return TimeEstimate(
            recommended_minutes=recommended,
            minimum_minutes=minimum,
            range_min=range_min,
            range_max=range_max,
            confidence=round(confidence, 2),
            breakdown=components,
            reasoning="Cold-start estimate. " + "; ".join(reasoning_parts),
        )

    # ------------------------------------------------------------------
    # History-informed estimate
    # ------------------------------------------------------------------

    def _history_informed_estimate(self, ctx: EstimationContext) -> TimeEstimate:
        components: list[DurationComponent] = []
        reasoning_parts: list[str] = []

        # Weighted average of historical durations (more recent = heavier weight)
        durations = ctx.historical_durations
        n = len(durations)
        weights = [math.exp(-0.15 * i) for i in range(n)]
        total_weight = sum(weights)
        historical_avg = sum(d * w for d, w in zip(durations, weights)) / total_weight

        components.append(DurationComponent(
            name="historical_baseline",
            minutes=round(historical_avg, 1),
            reason=f"Weighted average of {n} past appointment(s)",
        ))
        reasoning_parts.append(f"Historical baseline: {historical_avg:.1f} min (n={n})")

        # Adjust for current concern count relative to typical single-concern visit
        concern_count = len(ctx.concerns)
        if concern_count > 1:
            concern_adj = (concern_count - 1) * _ADDITIONAL_CONCERN_MINUTES * 0.7
            components.append(DurationComponent(
                name="concern_count_adjustment",
                minutes=round(concern_adj, 1),
                reason=f"{concern_count} concerns (adjusted from history)",
            ))
            reasoning_parts.append(f"+{concern_adj:.0f} min for {concern_count} concerns")

        # Severity adjustment
        if ctx.concerns:
            severities = [c.get("severity", "moderate") for c in ctx.concerns]
            avg_multiplier = sum(_SEVERITY_MULTIPLIER.get(s, 1.0) for s in severities) / len(severities)
            if avg_multiplier != 1.0:
                sev_adj = historical_avg * (avg_multiplier - 1.0)
                if abs(sev_adj) >= 1.0:
                    components.append(DurationComponent(
                        name="severity_adjustment",
                        minutes=round(sev_adj, 1),
                        reason=f"Average severity multiplier: {avg_multiplier:.2f}",
                    ))
                    reasoning_parts.append(f"Severity adjustment: {sev_adj:+.0f} min")

        # Physician feedback bias
        if ctx.physician_feedback_history:
            too_short_count = sum(
                1 for f in ctx.physician_feedback_history
                if f in ("too_short", "ran_over")
            )
            too_long_count = sum(
                1 for f in ctx.physician_feedback_history if f == "too_long"
            )
            feedback_total = len(ctx.physician_feedback_history)

            if too_short_count > too_long_count:
                # Bias longer: add proportional to how often it was too short
                bias_ratio = too_short_count / feedback_total
                feedback_adj = historical_avg * 0.15 * bias_ratio
                components.append(DurationComponent(
                    name="physician_feedback_bias",
                    minutes=round(feedback_adj, 1),
                    reason=f"Physician feedback: {too_short_count}/{feedback_total} marked too short/ran over",
                ))
                reasoning_parts.append(f"Feedback bias: +{feedback_adj:.0f} min (often too short)")
            elif too_long_count > too_short_count:
                bias_ratio = too_long_count / feedback_total
                feedback_adj = -historical_avg * 0.10 * bias_ratio
                components.append(DurationComponent(
                    name="physician_feedback_bias",
                    minutes=round(feedback_adj, 1),
                    reason=f"Physician feedback: {too_long_count}/{feedback_total} marked too long",
                ))
                reasoning_parts.append(f"Feedback bias: {feedback_adj:.0f} min (often too long)")

        total = sum(c.minutes for c in components)
        recommended = max(10, round(round(total / 5) * 5))

        # Confidence scales with number of data points, capped at 0.95
        confidence = min(0.95, 0.50 + 0.08 * n)

        # Range narrows with more data
        spread = max(3, round(10 - 0.8 * min(n, 10)))
        range_min = max(10, recommended - spread)
        range_max = recommended + spread
        minimum = max(10, range_min - 2)

        return TimeEstimate(
            recommended_minutes=recommended,
            minimum_minutes=minimum,
            range_min=range_min,
            range_max=range_max,
            confidence=round(confidence, 2),
            breakdown=components,
            reasoning="History-informed estimate. " + "; ".join(reasoning_parts),
        )
