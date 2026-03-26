// src/nlp-engine.ts
// ─────────────────────────────────────────────────────────
// NLP engine for extracting entities from patient input and
// determining which follow-up questions to ask.
//
// This works alongside the keyword classifier — it extracts
// structured data (symptoms, durations, severity, body parts,
// medications) that inform which follow-up questions are
// relevant and how they refine the time allocation.
// ─────────────────────────────────────────────────────────

import { ClassificationResult, TimeAllocation, UrgencyLevel, VisitCategory } from "../index";
import { getFollowUpQuestions, FollowUpQuestion, saveExtraction } from "./database";
import { classifyInput } from "./classifier";
import { allocateTime } from "./allocator";

// ─────────────────────────────────────────────────────────
// ENTITY EXTRACTION
// ─────────────────────────────────────────────────────────

export interface ExtractedEntity {
  type: "symptom" | "duration" | "severity" | "body_part" | "medication" | "condition" | "frequency";
  value: string;
  confidence: number;
  sourceText: string;
}

const DURATION_PATTERNS = [
  { pattern: /(?:for|since|past|last)\s+(\d+)\s+(day|days|week|weeks|month|months|year|years)/gi, type: "duration" as const },
  { pattern: /(?:started|began|happening)\s+(\w+\s+\w*(?:ago|yesterday|today|last\s+\w+))/gi, type: "duration" as const },
  { pattern: /(this morning|yesterday|last night|few days|couple days|a week|couple weeks)/gi, type: "duration" as const },
];

const SEVERITY_PATTERNS = [
  { pattern: /\b(mild|slight|little|minor)\b/gi, value: "mild", score: 0.3 },
  { pattern: /\b(moderate|noticeable|bothering|concerning)\b/gi, value: "moderate", score: 0.5 },
  { pattern: /\b(severe|terrible|horrible|excruciating|unbearable|worst|really bad|extremely|intense)\b/gi, value: "severe", score: 0.9 },
];

const BODY_PARTS = [
  "head", "neck", "throat", "chest", "back", "stomach", "abdomen", "arm", "arms",
  "leg", "legs", "knee", "knees", "ankle", "foot", "feet", "hand", "hands",
  "wrist", "shoulder", "hip", "eye", "eyes", "ear", "ears", "nose", "mouth",
  "skin", "joints", "spine", "lower back", "upper back",
];

const MEDICATION_PATTERNS = [
  /(?:taking|on|prescribed|medication|medicine|drug|pill)\s+(\w+(?:\s+\w+)?)/gi,
  /(\w+(?:ol|in|ide|ine|ate|one|ium|pam|fen|min|zole))\b/gi,  // Common drug name suffixes
];

const FREQUENCY_PATTERNS = [
  /\b(constantly|all the time|non-stop|24\/7)\b/gi,
  /\b(every day|daily|each day)\b/gi,
  /\b(a few times|several times|occasionally|sometimes|once in a while)\b/gi,
  /\b(\d+\s*(?:times?|x)\s*(?:a|per)\s*(?:day|week|month))\b/gi,
];

/**
 * Extract structured entities from raw patient text.
 */
export function extractEntities(text: string): ExtractedEntity[] {
  const entities: ExtractedEntity[] = [];
  const lower = text.toLowerCase();

  // Duration extraction
  for (const dp of DURATION_PATTERNS) {
    const re = new RegExp(dp.pattern.source, dp.pattern.flags);
    let match;
    while ((match = re.exec(lower)) !== null) {
      entities.push({
        type: "duration",
        value: match[0].trim(),
        confidence: 0.8,
        sourceText: match[0],
      });
      if (!re.global) break;
    }
  }

  // Severity extraction
  for (const sp of SEVERITY_PATTERNS) {
    const re = new RegExp(sp.pattern.source, sp.pattern.flags);
    let match;
    while ((match = re.exec(lower)) !== null) {
      entities.push({
        type: "severity",
        value: sp.value,
        confidence: sp.score,
        sourceText: match[0],
      });
      if (!re.global) break;
    }
  }

  // Body part extraction
  for (const part of BODY_PARTS) {
    if (lower.includes(part)) {
      entities.push({
        type: "body_part",
        value: part,
        confidence: 0.9,
        sourceText: part,
      });
    }
  }

  // Frequency extraction
  for (const fp of FREQUENCY_PATTERNS) {
    const re = new RegExp(fp.source, fp.flags);
    let match;
    while ((match = re.exec(lower)) !== null) {
      entities.push({
        type: "frequency",
        value: match[0].trim(),
        confidence: 0.7,
        sourceText: match[0],
      });
      if (!re.global) break;
    }
  }

  return entities;
}

