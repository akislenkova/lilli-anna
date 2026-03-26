import {
  ClassificationResult,
  TimeAllocation,
  DurationComponent,
  SchedulingFlag,
  FlagType,
  DoctorPreferences,
  AllocationRequest,
} from "../index";
import {
  BASE_DURATIONS,
  URGENCY_MULTIPLIERS,
  DEFAULT_BUFFER_MINUTES,
  ADDITIONAL_CONCERN_FACTOR,
} from "./config";

/**
 * Compute a time allocation recommendation from a classification result.
 */
export function allocateTime(
  classification: ClassificationResult,
  request: AllocationRequest,
  doctorPrefs?: DoctorPreferences
): TimeAllocation {
  const { intents, flags } = classification;
  const breakdown: DurationComponent[] = [];
  const allFlags: SchedulingFlag[] = [...flags];

  // --- Build duration components ---
  intents.forEach((intent, idx) => {
    const base =
      doctorPrefs?.categoryOverrides?.[intent.category] ??
      BASE_DURATIONS[intent.category];

    const urgencyMult = URGENCY_MULTIPLIERS[intent.urgency];

    // First concern gets full time; additional concerns get reduced overlap time
    const overlapFactor = idx === 0 ? 1.0 : ADDITIONAL_CONCERN_FACTOR;

    const adjusted = Math.round(base * urgencyMult * overlapFactor);

    breakdown.push({
      category: intent.category,
      baseDuration: base,
      adjustedDuration: adjusted,
      reason:
        idx === 0
          ? `Primary concern: ${intent.category.replace(/_/g, " ")} (${base}min base × ${urgencyMult} urgency)`
          : `Additional concern: ${intent.category.replace(/_/g, " ")} (${base}min × ${urgencyMult} urgency × ${ADDITIONAL_CONCERN_FACTOR} overlap)`,
    });
  });

  // --- New patient modifier ---
  if (request.isNewPatient) {
    const intakeAlreadyIncluded = intents.some(
      (i) => i.category === "new_patient_intake"
    );
    if (!intakeAlreadyIncluded) {
      // Add 10 extra minutes for paperwork / history gathering
      breakdown.push({
        category: "new_patient_intake" as any,
        baseDuration: 10,
        adjustedDuration: 10,
        reason: "New patient supplement: additional time for intake paperwork and history",
      });
    }
    allFlags.push({
      type: FlagType.NEW_PATIENT,
      message: "New patient — extra intake time included.",
      severity: "info",
    });
  }

  // --- Complexity modifier ---
  const isComplex = flags.some((f) => f.type === FlagType.COMPLEX_HISTORY);
  if (isComplex && breakdown.length > 0) {
    const extra = Math.round(breakdown[0].adjustedDuration * 0.2);
    breakdown.push({
      category: breakdown[0].category,
      baseDuration: 0,
      adjustedDuration: extra,
      reason: "Complexity supplement: +20% on primary concern for complex history",
    });
  }

  // --- Sum up ---
  const totalAdjusted = breakdown.reduce((sum, c) => sum + c.adjustedDuration, 0);

  const buffer = doctorPrefs?.defaultBufferMinutes ?? DEFAULT_BUFFER_MINUTES;
  const maxAllowed = doctorPrefs?.maxAppointmentMinutes ?? 90;
  const minAllowed = doctorPrefs?.minAppointmentMinutes ?? 10;

  let recommended = Math.min(totalAdjusted + buffer, maxAllowed);
  recommended = Math.max(recommended, minAllowed);

  // Round to nearest 5 minutes for clean scheduling
  recommended = Math.ceil(recommended / 5) * 5;

  // Minimum is 80% of recommended, floored to minAllowed
  const minimum = Math.max(Math.round(recommended * 0.8), minAllowed);

  // Patient override: if patient requested a specific duration, note it
  if (request.preferredDuration && request.preferredDuration > recommended) {
    allFlags.push({
      type: FlagType.MULTI_CONCERN,
      message: `Patient requested ${request.preferredDuration}min which exceeds recommendation of ${recommended}min — consider honoring if schedule allows.`,
      severity: "info",
    });
  }

  // Overall confidence is average of intent confidences
  const confidence =
    classification.intents.reduce((sum, i) => sum + i.confidence, 0) /
    classification.intents.length;

  // Build reasoning summary
  const reasoning = buildReasoning(classification, breakdown, recommended, minimum, buffer);

  return {
    recommendedDuration: recommended,
    minimumDuration: minimum,
    breakdown,
    bufferMinutes: buffer,
    flags: allFlags,
    confidence: Math.round(confidence * 100) / 100,
    reasoning,
  };
}

function buildReasoning(
  classification: ClassificationResult,
  breakdown: DurationComponent[],
  recommended: number,
  minimum: number,
  buffer: number
): string {
  const primary = classification.primaryIntent;
  const lines: string[] = [];

  lines.push(
    `Based on patient input, the primary concern is "${primary.category.replace(/_/g, " ")}" ` +
      `(confidence: ${Math.round(primary.confidence * 100)}%, urgency: ${primary.urgency}).`
  );

  if (classification.hasMultipleConcerns) {
    lines.push(
      `Patient has ${classification.intents.length} concerns — time adjusted for combined visit.`
    );
  }

  lines.push(
    `Recommended appointment: ${recommended} minutes (minimum: ${minimum} minutes, includes ${buffer}-minute buffer).`
  );

  if (classification.flags.some((f) => f.severity === "critical")) {
    lines.push("** CRITICAL FLAGS present — review before scheduling. **");
  }

  return lines.join(" ");
}
