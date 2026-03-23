import { VisitCategory, UrgencyLevel, FlagType } from "../index";

/**
 * Base appointment durations in minutes per visit category.
 */
export const BASE_DURATIONS: Record<VisitCategory, number> = {
  [VisitCategory.ROUTINE_CHECKUP]: 20,
  [VisitCategory.FOLLOW_UP]: 15,
  [VisitCategory.ACUTE_ILLNESS]: 20,
  [VisitCategory.CHRONIC_MANAGEMENT]: 30,
  [VisitCategory.MENTAL_HEALTH]: 45,
  [VisitCategory.PRESCRIPTION_REFILL]: 10,
  [VisitCategory.LAB_REVIEW]: 15,
  [VisitCategory.PROCEDURE_MINOR]: 30,
  [VisitCategory.PROCEDURE_MAJOR]: 60,
  [VisitCategory.NEW_PATIENT_INTAKE]: 45,
  [VisitCategory.URGENT_CARE]: 25,
  [VisitCategory.PREVENTIVE_SCREENING]: 30,
  [VisitCategory.CONSULTATION]: 30,
  [VisitCategory.UNKNOWN]: 20,
};

/**
 * Urgency multipliers applied to the base duration.
 */
export const URGENCY_MULTIPLIERS: Record<UrgencyLevel, number> = {
  [UrgencyLevel.ROUTINE]: 1.0,
  [UrgencyLevel.SOON]: 1.0,
  [UrgencyLevel.URGENT]: 1.15,
  [UrgencyLevel.EMERGENCY]: 1.25,
};

/**
 * Default buffer minutes between appointments.
 */
export const DEFAULT_BUFFER_MINUTES = 5;

/**
 * When multiple concerns exist, each additional concern adds this fraction
 * of its base duration (to account for overlap in exam/discussion).
 */
export const ADDITIONAL_CONCERN_FACTOR = 0.6;

/**
 * Keyword-to-category mapping used by the classifier.
 * Each entry is [keywords[], category, urgencyHint?].
 */
export const KEYWORD_RULES: {
  keywords: string[];
  category: VisitCategory;
  urgency?: UrgencyLevel;
}[] = [
  // Emergency / urgent signals
  {
    keywords: ["chest pain", "can't breathe", "difficulty breathing", "shortness of breath", "severe bleeding", "unconscious", "stroke", "heart attack", "anaphylaxis", "seizure"],
    category: VisitCategory.URGENT_CARE,
    urgency: UrgencyLevel.EMERGENCY,
  },
  {
    keywords: ["urgent", "asap", "right away", "immediately", "can't wait", "getting worse fast", "emergency"],
    category: VisitCategory.URGENT_CARE,
    urgency: UrgencyLevel.URGENT,
  },

  // Mental health
  {
    keywords: ["depressed", "depression", "anxiety", "anxious", "panic attack", "suicidal", "self-harm", "mental health", "stressed", "can't sleep", "insomnia", "therapy", "counseling", "overwhelmed", "hopeless"],
    category: VisitCategory.MENTAL_HEALTH,
    urgency: UrgencyLevel.SOON,
  },

  // New patient
  {
    keywords: ["new patient", "first visit", "first time", "never been", "new here", "establish care", "new doctor"],
    category: VisitCategory.NEW_PATIENT_INTAKE,
  },

  // Procedures
  {
    keywords: ["surgery", "operation", "surgical", "biopsy", "excision", "removal of"],
    category: VisitCategory.PROCEDURE_MAJOR,
  },
  {
    keywords: ["mole removal", "wart removal", "stitches", "sutures", "drain", "injection", "cortisone shot", "joint injection", "iud", "implant", "cast", "splint"],
    category: VisitCategory.PROCEDURE_MINOR,
  },

  // Chronic management
  {
    keywords: ["diabetes", "blood sugar", "a1c", "hypertension", "high blood pressure", "asthma", "copd", "arthritis", "thyroid", "cholesterol", "heart failure", "chronic", "ongoing condition", "lupus", "fibromyalgia", "epilepsy"],
    category: VisitCategory.CHRONIC_MANAGEMENT,
  },

  // Preventive / screening
  {
    keywords: ["physical", "annual", "wellness", "screening", "mammogram", "colonoscopy", "pap smear", "vaccination", "vaccine", "immunization", "flu shot", "preventive", "check-up"],
    category: VisitCategory.PREVENTIVE_SCREENING,
  },

  // Lab review
  {
    keywords: ["lab results", "blood work", "test results", "bloodwork", "lab report", "results from", "mri results", "x-ray results", "scan results"],
    category: VisitCategory.LAB_REVIEW,
  },

  // Prescription refill
  {
    keywords: ["refill", "prescription", "medication refill", "need more", "ran out", "running low", "renew prescription", "rx"],
    category: VisitCategory.PRESCRIPTION_REFILL,
  },

  // Follow-up
  {
    keywords: ["follow up", "follow-up", "followup", "came back", "still having", "not better", "after surgery", "post-op", "recheck", "check on"],
    category: VisitCategory.FOLLOW_UP,
  },

  // Consultation
  {
    keywords: ["second opinion", "specialist", "referral", "consult", "consultation", "discuss options", "want to talk about"],
    category: VisitCategory.CONSULTATION,
  },

  // Acute illness (broad — matched later as fallback)
  {
    keywords: ["sick", "fever", "cough", "cold", "flu", "sore throat", "ear pain", "earache", "infection", "rash", "vomiting", "diarrhea", "nausea", "headache", "migraine", "pain", "hurt", "swollen", "burning", "itch", "lump", "bump", "sprain", "twisted", "cut", "wound"],
    category: VisitCategory.ACUTE_ILLNESS,
  },

  // Routine checkup (lowest priority — general terms)
  {
    keywords: ["checkup", "general visit", "just want to see", "routine"],
    category: VisitCategory.ROUTINE_CHECKUP,
  },
];

/**
 * Keywords that signal the patient may have a complex history,
 * warranting extra time regardless of visit type.
 */
export const COMPLEXITY_KEYWORDS: string[] = [
  "multiple conditions",
  "several medications",
  "long history",
  "complicated",
  "complex",
  "many issues",
  "a lot going on",
  "list of things",
  "several concerns",
  "multiple problems",
];

/**
 * Flags auto-raised by certain detections.
 */
export const AUTO_FLAGS: {
  keywords: string[];
  flagType: FlagType;
  message: string;
  severity: "info" | "warning" | "critical";
}[] = [
  {
    keywords: ["suicidal", "self-harm", "kill myself", "end my life", "want to die"],
    flagType: FlagType.POSSIBLE_EMERGENCY,
    message: "Patient language indicates possible suicidal ideation — route to crisis protocol.",
    severity: "critical",
  },
  {
    keywords: ["chest pain", "can't breathe", "stroke", "heart attack", "seizure", "unconscious"],
    flagType: FlagType.POSSIBLE_EMERGENCY,
    message: "Patient describes symptoms consistent with a medical emergency — consider immediate triage.",
    severity: "critical",
  },
];
