"""
Anilla AI Symptom Extractor
============================

NLP-based symptom extraction service that processes free-text patient input
and identifies structured symptom data. Uses keyword matching and pattern
recognition against the medical knowledge base.

This module intentionally avoids external ML dependencies -- it uses rule-based
NLP so the system can run without GPU/model infrastructure while still
providing clinically useful extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.knowledge_base import SYMPTOM_CONDITION_MAP


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtractedSymptom:
    """A single symptom extracted from patient free-text input."""

    symptom_name: str
    """Canonical symptom key matching SYMPTOM_CONDITION_MAP (e.g. 'chest_pain')."""

    severity: str = "moderate"
    """One of 'mild', 'moderate', 'severe'. Defaults to moderate if unspecified."""

    duration_mentioned: str | None = None
    """Raw duration phrase extracted from text, e.g. 'for two weeks'."""

    body_location: str | None = None
    """Body location qualifier when mentioned, e.g. 'left arm', 'lower back'."""


# ---------------------------------------------------------------------------
# Colloquial -> canonical mappings
# ---------------------------------------------------------------------------
# Maps informal / lay-person phrases to canonical symptom keys used in the
# knowledge base.  Order matters: longer phrases are checked first to avoid
# partial matches.
# ---------------------------------------------------------------------------

_COLLOQUIAL_MAP: list[tuple[list[str], str]] = [
    # Head / Neurological
    (["my head hurts", "head is pounding", "head is killing me", "headaches", "head ache", "migraine", "head pain"], "headache"),
    (["dizzy", "lightheaded", "light headed", "room is spinning", "vertigo", "feeling faint", "woozy"], "dizziness"),
    (["can't see well", "blurry vision", "blurred vision", "vision is fuzzy", "hard to see", "losing vision", "seeing spots", "seeing flashes"], "vision_changes"),
    (["numb", "tingling", "pins and needles", "prickling", "lost feeling"], "numbness_tingling"),

    # Cardiovascular / Respiratory
    (["chest hurts", "chest tightness", "chest pressure", "pain in my chest", "tightness in chest", "heart hurts"], "chest_pain"),
    (["can't breathe", "hard to breathe", "out of breath", "short of breath", "breathing trouble", "winded", "gasping", "trouble breathing", "difficulty breathing"], "shortness_of_breath"),
    (["coughing", "dry cough", "wet cough", "hacking cough", "can't stop coughing", "productive cough"], "cough"),
    (["heart racing", "heart is pounding", "heart skipping", "fluttering in chest", "irregular heartbeat", "heart flutter"], "palpitations"),

    # Gastrointestinal
    (["tummy hurts", "stomach hurts", "stomach ache", "stomachache", "belly pain", "abdominal cramps", "stomach cramps", "gut pain", "tummy ache"], "abdominal_pain"),
    (["feel sick to my stomach", "nauseous", "queasy", "feel like throwing up", "going to vomit", "want to puke", "throwing up"], "nausea"),

    # Musculoskeletal
    (["my back hurts", "back is killing me", "back ache", "backache", "lower back pain", "upper back pain", "spine pain"], "back_pain"),
    (["herniated disk", "herniated disc", "bulging disk", "bulging disc", "slipped disk", "slipped disc", "disc herniation", "disk herniation", "pinched nerve", "sciatica", "spinal stenosis", "degenerative disc", "degenerative disk"], "herniated_disc"),
    (["joint aches", "joints hurt", "achy joints", "joint stiffness", "stiff joints", "sore joints", "arthritis pain"], "joint_pain"),
    (["neck hurts", "stiff neck", "neck is sore", "neck ache", "neck stiffness", "crick in my neck"], "neck_pain"),
    (["swollen", "swelling", "puffiness", "puffy", "bloated limb", "edema"], "swelling"),

    # Systemic
    (["tired all the time", "exhausted", "no energy", "worn out", "fatigued", "always tired", "wiped out", "run down", "low energy", "lethargic"], "fatigue"),
    (["fever", "feverish", "temperature", "chills", "feel hot", "burning up", "running a fever", "high temperature"], "fever"),
    (["gained weight", "losing weight", "weight loss", "weight gain", "getting heavier", "getting thinner", "unexplained weight"], "weight_changes"),
    (["bruising easily", "bleeding", "unexplained bruises", "bruises easily", "nosebleeds"], "bruising_bleeding"),

    # Dermatological
    (["rash", "skin rash", "itchy skin", "hives", "breaking out", "skin irritation", "skin bumps", "red patches", "skin lesion"], "skin_rash"),

    # Urological
    (["hurts to pee", "burning when i pee", "peeing a lot", "frequent urination", "blood in urine", "uti", "bladder issues", "urinary problems", "trouble peeing"], "urinary_issues"),

    # Mental health
    (["anxious", "worried all the time", "nervous", "panicky", "panic attacks", "constant worry", "can't relax", "on edge", "anxiety"], "anxiety"),
    (["feeling sad", "feeling hopeless", "depressed", "down in the dumps", "no motivation", "lost interest", "feeling empty", "crying a lot", "worthless"], "depression"),
    (["can't sleep", "trouble sleeping", "insomnia", "waking up at night", "sleep issues", "not sleeping well", "poor sleep", "restless nights"], "sleep_problems"),

    # ENT
    (["sore throat", "throat hurts", "throat pain", "scratchy throat", "painful swallowing", "hurts to swallow"], "sore_throat"),
    (["ear hurts", "earache", "ear pain", "ear infection", "ringing in ears"], "ear_pain"),
]

# Pre-compile a flat lookup for direct canonical names
_CANONICAL_SYMPTOMS: set[str] = set(SYMPTOM_CONDITION_MAP.keys()) | {"herniated_disc"}

# ---------------------------------------------------------------------------
# Negation handling
# ---------------------------------------------------------------------------
# Replaces negated symptom phrases (e.g. "no fever", "don't have fever") with
# a blank so they are not accidentally matched as positive findings.
# ---------------------------------------------------------------------------

_NEGATION_PATTERN = re.compile(
    r"\b(?:no|not|without|don't have|doesn't have|do not have|haven't had|"
    r"never had|denies|deny|absence of|free of)\s+\w+(?:\s+\w+){0,3}",
    re.IGNORECASE,
)


def _strip_negations(text: str) -> str:
    """Remove negated phrases so they don't match as positive symptoms."""
    return _NEGATION_PATTERN.sub(" ", text)


