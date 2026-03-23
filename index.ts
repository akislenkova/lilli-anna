// src/types/index.ts
// ─────────────────────────────────────────────────────────
// Shared type definitions for the scheduling allocation system
// ─────────────────────────────────────────────────────────

/**
 * Medical visit categories that the classifier can identify.
 * Each maps to a base duration in the config.
 */
export enum VisitCategory {
    ROUTINE_CHECKUP = "routine_checkup",
    FOLLOW_UP = "follow_up",
    ACUTE_ILLNESS = "acute_illness",
    CHRONIC_MANAGEMENT = "chronic_management",
    MENTAL_HEALTH = "mental_health",
    PRESCRIPTION_REFILL = "prescription_refill",
    LAB_REVIEW = "lab_review",
    PROCEDURE_MINOR = "procedure_minor",
    PROCEDURE_MAJOR = "procedure_major",
    NEW_PATIENT_INTAKE = "new_patient_intake",
    URGENT_CARE = "urgent_care",
    PREVENTIVE_SCREENING = "preventive_screening",
    CONSULTATION = "consultation",
    UNKNOWN = "unknown",
  }
  
  /**
   * Urgency levels that can modify scheduling priority
   */
  export enum UrgencyLevel {
    ROUTINE = "routine",
    SOON = "soon",         // within a few days
    URGENT = "urgent",     // same-day preferred
    EMERGENCY = "emergency", // immediate — flagged for triage, not scheduled normally
  }
  
  /**
   * A single classified intent extracted from patient input
   */
  export interface ClassifiedIntent {
    category: VisitCategory;
    confidence: number;        // 0.0 – 1.0
    matchedKeywords: string[]; // which words/phrases triggered this classification
    urgency: UrgencyLevel;
  }
  
  /**
   * The full classification result from the intake text
   */
  export interface ClassificationResult {
    rawInput: string;
    intents: ClassifiedIntent[];
    primaryIntent: ClassifiedIntent;
    hasMultipleConcerns: boolean;
    flags: SchedulingFlag[];
  }
  
  /**
   * Flags that the system raises for doctor/staff attention
   */
  export interface SchedulingFlag {
    type: FlagType;
    message: string;
    severity: "info" | "warning" | "critical";
  }
  
  export enum FlagType {
    MULTI_CONCERN = "multi_concern",
    POSSIBLE_EMERGENCY = "possible_emergency",
    MENTAL_HEALTH_MENTION = "mental_health_mention",
    LOW_CONFIDENCE = "low_confidence",
    NEW_PATIENT = "new_patient",
    COMPLEX_HISTORY = "complex_history",
  }
  
  /**
   * Duration breakdown for a single concern within a visit
   */
  export interface DurationComponent {
    category: VisitCategory;
    baseDuration: number;      // minutes
    adjustedDuration: number;  // after modifiers
    reason: string;            // human-readable explanation
  }
  
  /**
   * The final time allocation recommendation
   */
  export interface TimeAllocation {
    recommendedDuration: number;  // total minutes
    minimumDuration: number;      // bare minimum if schedule is tight
    breakdown: DurationComponent[];
    bufferMinutes: number;        // added buffer for transitions
    flags: SchedulingFlag[];
    confidence: number;           // overall confidence in the recommendation
    reasoning: string;            // human-readable summary for the doctor
  }
  
  /**
   * API request shape
   */
  export interface AllocationRequest {
    patientInput: string;
    patientId?: string;
    isNewPatient?: boolean;
    doctorId?: string;
    preferredDuration?: number;  // patient-requested duration override
  }
  
  /**
   * API response shape
   */
  export interface AllocationResponse {
    success: boolean;
    allocation: TimeAllocation;
    classification: ClassificationResult;
    timestamp: string;
  }
  
  /**
   * Doctor-specific configuration overrides
   */
  export interface DoctorPreferences {
    doctorId: string;
    defaultBufferMinutes: number;
    categoryOverrides: Partial<Record<VisitCategory, number>>; // custom durations
    maxAppointmentMinutes: number;
    minAppointmentMinutes: number;
  }