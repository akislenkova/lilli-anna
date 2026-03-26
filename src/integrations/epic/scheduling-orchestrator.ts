// src/integrations/epic/scheduling-orchestrator.ts
// ─────────────────────────────────────────────────────────
// The orchestrator connects the AI classification engine to
// Epic's FHIR scheduling APIs. This is where everything
// comes together.
//
// FLOW:
//   1. Patient enters free text in MyChart (via SMART app)
//   2. We classify the text → visit categories
//   3. We pull patient's conditions from Epic (enrichment)
//   4. We allocate time based on categories + history
//   5. We map the category to an Epic visit type
//   6. We call Appointment.$find with that visit type
//   7. Patient picks a slot → we call Appointment.$book
//   8. Allocation reasoning is sent to provider's In Basket
// ─────────────────────────────────────────────────────────

import { EpicFhirClient, FhirCondition, FhirAppointment } from "./epic-fhir-client";
import { resolveVisitType, VisitTypeMapping, EXAMPLE_VISIT_TYPE_MAP } from "./visit-type-mapping";
import { classifyInput } from "../../classifier";
import { allocateTime } from "../../allocator";
import {
  ClassificationResult,
  TimeAllocation,
  VisitCategory,
  FlagType,
} from "../../../index";

export interface SchedulingContext {
  /** Authenticated Epic FHIR client */
  epicClient: EpicFhirClient;

  /** Visit type mapping for this health system */
  visitTypeMapping?: VisitTypeMapping;

  /** Patient's FHIR ID (from SMART launch context) */
  patientFhirId: string;

  /** Whether this patient is new to the practice */
  isNewPatient?: boolean;
}

export interface SchedulingRecommendation {
  /** Our AI classification of the patient's input */
  classification: ClassificationResult;

  /** Our AI time allocation recommendation */
  allocation: TimeAllocation;

  /** How our category maps to Epic's visit type system */
  epicMapping: {
    epicVisitTypeId: string | null;
    epicDisplayName: string | null;
    aiDuration: number;
    epicDuration: number | null;
    durationMismatch: boolean;
    recommendation: string;
  };

  /** Patient's active conditions from Epic (for enrichment) */
  activeConditions: string[];

  /** Whether any active conditions match the stated reason */
  conditionsMatchReason: boolean;

  /** Available appointment slots from Epic */
  availableSlots: FhirAppointment[];

  /** The search window used for slot discovery */
  searchWindow: { start: string; end: string };
}

/**
 * Main orchestration function.
 *
 * Takes the patient's free-text reason for visit (from MyChart)
 * and returns a full recommendation with available slots.
 */
export async function getSchedulingRecommendation(
  patientInput: string,
  context: SchedulingContext
): Promise<SchedulingRecommendation> {
  const mapping = context.visitTypeMapping ?? EXAMPLE_VISIT_TYPE_MAP;

  // ── Step 1: Classify the patient's stated needs ────
  const classification = classifyInput(patientInput);

  // ── Step 2: Enrich with patient's known conditions ─
  let activeConditions: string[] = [];
  let conditionsMatchReason = false;

  try {
    const conditions = await context.epicClient.getActiveConditions(context.patientFhirId);
    activeConditions = conditions.map(c => c.code?.text || c.code?.coding?.[0]?.display || "Unknown");

    // Check if any active conditions relate to the classification
    conditionsMatchReason = checkConditionMatch(conditions, classification);

    // If patient has chronic conditions that match, boost chronic_management confidence
    if (conditionsMatchReason && classification.primaryIntent.category !== VisitCategory.CHRONIC_MANAGEMENT) {
      classification.flags.push({
        type: FlagType.COMPLEX_HISTORY,
        message: `Patient has active conditions (${activeConditions.slice(0, 3).join(", ")}) that may be relevant to this visit.`,
        severity: "info",
      });
    }
  } catch (error) {
    console.warn("Could not fetch patient conditions:", error);
    // Non-fatal — we can still schedule without condition enrichment
  }

  // ── Step 3: Allocate time ──────────────────────────
  const allocation = allocateTime(classification, {
    patientInput,
    isNewPatient: context.isNewPatient ?? false,
  });

  // ── Step 4: Map to Epic visit type ─────────────────
  const epicMappingResult = resolveVisitType(
    classification.primaryIntent.category,
    allocation.recommendedDuration,
    mapping
  );

  // ── Step 5: Find available slots in Epic ───────────
  const searchWindow = calculateSearchWindow(classification);
  let availableSlots: FhirAppointment[] = [];

  try {
    availableSlots = await context.epicClient.findAvailableAppointments({
      startTime: searchWindow.start,
      endTime: searchWindow.end,
      visitTypeId: epicMappingResult.epicVisitType?.epicVisitTypeId,
      patientId: context.patientFhirId,
    });
  } catch (error) {
    console.warn("Could not fetch available appointments:", error);
    // Return recommendation without slots — UI will show "call to schedule"
  }

  return {
    classification,
    allocation,
    epicMapping: {
      epicVisitTypeId: epicMappingResult.epicVisitType?.epicVisitTypeId || null,
      epicDisplayName: epicMappingResult.epicVisitType?.epicDisplayName || null,
      aiDuration: epicMappingResult.aiDuration,
      epicDuration: epicMappingResult.epicDuration,
      durationMismatch: epicMappingResult.durationMismatch,
      recommendation: epicMappingResult.recommendation,
    },
    activeConditions,
    conditionsMatchReason,
    availableSlots,
    searchWindow,
  };
}