# ---------------------------------------------------------------------------
# Severity detection
# ---------------------------------------------------------------------------

_SEVERITY_PATTERNS: list[tuple[str, str]] = [
    # Severe
    (r"\b(worst ever|worst i.ve|excruciating|unbearable|extreme|terrible|horrible|agonizing|10 out of 10|really really bad|severe|intense|crushing|intolerable)\b", "severe"),
    # Mild
    (r"\b(slight|mild|minor|a little|a bit|small|barely|not too bad|tolerable|manageable|occasional|faint)\b", "mild"),
    # Moderate (explicit mentions; otherwise default)
    (r"\b(moderate|noticeable|pretty bad|fairly bad|uncomfortable|bothersome|significant)\b", "moderate"),
]

_SEVERITY_COMPILED = [(re.compile(pat, re.IGNORECASE), sev) for pat, sev in _SEVERITY_PATTERNS]


# ---------------------------------------------------------------------------
# Duration detection
# ---------------------------------------------------------------------------

_DURATION_PATTERN = re.compile(
    r"""
    (?:for\s+)?                         # optional leading "for"
    (?:about\s+|around\s+|roughly\s+)?  # optional approximation
    (?:the\s+(?:past|last)\s+)?         # "the past" / "the last"
    (\d+\s*(?:to\s*\d+\s*)?             # number (or range)
     (?:minute|hour|day|week|month|year)s?)
    |
    (?:since\s+(?:yesterday|last\s+(?:night|week|month|year)|this\s+morning))
    |
    (?:(?:a\s+)?(?:few|couple(?:\s+of)?)\s+(?:day|week|month|hour)s?)
    |
    (?:(?:all|over(?:night)?|today|yesterday|this\s+(?:morning|afternoon|evening|week)))
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Body location detection
# ---------------------------------------------------------------------------

_BODY_LOCATIONS = [
    "left arm", "right arm", "left leg", "right leg",
    "left side", "right side", "both sides",
    "lower back", "upper back", "middle back",
    "left knee", "right knee", "left hip", "right hip",
    "left shoulder", "right shoulder",
    "left wrist", "right wrist",
    "forehead", "temple", "back of head", "top of head",
    "upper abdomen", "lower abdomen", "right lower abdomen", "left lower abdomen",
    "chest", "throat", "groin", "ankle", "foot", "hand", "wrist",
    "neck", "jaw", "eye", "ear",
]

_LOCATION_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(loc) for loc in sorted(_BODY_LOCATIONS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------

class SymptomExtractor:
    """
    Extracts structured symptom information from free-text patient input.

    Uses a three-stage pipeline:
      1. **Symptom identification** -- matches colloquial phrases and canonical
         symptom names against the input text.
      2. **Severity classification** -- scans for severity-modifying language.
      3. **Metadata extraction** -- pulls duration and body-location mentions.

    Example::

        extractor = SymptomExtractor()
        results = extractor.extract("I've had a really bad headache for two weeks")
        # [ExtractedSymptom(symptom_name='headache', severity='severe',
        #                    duration_mentioned='two weeks', body_location=None)]
    """

    def extract(self, text: str) -> list[ExtractedSymptom]:
        """
        Extract symptoms from free-text patient input.

        Parameters
        ----------
        text : str
            Raw patient input, e.g. from a chat message or intake form.

        Returns
        -------
        list[ExtractedSymptom]
            Deduplicated list of extracted symptoms with severity, duration,
            and body-location metadata when available.
        """
        if not text or not text.strip():
            return []

        text_lower = _strip_negations(text.lower())
        found: dict[str, ExtractedSymptom] = {}

        # Stage 1: Identify symptoms via colloquial mapping
        for phrases, canonical in _COLLOQUIAL_MAP:
            for phrase in phrases:
                if phrase in text_lower:
                    if canonical not in found:
                        found[canonical] = ExtractedSymptom(symptom_name=canonical)
                    break  # first matching phrase is enough per symptom

        # Stage 1b: Also check for exact canonical symptom names
        for canonical in _CANONICAL_SYMPTOMS:
            display_name = canonical.replace("_", " ")
            if display_name in text_lower and canonical not in found:
                found[canonical] = ExtractedSymptom(symptom_name=canonical)

        # Stage 2: Classify severity
        global_severity = self._detect_severity(text_lower)

        # Stage 3: Extract duration
        duration = self._extract_duration(text)

        # Stage 4: Extract body location
        location = self._extract_location(text_lower)

        # Apply global metadata to all found symptoms.
        # In a multi-symptom sentence each symptom gets the same global
        # metadata unless we implement per-symptom windowing (future work).
        for sym in found.values():
            if global_severity:
                sym.severity = global_severity
            if duration:
                sym.duration_mentioned = duration
            if location:
                sym.body_location = location

        return list(found.values())

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _detect_severity(text: str) -> str | None:
        """Return the most extreme severity modifier found, or None."""
        best: str | None = None
        priority = {"severe": 3, "moderate": 2, "mild": 1}
        best_priority = 0
        for pattern, severity in _SEVERITY_COMPILED:
            if pattern.search(text):
                if priority[severity] > best_priority:
                    best = severity
                    best_priority = priority[severity]
        return best

    @staticmethod
    def _extract_duration(text: str) -> str | None:
        """Return the first duration phrase found, or None."""
        match = _DURATION_PATTERN.search(text)
        if match:
            return match.group(0).strip()
        return None

    @staticmethod
    def _extract_location(text: str) -> str | None:
        """Return the first body-location mention found, or None."""
        match = _LOCATION_PATTERN.search(text)
        if match:
            return match.group(0).strip().lower()
        return None
