"""
Anilla AI Question Engine
==========================

Hybrid question selection engine that uses decision-tree logic to guide
follow-up questioning during patient intake. The engine:

1. Maps extracted symptoms to candidate conditions via the knowledge base.
2. Ranks conditions by probability.
3. Selects the most informative unanswered question for the top candidate.
4. Refines probability estimates as answers arrive.
5. Checks for red-flag patterns after every update.

Limits:
- 10 questions per individual concern
- 20 questions globally across all concerns
- Terminates early when the decision tree has no more discriminating questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.knowledge_base import (
    CONDITION_QUESTIONS,
    PHQ2_QUESTIONS,
    RED_FLAG_PATTERNS,
    SYMPTOM_CONDITION_MAP,
    YEARLY_CHECKUP_QUESTIONS,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SessionContext:
    """Accumulated state for one intake session."""

    extracted_symptoms: list[str] = field(default_factory=list)
    """Canonical symptom names extracted so far."""

    previous_questions: list[str] = field(default_factory=list)
    """Question IDs already asked."""

    previous_answers: dict[str, Any] = field(default_factory=dict)
    """Map of question_id -> patient answer (bool for yes_no, str for short_answer)."""

    patient_medical_history: dict[str, Any] = field(default_factory=dict)
    """Known patient history: chronic_conditions, medications, allergies, etc."""

    concerns_list: list[str] = field(default_factory=list)
    """Ordered list of concern topics the patient wants to discuss."""

    current_concern_index: int = 0
    """Index into concerns_list for the concern currently being explored."""

    total_questions_asked: int = 0
    """Running total across all concerns."""


@dataclass
class FollowUpQuestion:
    """A single follow-up question to present to the patient."""

    question_id: str
    text: str
    question_type: str  # "yes_no" | "short_answer" | "scale"
    target_condition: str
    """The condition this question is most informative for."""
    options: list[dict] | None = None
    """For scale-type questions (e.g. PHQ-2), the available options."""


@dataclass
class RedFlag:
    """A matched red-flag pattern that warrants clinical escalation."""

    trigger_description: str
    severity: str  # "critical" | "high" | "moderate"
    matched_pattern: str
    action: str = ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUESTIONS_PER_CONCERN = 10
MAX_GLOBAL_QUESTIONS = 20


# ---------------------------------------------------------------------------
# Question Engine
# ---------------------------------------------------------------------------

class QuestionEngine:
    """
    Selects the next most informative follow-up question for a patient intake
    session using a decision-tree approach over the medical knowledge base.

    The engine maintains a probability distribution over candidate conditions
    for each symptom cluster and greedily picks the question with the highest
    expected information gain (approximated by the question weight for the
    top-ranked unresolved condition).

    Example::

        engine = QuestionEngine()
        ctx = SessionContext(extracted_symptoms=["chest_pain"])
        q = engine.select_next_question(ctx)
        # FollowUpQuestion(question_id='ap_exertion', ...)
    """

    def select_next_question(self, ctx: SessionContext) -> FollowUpQuestion | None:
        """
        Select the next follow-up question based on the current session state.

        Returns ``None`` when:
        - The decision tree has no more unanswered questions for current conditions.
        - 10 questions have been asked for the current concern.
        - 20 global questions have been reached.

        Parameters
        ----------
        ctx : SessionContext
            The current accumulated session state.

        Returns
        -------
        FollowUpQuestion | None
        """
        # Global limit
        if ctx.total_questions_asked >= MAX_GLOBAL_QUESTIONS:
            return None

        # Per-concern limit: count questions asked for current concern's symptoms
        concern_question_count = self._count_concern_questions(ctx)
        if concern_question_count >= MAX_QUESTIONS_PER_CONCERN:
            return None

        # Build ranked condition list from extracted symptoms
        condition_scores = self._rank_conditions(ctx)
        if not condition_scores:
            return None

        # Iterate conditions in descending score order.  For each, find the
        # highest-weight unanswered question.
        for condition, _score in condition_scores:
            questions = CONDITION_QUESTIONS.get(condition, [])
            if not questions:
                continue

            # Filter out already-asked questions, sort by weight descending
            candidates = [
                q for q in questions if q["id"] not in ctx.previous_questions
            ]
            candidates.sort(key=lambda q: q.get("weight", 0.5), reverse=True)

            if candidates:
                best = candidates[0]
                return FollowUpQuestion(
                    question_id=best["id"],
                    text=best["text"],
                    question_type=best["question_type"],
                    target_condition=condition,
                    options=best.get("options"),
                )

        # No unanswered questions remain
        return None

    def check_red_flags(
        self,
        symptoms: list[str],
        answers: dict[str, Any],
    ) -> list[RedFlag]:
        """
        Check current symptoms and accumulated answers against known
        red-flag patterns.

        The check works in two passes:
        1. **Symptom match** -- does the patient have the required symptom(s)?
        2. **Indicator scan** -- do answers or symptom text contain any of the
           additional indicator phrases?

        Parameters
        ----------
        symptoms : list[str]
            Canonical symptom names.
        answers : dict[str, Any]
            Accumulated question answers (values may be bool or str).

        Returns
        -------
        list[RedFlag]
            Matched red-flag patterns, ordered by severity (critical first).
        """
        flags: list[RedFlag] = []
        answers_text = " ".join(
            str(v).lower() for v in answers.values() if isinstance(v, str)
        )
        # Also consider "yes" answers -- if a yes_no question about a red-flag
        # indicator was answered affirmatively, include the question id text
        # (the question text itself may reference the indicator).
        yes_context = " ".join(
            qid.lower() for qid, val in answers.items()
            if val is True or (isinstance(val, str) and val.strip().lower() in ("yes", "y"))
        )
        combined_context = f"{answers_text} {yes_context} {' '.join(symptoms)}"

        for pattern in RED_FLAG_PATTERNS:
            # Check required symptom overlap
            required_symptoms = pattern["symptoms"]
            if not any(rs in symptoms for rs in required_symptoms):
                continue

            # Check additional indicators
            indicators = pattern.get("additional_indicators", [])
            matched_indicators = [
                ind for ind in indicators
                if ind.lower() in combined_context
            ]

            # A red flag triggers if:
            # - symptom match AND at least one indicator matches, OR
            # - symptom match AND there are no additional indicators defined
            if matched_indicators or not indicators:
                flags.append(
                    RedFlag(
                        trigger_description=pattern["name"],
                        severity=pattern["severity"],
                        matched_pattern=pattern["id"],
                        action=pattern.get("action", ""),
                    )
                )

        # Also check for multi-symptom red flags where ALL required symptoms
        # are present (even without indicator matches).
        for pattern in RED_FLAG_PATTERNS:
            required = pattern["symptoms"]
            if len(required) > 1 and all(rs in symptoms for rs in required):
                pid = pattern["id"]
                if not any(f.matched_pattern == pid for f in flags):
                    flags.append(
                        RedFlag(
                            trigger_description=pattern["name"],
                            severity=pattern["severity"],
                            matched_pattern=pid,
                            action=pattern.get("action", ""),
                        )
                    )

        # Sort: critical > high > moderate
        severity_order = {"critical": 0, "high": 1, "moderate": 2}
        flags.sort(key=lambda f: severity_order.get(f.severity, 3))
        return flags

    def generate_yearly_checkup_questions(self) -> list[dict]:
        """
        Return the full list of standard yearly-checkup pre-visit questions.

        These are presented as a batch (not one-at-a-time like follow-up
        questions) and include PHQ-2 screening, medication reconciliation,
        vital-sign self-reports, and lifestyle questions.

        Returns
        -------
        list[dict]
            Each dict contains id, category, text, question_type, and
            optional options.
        """
        return list(YEARLY_CHECKUP_QUESTIONS)

    def analyze_phq2_responses(self, answers: dict[str, int]) -> bool:
        """
        Analyze PHQ-2 screening responses to determine if follow-up is needed.

        The PHQ-2 consists of two questions scored 0-3 each. A total score
        of 3 or higher indicates a positive screen and warrants a full PHQ-9
        assessment.

        Parameters
        ----------
        answers : dict[str, int]
            Map of PHQ-2 question IDs to integer scores (0-3).
            Expected keys: ``"phq2_q1"`` and ``"phq2_q2"``.

        Returns
        -------
        bool
            ``True`` if the combined score >= 3 (needs follow-up), else ``False``.
        """
        total = sum(
            answers.get(q["id"], 0) for q in PHQ2_QUESTIONS
        )
        return total >= 3

    # -- internal helpers --------------------------------------------------

    def _rank_conditions(self, ctx: SessionContext) -> list[tuple[str, float]]:
        """
        Build a ranked list of (condition, adjusted_score) from the patient's
        current symptoms and answers.

        The base score comes from ``SYMPTOM_CONDITION_MAP`` priors. Affirmative
        answers to a condition's questions boost its score; negative answers
        reduce it.
        """
        scores: dict[str, float] = {}

        for symptom in ctx.extracted_symptoms:
            condition_probs = SYMPTOM_CONDITION_MAP.get(symptom, [])
            for condition, prob in condition_probs:
                scores[condition] = scores.get(condition, 0.0) + prob

        # Adjust scores based on answered questions
        for condition in list(scores.keys()):
            questions = CONDITION_QUESTIONS.get(condition, [])
            for q in questions:
                qid = q["id"]
                if qid in ctx.previous_answers:
                    answer = ctx.previous_answers[qid]
                    weight = q.get("weight", 0.5)
                    if answer is True or (isinstance(answer, str) and answer.strip().lower() in ("yes", "y")):
                        # Affirmative: boost score
                        scores[condition] *= (1.0 + weight * 0.5)
                    elif answer is False or (isinstance(answer, str) and answer.strip().lower() in ("no", "n")):
                        # Negative: reduce score
                        scores[condition] *= (1.0 - weight * 0.3)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked

    @staticmethod
    def _count_concern_questions(ctx: SessionContext) -> int:
        """
        Count how many questions have been asked that are relevant to the
        current concern's symptom cluster.

        This is approximated by counting all previous questions whose target
        condition is reachable from any of the currently extracted symptoms.
        """
        # Gather all conditions reachable from current symptoms
        reachable_conditions: set[str] = set()
        for symptom in ctx.extracted_symptoms:
            for condition, _ in SYMPTOM_CONDITION_MAP.get(symptom, []):
                reachable_conditions.add(condition)

        # Count questions whose ID belongs to a reachable condition
        count = 0
        for condition in reachable_conditions:
            for q in CONDITION_QUESTIONS.get(condition, []):
                if q["id"] in ctx.previous_questions:
                    count += 1
        return count