// ─────────────────────────────────────────────────────────
// FOLLOW-UP QUESTION SELECTION
// ─────────────────────────────────────────────────────────

export interface FollowUpFlow {
  questions: FollowUpQuestion[];
  entities: ExtractedEntity[];
  reasoning: string;
}

/**
 * Given a classification result, determine which follow-up
 * questions to ask the patient, informed by NLP extraction.
 */
export function generateFollowUpFlow(
  patientInput: string,
  classification: ClassificationResult,
  sessionId?: string
): FollowUpFlow {
  // 1. Extract entities from the raw text
  const entities = extractEntities(patientInput);

  // 2. Save extractions to DB if we have a session
  if (sessionId) {
    for (const entity of entities) {
      saveExtraction({
        session_id: sessionId,
        entity_type: entity.type,
        entity_value: entity.value,
        confidence: entity.confidence,
        source_text: entity.sourceText,
      });
    }
  }

  // 3. Get the categories and matched keywords from classification
  const categories = classification.intents.map(i => i.category);
  const allKeywords = classification.intents.flatMap(i => i.matchedKeywords);

  // 4. Query the database for relevant follow-up questions
  let questions = getFollowUpQuestions(categories, allKeywords);

  // 5. Filter out questions that the NLP extraction already answered
  questions = filterAlreadyAnswered(questions, entities);

  // 6. Limit to a reasonable number (max 5 questions)
  questions = questions.slice(0, 5);

  // 7. Build reasoning
  const reasoning = buildFollowUpReasoning(classification, entities, questions);

  return { questions, entities, reasoning };
}

/**
 * If NLP already extracted certain information, skip
 * questions that would ask for the same thing.
 */
function filterAlreadyAnswered(
  questions: FollowUpQuestion[],
  entities: ExtractedEntity[]
): FollowUpQuestion[] {
  const hasDuration = entities.some(e => e.type === "duration");
  const hasSeverity = entities.some(e => e.type === "severity");
  const hasBodyPart = entities.some(e => e.type === "body_part");

  return questions.filter(q => {
    const qLower = q.question_text.toLowerCase();

    // If patient already mentioned duration, skip duration questions
    if (hasDuration && (qLower.includes("how long") || qLower.includes("when did"))) {
      return false;
    }

    // If patient already expressed severity, skip pain scale / severity questions
    if (hasSeverity && (qLower.includes("rate your") || qLower.includes("how would you rate"))) {
      return false;
    }

    // If patient already mentioned body part, skip "where is" questions
    if (hasBodyPart && qLower.includes("where is")) {
      return false;
    }

    return true;
  });
}

function buildFollowUpReasoning(
  classification: ClassificationResult,
  entities: ExtractedEntity[],
  questions: FollowUpQuestion[]
): string {
  const parts: string[] = [];
  const primary = classification.primaryIntent;

  parts.push(
    `Detected ${classification.intents.length} concern(s), primary: ${primary.category.replace(/_/g, " ")}.`
  );

  if (entities.length > 0) {
    const types = [...new Set(entities.map(e => e.type))];
    parts.push(`Extracted ${entities.length} entities (${types.join(", ")}) from patient input.`);
  }

  if (questions.length > 0) {
    const required = questions.filter(q => q.required).length;
    parts.push(
      `Asking ${questions.length} follow-up question(s) (${required} required) to refine allocation.`
    );
  } else {
    parts.push("No additional follow-up questions needed — sufficient information provided.");
  }

  return parts.join(" ");
}

