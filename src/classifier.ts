import {
  VisitCategory,
  UrgencyLevel,
  ClassifiedIntent,
  ClassificationResult,
  SchedulingFlag,
  FlagType,
} from "../index";
import {
  KEYWORD_RULES,
  COMPLEXITY_KEYWORDS,
  AUTO_FLAGS,
} from "./config";

/**
 * Classify free-text patient input into one or more visit intents
 * with urgency levels and scheduling flags.
 */
export function classifyInput(rawInput: string): ClassificationResult {
  const normalized = rawInput.toLowerCase();
  const intents: ClassifiedIntent[] = [];
  const flags: SchedulingFlag[] = [];

  // --- Match keyword rules ---
  for (const rule of KEYWORD_RULES) {
    const matched: string[] = [];
    for (const kw of rule.keywords) {
      if (normalized.includes(kw)) {
        matched.push(kw);
      }
    }
    if (matched.length === 0) continue;

    // Calculate confidence based on how many keywords matched relative to rule size
    const confidence = Math.min(0.5 + matched.length * 0.15, 0.98);

    // Check if we already have an intent for this category
    const existing = intents.find((i) => i.category === rule.category);
    if (existing) {
      // Merge: add keywords, raise confidence, escalate urgency
      existing.matchedKeywords.push(...matched);
      existing.confidence = Math.min(existing.confidence + matched.length * 0.1, 0.98);
      if (rule.urgency && urgencyRank(rule.urgency) > urgencyRank(existing.urgency)) {
        existing.urgency = rule.urgency;
      }
    } else {
      intents.push({
        category: rule.category,
        confidence,
        matchedKeywords: matched,
        urgency: rule.urgency ?? UrgencyLevel.ROUTINE,
      });
    }
  }

  // --- If nothing matched, classify as UNKNOWN ---
  if (intents.length === 0) {
    intents.push({
      category: VisitCategory.UNKNOWN,
      confidence: 0.2,
      matchedKeywords: [],
      urgency: UrgencyLevel.ROUTINE,
    });
    flags.push({
      type: FlagType.LOW_CONFIDENCE,
      message: "Could not confidently classify patient input — manual review recommended.",
      severity: "warning",
    });
  }

  // --- Sort intents by confidence descending ---
  intents.sort((a, b) => b.confidence - a.confidence);
  const primaryIntent = intents[0];

  // --- Multi-concern flag ---
  if (intents.length > 1) {
    flags.push({
      type: FlagType.MULTI_CONCERN,
      message: `Patient described ${intents.length} distinct concerns — additional time allocated.`,
      severity: "info",
    });
  }

  // --- Mental health flag ---
  if (intents.some((i) => i.category === VisitCategory.MENTAL_HEALTH)) {
    flags.push({
      type: FlagType.MENTAL_HEALTH_MENTION,
      message: "Patient mentioned mental health concerns — ensure appropriate provider and time.",
      severity: "warning",
    });
  }

  // --- Low overall confidence ---
  if (primaryIntent.confidence < 0.5) {
    const alreadyFlagged = flags.some((f) => f.type === FlagType.LOW_CONFIDENCE);
    if (!alreadyFlagged) {
      flags.push({
        type: FlagType.LOW_CONFIDENCE,
        message: "Classification confidence is low — consider calling the patient for clarification.",
        severity: "warning",
      });
    }
  }

  // --- Complexity detection ---
  const hasComplexity = COMPLEXITY_KEYWORDS.some((kw) => normalized.includes(kw));
  if (hasComplexity) {
    flags.push({
      type: FlagType.COMPLEX_HISTORY,
      message: "Patient language suggests complex medical history — extra time may be needed.",
      severity: "info",
    });
  }

  // --- Auto-flags (emergency / crisis) ---
  for (const af of AUTO_FLAGS) {
    if (af.keywords.some((kw) => normalized.includes(kw))) {
      // Avoid duplicate flag types with the same message
      if (!flags.some((f) => f.type === af.flagType && f.message === af.message)) {
        flags.push({
          type: af.flagType,
          message: af.message,
          severity: af.severity,
        });
      }
    }
  }

  return {
    rawInput,
    intents,
    primaryIntent,
    hasMultipleConcerns: intents.length > 1,
    flags,
  };
}

/** Numeric rank for urgency comparison. */
function urgencyRank(level: UrgencyLevel): number {
  switch (level) {
    case UrgencyLevel.ROUTINE:
      return 0;
    case UrgencyLevel.SOON:
      return 1;
    case UrgencyLevel.URGENT:
      return 2;
    case UrgencyLevel.EMERGENCY:
      return 3;
  }
}
