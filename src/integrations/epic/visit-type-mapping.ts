// src/integrations/epic/visit-type-mapping.ts
// ─────────────────────────────────────────────────────────
// Maps our AI-classified visit categories to Epic's visit
// type system.
//
// Every Epic instance has its own visit type IDs. This file
// provides a configurable mapping layer so clinics can wire
// up their specific Epic visit type codes.
// ─────────────────────────────────────────────────────────

import { VisitCategory } from "../../../index";

/**
 * Represents an Epic visit type as configured in their system.
 */
export interface EpicVisitType {
  /** Epic's internal visit type ID (varies per instance) */
  epicVisitTypeId: string;

  /** Human-readable name in Epic (e.g., "OFFICE VISIT - NEW PT") */
  epicDisplayName: string;

  /** Default duration in Epic (minutes) — may differ from our AI suggestion */
  epicDefaultDuration: number;

  /** Department IDs where this visit type is available */
  departmentIds: string[];
}

/**
 * The mapping from our classification categories to Epic visit types.
 */
export type VisitTypeMapping = Record<VisitCategory, EpicVisitType | null>;

/**
 * Example mapping — replace with values from your Epic instance.
 *
 * To discover your visit types, query:
 *   GET [fhir-base]/ValueSet/$expand?url=urn:oid:1.2.840.114350.1.13.861.1.7.3.808267.11
 * Or work with your Epic analyst to export the visit type table.
 */
export const EXAMPLE_VISIT_TYPE_MAP: VisitTypeMapping = {
  [VisitCategory.ROUTINE_CHECKUP]: {
    epicVisitTypeId: "1001",
    epicDisplayName: "OFFICE VISIT - ESTABLISHED",
    epicDefaultDuration: 20,
    departmentIds: ["10001", "10002"],
  },

  [VisitCategory.FOLLOW_UP]: {
    epicVisitTypeId: "1002",
    epicDisplayName: "FOLLOW UP VISIT",
    epicDefaultDuration: 15,
    departmentIds: ["10001", "10002"],
  },

  [VisitCategory.ACUTE_ILLNESS]: {
    epicVisitTypeId: "1003",
    epicDisplayName: "SICK VISIT",
    epicDefaultDuration: 20,
    departmentIds: ["10001", "10002", "10003"],
  },

  [VisitCategory.CHRONIC_MANAGEMENT]: {
    epicVisitTypeId: "1004",
    epicDisplayName: "CHRONIC DISEASE MANAGEMENT",
    epicDefaultDuration: 30,
    departmentIds: ["10001"],
  },

  [VisitCategory.MENTAL_HEALTH]: {
    epicVisitTypeId: "2001",
    epicDisplayName: "BEHAVIORAL HEALTH - INDIVIDUAL",
    epicDefaultDuration: 45,
    departmentIds: ["20001"],
  },

  [VisitCategory.PRESCRIPTION_REFILL]: {
    epicVisitTypeId: "1005",
    epicDisplayName: "MEDICATION MANAGEMENT",
    epicDefaultDuration: 10,
    departmentIds: ["10001", "10002"],
  },

  [VisitCategory.LAB_REVIEW]: {
    epicVisitTypeId: "1006",
    epicDisplayName: "RESULTS REVIEW",
    epicDefaultDuration: 15,
    departmentIds: ["10001"],
  },

  [VisitCategory.PROCEDURE_MINOR]: {
    epicVisitTypeId: "3001",
    epicDisplayName: "MINOR PROCEDURE",
    epicDefaultDuration: 30,
    departmentIds: ["10001", "30001"],
  },

  [VisitCategory.PROCEDURE_MAJOR]: {
    epicVisitTypeId: "3002",
    epicDisplayName: "SURGICAL CONSULTATION",
    epicDefaultDuration: 60,
    departmentIds: ["30001"],
  },

  [VisitCategory.NEW_PATIENT_INTAKE]: {
    epicVisitTypeId: "1007",
    epicDisplayName: "OFFICE VISIT - NEW PATIENT",
    epicDefaultDuration: 45,
    departmentIds: ["10001", "10002"],
  },

  [VisitCategory.URGENT_CARE]: {
    epicVisitTypeId: "4001",
    epicDisplayName: "URGENT CARE VISIT",
    epicDefaultDuration: 25,
    departmentIds: ["40001"],
  },

  [VisitCategory.PREVENTIVE_SCREENING]: {
    epicVisitTypeId: "1008",
    epicDisplayName: "PREVENTIVE CARE",
    epicDefaultDuration: 30,
    departmentIds: ["10001", "10002"],
  },

  [VisitCategory.CONSULTATION]: {
    epicVisitTypeId: "1009",
    epicDisplayName: "CONSULTATION",
    epicDefaultDuration: 30,
    departmentIds: ["10001"],
  },

  [VisitCategory.UNKNOWN]: null,  // Requires manual triage
};

/**
 * Resolves our AI classification to the right Epic visit type.
 *
 * When the AI suggests a different duration than Epic's default,
 * we include both so the scheduler can make an informed choice.
 */
export function resolveVisitType(
  category: VisitCategory,
  aiRecommendedMinutes: number,
  mapping: VisitTypeMapping = EXAMPLE_VISIT_TYPE_MAP
): {
  epicVisitType: EpicVisitType | null;
  aiDuration: number;
  epicDuration: number | null;
  durationMismatch: boolean;
  recommendation: string;
} {
  const epicType = mapping[category];

  if (!epicType) {
    return {
      epicVisitType: null,
      aiDuration: aiRecommendedMinutes,
      epicDuration: null,
      durationMismatch: false,
      recommendation: "No matching Epic visit type. Scheduler should manually select visit type.",
    };
  }

  const mismatch = Math.abs(aiRecommendedMinutes - epicType.epicDefaultDuration) > 5;

  let recommendation: string;
  if (!mismatch) {
    recommendation = `Use "${epicType.epicDisplayName}" (${epicType.epicDefaultDuration}min) — matches AI recommendation.`;
  } else if (aiRecommendedMinutes > epicType.epicDefaultDuration) {
    recommendation =
      `AI recommends ${aiRecommendedMinutes}min but "${epicType.epicDisplayName}" defaults to ${epicType.epicDefaultDuration}min. ` +
      `Consider using an extended visit type or booking back-to-back slots.`;
  } else {
    recommendation =
      `AI recommends only ${aiRecommendedMinutes}min for "${epicType.epicDisplayName}" (default ${epicType.epicDefaultDuration}min). ` +
      `Standard slot duration is fine — patient may finish early.`;
  }

  return {
    epicVisitType: epicType,
    aiDuration: aiRecommendedMinutes,
    epicDuration: epicType.epicDefaultDuration,
    durationMismatch: mismatch,
    recommendation,
  };
}