// ─────────────────────────────────────────────────────────
// ANSWER PROCESSING — Refine allocation based on follow-up
// ─────────────────────────────────────────────────────────

export interface FollowUpAnswer {
  questionId: number;
  answer: string | string[] | number;  // depends on question_type
}

export interface RefinedResult {
  classification: ClassificationResult;
  allocation: TimeAllocation;
  adjustments: string[];
}

/**
 * Process follow-up answers and produce a refined classification
 * and time allocation.
 */
export function processFollowUpAnswers(
  originalInput: string,
  originalClassification: ClassificationResult,
  answers: FollowUpAnswer[],
  questions: FollowUpQuestion[],
  isNewPatient: boolean
): RefinedResult {
  const adjustments: string[] = [];
  let extraMinutes = 0;
  let urgencyEscalation: UrgencyLevel | null = null;

  // Build a map of questionId → question for quick lookup
  const qMap = new Map(questions.map(q => [q.id, q]));

  // Process each answer
  for (const ans of answers) {
    const q = qMap.get(ans.questionId);
    if (!q) continue;

    // Check if the answer triggers a duration adjustment
    const durationImpact = assessDurationImpact(q, ans);
    if (durationImpact > 0) {
      extraMinutes += durationImpact;
      adjustments.push(`+${durationImpact}min: ${q.question_text} → "${ans.answer}"`);
    }

    // Check if the answer triggers an urgency escalation
    const urgencyImpact = assessUrgencyImpact(q, ans);
    if (urgencyImpact && (!urgencyEscalation || urgencyRank(urgencyImpact) > urgencyRank(urgencyEscalation))) {
      urgencyEscalation = urgencyImpact;
      adjustments.push(`Urgency → ${urgencyImpact}: ${q.question_text} → "${ans.answer}"`);
    }
  }

  // Build enriched input by appending answer context
  const enrichedInput = buildEnrichedInput(originalInput, answers, questions);

  // Re-classify with enriched input
  const refinedClassification = classifyInput(enrichedInput);

  // Apply urgency escalation if needed
  if (urgencyEscalation) {
    for (const intent of refinedClassification.intents) {
      if (urgencyRank(urgencyEscalation) > urgencyRank(intent.urgency)) {
        intent.urgency = urgencyEscalation;
      }
    }
  }

  // Re-allocate time
  const refinedAllocation = allocateTime(refinedClassification, {
    patientInput: enrichedInput,
    isNewPatient,
  });

  // Add extra minutes from follow-up answers
  if (extraMinutes > 0) {
    refinedAllocation.recommendedDuration = Math.min(
      refinedAllocation.recommendedDuration + extraMinutes,
      90 // cap
    );
    // Re-round to 5 minutes
    refinedAllocation.recommendedDuration = Math.ceil(refinedAllocation.recommendedDuration / 5) * 5;
    refinedAllocation.minimumDuration = Math.max(
      Math.round(refinedAllocation.recommendedDuration * 0.8),
      10
    );
    adjustments.push(`Total adjustment: +${extraMinutes}min from follow-up responses`);
  }

  return {
    classification: refinedClassification,
    allocation: refinedAllocation,
    adjustments,
  };
}

/**
 * Assess whether an answer to a follow-up question should
 * add extra time to the appointment.
 */