/**
 * Books a selected appointment slot and files the AI reasoning.
 */
export async function bookWithRecommendation(
  appointmentId: string,
  recommendation: SchedulingRecommendation,
  context: SchedulingContext
): Promise<FhirAppointment> {
  const comment = buildAppointmentComment(recommendation);

  const booked = await context.epicClient.bookAppointment({
    appointmentId,
    patientId: context.patientFhirId,
    comment,
  });

  // TODO: Send detailed allocation breakdown to provider In Basket
  // via Epic's SendMessage API so they can review before the visit

  return booked;
}

// ─────────────────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────────────────

/**
 * Calculates the appointment search window based on urgency.
 */
function calculateSearchWindow(
  classification: ClassificationResult
): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now);
  const end = new Date(now);

  switch (classification.primaryIntent.urgency) {
    case "emergency":
      // Same day
      end.setDate(end.getDate() + 1);
      break;
    case "urgent":
      // Within 2 days
      end.setDate(end.getDate() + 2);
      break;
    case "soon":
      // Within a week
      end.setDate(end.getDate() + 7);
      break;
    case "routine":
    default:
      // Within 2 weeks
      start.setDate(start.getDate() + 1); // Not today for routine
      end.setDate(end.getDate() + 14);
      break;
  }

  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}

/**
 * Checks whether any of the patient's active conditions relate
 * to the classified visit categories.
 */
function checkConditionMatch(
  conditions: FhirCondition[],
  classification: ClassificationResult
): boolean {
  const conditionText = conditions
    .map(c => (c.code?.text || c.code?.coding?.[0]?.display || "").toLowerCase())
    .join(" ");

  const classifiedKeywords = classification.intents.flatMap(i => i.matchedKeywords);

  return classifiedKeywords.some(kw => conditionText.includes(kw.toLowerCase()));
}

/**
 * Builds a concise appointment comment with AI reasoning.
 * This is saved with the appointment in Epic and visible to staff.
 */
function buildAppointmentComment(rec: SchedulingRecommendation): string {
  const parts: string[] = [];

  parts.push(`[Smart Scheduling AI] ${rec.allocation.reasoning}`);

  if (rec.conditionsMatchReason) {
    parts.push(`Note: Patient has active conditions relevant to this visit.`);
  }

  if (rec.epicMapping.durationMismatch) {
    parts.push(rec.epicMapping.recommendation);
  }

  if (rec.classification.flags.length > 0) {
    const criticalFlags = rec.classification.flags.filter(f => f.severity !== "info");
    if (criticalFlags.length > 0) {
      parts.push(`Flags: ${criticalFlags.map(f => f.message).join(" | ")}`);
    }
  }

  return parts.join(" • ");
}