function assessDurationImpact(q: FollowUpQuestion, ans: FollowUpAnswer): number {
  if (q.affects_duration === 0) return 0;

  // For scale questions: high values (>7) trigger the duration impact
  if (q.question_type === "scale" && typeof ans.answer === "number") {
    if (ans.answer >= 7) return q.affects_duration;
    if (ans.answer >= 5) return Math.ceil(q.affects_duration / 2);
    return 0;
  }

  // For single_choice: certain answers indicate more time needed
  if (q.question_type === "single_choice" && typeof ans.answer === "string") {
    const lower = ans.answer.toLowerCase();
    // Answers suggesting worse condition → add time
    if (lower.includes("worse") || lower.includes("severe") || lower.includes("can't") ||
        lower.includes("multiple") || lower.includes("stopped") || lower.includes("very high") ||
        lower.includes("rapidly") || lower.includes("over 103") || lower.includes("struggling")) {
      return q.affects_duration;
    }
    // Middle-ground answers → half the time
    if (lower.includes("moderate") || lower.includes("several") || lower.includes("sometimes") ||
        lower.includes("elevated") || lower.includes("slightly")) {
      return Math.ceil(q.affects_duration / 2);
    }
    return 0;
  }

  // For multi_choice: more selections = more time (proportional)
  if (q.question_type === "multi_choice" && Array.isArray(ans.answer)) {
    const count = ans.answer.length;
    if (count >= 3) return q.affects_duration;
    if (count >= 2) return Math.ceil(q.affects_duration / 2);
    return 0;
  }

  // Free text: always add the duration (we can't easily assess free text)
  if (q.question_type === "free_text") {
    return Math.ceil(q.affects_duration / 2);
  }

  return 0;
}

/**
 * Assess whether an answer should escalate urgency.
 */
function assessUrgencyImpact(q: FollowUpQuestion, ans: FollowUpAnswer): UrgencyLevel | null {
  if (!q.affects_urgency) return null;

  const targetUrgency = q.affects_urgency as UrgencyLevel;

  // For scale: >7 triggers urgency escalation
  if (q.question_type === "scale" && typeof ans.answer === "number") {
    if (ans.answer >= 8) return targetUrgency;
    return null;
  }

  // For single_choice: severe/worsening answers trigger escalation
  if (q.question_type === "single_choice" && typeof ans.answer === "string") {
    const lower = ans.answer.toLowerCase();
    if (lower.includes("severe") || lower.includes("rapidly") || lower.includes("struggling") ||
        lower.includes("worse") || lower.includes("can't") || lower.includes("over 103") ||
        lower.includes("very high")) {
      return targetUrgency;
    }
    return null;
  }

  // For multi_choice: concerning symptoms trigger escalation
  if (q.question_type === "multi_choice" && Array.isArray(ans.answer)) {
    const concerning = ans.answer.some(a => {
      const l = a.toLowerCase();
      return l.includes("fever") || l.includes("bleeding") || l.includes("vision") ||
             l.includes("chest") || l.includes("breathing") || l.includes("neck stiffness");
    });
    if (concerning) return targetUrgency;
    return null;
  }

  return null;
}

/**
 * Build an enriched version of the patient's input that
 * incorporates their follow-up answers for re-classification.
 */
function buildEnrichedInput(
  originalInput: string,
  answers: FollowUpAnswer[],
  questions: FollowUpQuestion[]
): string {
  const qMap = new Map(questions.map(q => [q.id, q]));
  const parts = [originalInput];

  for (const ans of answers) {
    const q = qMap.get(ans.questionId);
    if (!q) continue;

    if (typeof ans.answer === "string") {
      parts.push(ans.answer);
    } else if (Array.isArray(ans.answer)) {
      parts.push(ans.answer.join(", "));
    } else if (typeof ans.answer === "number") {
      // For scale, add severity context
      if (ans.answer >= 7) parts.push("severe");
      else if (ans.answer >= 4) parts.push("moderate");
    }
  }

  return parts.join(". ");
}

function urgencyRank(level: UrgencyLevel): number {
  const ranks: Record<string, number> = {
    routine: 0, soon: 1, urgent: 2, emergency: 3,
  };
  return ranks[level] ?? 0;
}
