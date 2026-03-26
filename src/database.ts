// src/database.ts
// ─────────────────────────────────────────────────────────
// SQLite database for follow-up question templates, appointment
// state, and NLP-driven clarification flows.
// ─────────────────────────────────────────────────────────

import Database from "better-sqlite3";
import path from "node:path";
import { VisitCategory, UrgencyLevel } from "../index";

const DB_PATH = process.env.DB_PATH || path.join(process.cwd(), "scheduling.db");

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma("journal_mode = WAL");
    db.pragma("foreign_keys = ON");
    initializeSchema(db);
    seedFollowUpQuestions(db);
  }
  return db;
}

// ─────────────────────────────────────────────────────────
// SCHEMA
// ─────────────────────────────────────────────────────────

function initializeSchema(d: Database.Database): void {

  d.exec(`
    -- Follow-up question templates keyed by visit category + trigger keywords
    CREATE TABLE IF NOT EXISTS follow_up_questions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL,
      trigger_keywords TEXT NOT NULL,   -- comma-separated keywords that activate this question
      question_text TEXT NOT NULL,
      question_type TEXT NOT NULL DEFAULT 'single_choice',  -- single_choice | multi_choice | free_text | scale
      options TEXT,                     -- JSON array of options (for choice types)
      priority INTEGER NOT NULL DEFAULT 5,  -- 1=highest, 10=lowest
      affects_duration INTEGER NOT NULL DEFAULT 0,  -- extra minutes if answered affirmatively
      affects_urgency TEXT,             -- can escalate urgency: 'soon', 'urgent', 'emergency'
      required INTEGER NOT NULL DEFAULT 0,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Patient sessions: tracks the full conversation flow across all 3 views
    CREATE TABLE IF NOT EXISTS patient_sessions (
      id TEXT PRIMARY KEY,
      patient_id TEXT,
      patient_name TEXT,
      mrn TEXT,
      is_new_patient INTEGER NOT NULL DEFAULT 0,
      initial_input TEXT NOT NULL,
      classification_json TEXT,
      allocation_json TEXT,
      follow_up_answers_json TEXT,     -- answers to follow-up questions
      refined_classification_json TEXT, -- classification after follow-up
      refined_allocation_json TEXT,     -- allocation after follow-up
      status TEXT NOT NULL DEFAULT 'intake',  -- intake | follow_up | classified | scheduled | confirmed
      selected_slot TEXT,
      booked_appointment_id TEXT,
      physician_notes TEXT,
      scheduler_override_minutes INTEGER,
      urgency_level TEXT NOT NULL DEFAULT 'routine',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- NLP extraction cache: stores extracted entities from patient input
    CREATE TABLE IF NOT EXISTS nlp_extractions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL REFERENCES patient_sessions(id),
      entity_type TEXT NOT NULL,       -- symptom | duration | severity | body_part | medication | condition
      entity_value TEXT NOT NULL,
      confidence REAL NOT NULL DEFAULT 0.5,
      source_text TEXT,                -- the substring it was extracted from
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_followup_category ON follow_up_questions(category);
    CREATE INDEX IF NOT EXISTS idx_followup_active ON follow_up_questions(active);
    CREATE INDEX IF NOT EXISTS idx_sessions_status ON patient_sessions(status);
    CREATE INDEX IF NOT EXISTS idx_sessions_patient ON patient_sessions(patient_id);
    CREATE INDEX IF NOT EXISTS idx_extractions_session ON nlp_extractions(session_id);
  `);
}

// ─────────────────────────────────────────────────────────
// SEED DATA: Follow-up question templates
// ─────────────────────────────────────────────────────────

function seedFollowUpQuestions(d: Database.Database): void {
  const count = d.prepare("SELECT COUNT(*) as n FROM follow_up_questions").get() as any;
  if (count.n > 0) return; // Already seeded

  const insert = d.prepare(`
    INSERT INTO follow_up_questions
    (category, trigger_keywords, question_text, question_type, options, priority, affects_duration, affects_urgency, required)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const questions = [
    // ── ACUTE ILLNESS ──────────────────────
    ["acute_illness", "headache,migraine,head pain", "How long have you been experiencing headaches?", "single_choice",
      JSON.stringify(["Less than 24 hours", "A few days", "More than a week", "More than a month"]),
      1, 5, "soon", 1],
    ["acute_illness", "headache,migraine", "How would you rate your headache pain?", "scale",
      JSON.stringify({ min: 1, max: 10, labels: { 1: "Mild", 5: "Moderate", 10: "Worst ever" } }),
      2, 0, null, 1],
    ["acute_illness", "headache,migraine", "Have you experienced any of these with your headache?", "multi_choice",
      JSON.stringify(["Vision changes", "Nausea/vomiting", "Sensitivity to light", "Neck stiffness", "Fever", "Dizziness", "None of these"]),
      3, 10, "urgent", 0],
    ["acute_illness", "fever,temperature", "What was your highest temperature?", "single_choice",
      JSON.stringify(["99-100°F (low-grade)", "100-101°F", "101-103°F", "Over 103°F", "I haven't checked"]),
      1, 5, "urgent", 1],
    ["acute_illness", "fever,temperature", "How long have you had a fever?", "single_choice",
      JSON.stringify(["Started today", "1-2 days", "3-5 days", "More than 5 days"]),
      2, 5, "soon", 1],
    ["acute_illness", "cough,congestion,cold,flu", "Are you experiencing any difficulty breathing?", "single_choice",
      JSON.stringify(["No", "Mild — winded with activity", "Moderate — at rest sometimes", "Severe — struggling to breathe"]),
      1, 10, "emergency", 1],
    ["acute_illness", "cough", "What type of cough do you have?", "single_choice",
      JSON.stringify(["Dry cough", "Productive (bringing up mucus)", "Coughing up blood", "Barking/croup-like"]),
      2, 5, "urgent", 0],
    ["acute_illness", "rash,skin", "Where is the rash located?", "multi_choice",
      JSON.stringify(["Face", "Arms", "Legs", "Torso", "Widespread / all over"]),
      1, 0, null, 1],
    ["acute_illness", "rash,skin", "Is the rash spreading or getting worse?", "single_choice",
      JSON.stringify(["No, it's stable", "Yes, slowly spreading", "Yes, rapidly spreading", "It comes and goes"]),
      2, 5, "soon", 0],
    ["acute_illness", "pain,hurt,ache", "Where is your pain located?", "free_text", null, 1, 0, null, 1],
    ["acute_illness", "pain,hurt,ache", "Rate your pain level:", "scale",
      JSON.stringify({ min: 1, max: 10, labels: { 1: "Barely noticeable", 5: "Moderate", 10: "Unbearable" } }),
      2, 5, "urgent", 1],
    ["acute_illness", "nausea,vomiting,stomach", "Are you able to keep food and liquids down?", "single_choice",
      JSON.stringify(["Yes, eating normally", "Some nausea but can eat", "Vomiting occasionally", "Can't keep anything down"]),
      1, 5, "urgent", 1],

    // ── CHRONIC MANAGEMENT ─────────────────
    ["chronic_management", "diabetes,blood sugar,a1c", "When was your last A1C test?", "single_choice",
      JSON.stringify(["Within 3 months", "3-6 months ago", "6-12 months ago", "Over a year ago", "I'm not sure"]),
      1, 5, null, 1],
    ["chronic_management", "diabetes,blood sugar", "Have your blood sugar levels been in range recently?", "single_choice",
      JSON.stringify(["Mostly in range", "Running higher than usual", "Running lower than usual", "Very unstable", "I don't check regularly"]),
      2, 5, null, 1],
    ["chronic_management", "hypertension,blood pressure", "Do you monitor your blood pressure at home?", "single_choice",
      JSON.stringify(["Yes, regularly", "Sometimes", "No"]),
      1, 0, null, 0],
    ["chronic_management", "hypertension,blood pressure", "What have your recent blood pressure readings been?", "single_choice",
      JSON.stringify(["Normal (under 130/80)", "Slightly elevated (130-140/80-90)", "High (over 140/90)", "Very high (over 160/100)", "I don't know"]),
      2, 5, "soon", 1],
    ["chronic_management", "asthma,copd,breathing", "How often are you using your rescue inhaler?", "single_choice",
      JSON.stringify(["Rarely / less than 2x per week", "Several times a week", "Daily", "Multiple times per day"]),
      1, 5, "soon", 1],
    ["chronic_management", "thyroid", "Have you noticed any changes in energy, weight, or mood?", "multi_choice",
      JSON.stringify(["Fatigue / low energy", "Weight gain", "Weight loss", "Feeling anxious/jittery", "Feeling cold", "Hair thinning", "No changes"]),
      1, 5, null, 0],

    // ── MENTAL HEALTH ──────────────────────
    ["mental_health", "anxiety,panic,stress,overwhelmed", "How often have you been feeling anxious in the past 2 weeks?", "single_choice",
      JSON.stringify(["Occasionally", "Several days", "More than half the days", "Nearly every day"]),
      1, 5, null, 1],
    ["mental_health", "anxiety,panic", "Have you experienced panic attacks?", "single_choice",
      JSON.stringify(["No", "Once or twice", "Weekly", "Multiple times per week"]),
      2, 5, "soon", 0],
    ["mental_health", "depression,feeling down,hopeless,sad", "Over the past 2 weeks, how often have you felt down or hopeless?", "single_choice",
      JSON.stringify(["Not at all", "Several days", "More than half the days", "Nearly every day"]),
      1, 5, null, 1],
    ["mental_health", "depression,feeling down", "Have you lost interest in things you usually enjoy?", "single_choice",
      JSON.stringify(["No", "Somewhat", "Yes, noticeably", "Yes, in almost everything"]),
      2, 5, null, 0],
    ["mental_health", "sleep,insomnia,can't sleep", "Describe your sleep difficulty:", "single_choice",
      JSON.stringify(["Trouble falling asleep", "Waking up during the night", "Waking too early", "Sleeping too much", "Not feeling rested"]),
      1, 0, null, 1],
    ["mental_health", "anxiety,depression,stress,mental health", "Are you currently seeing a therapist or counselor?", "single_choice",
      JSON.stringify(["Yes", "No, but interested", "No, not interested", "I was, but stopped"]),
      3, 0, null, 0],
    ["mental_health", "anxiety,depression,stress,mental health", "Are you currently taking any mental health medications?", "single_choice",
      JSON.stringify(["Yes", "No", "I was, but stopped", "I'd like to discuss options"]),
      4, 5, null, 0],

    // ── PRESCRIPTION REFILL ────────────────
    ["prescription_refill", "refill,prescription,medication,rx", "Which medication(s) do you need refilled?", "free_text",
      null, 1, 0, null, 1],
    ["prescription_refill", "refill,prescription,medication", "Have you experienced any side effects from your medication?", "single_choice",
      JSON.stringify(["No side effects", "Mild side effects", "Moderate side effects", "Severe side effects — I stopped taking it"]),
      2, 10, null, 0],
    ["prescription_refill", "refill,prescription,medication", "Are you taking the medication as prescribed?", "single_choice",
      JSON.stringify(["Yes, exactly as prescribed", "Usually, but I miss doses sometimes", "I've been taking a different dose", "I stopped taking it"]),
      3, 5, null, 0],

    // ── FOLLOW UP ──────────────────────────
    ["follow_up", "follow up,followup,follow-up,recheck", "What were you originally seen for?", "free_text",
      null, 1, 0, null, 1],
    ["follow_up", "follow up,followup,follow-up", "Has your condition improved since your last visit?", "single_choice",
      JSON.stringify(["Fully resolved", "Mostly better", "About the same", "Slightly worse", "Much worse"]),
      2, 5, "soon", 1],
    ["follow_up", "surgery,post-op,after surgery", "How many days/weeks has it been since your procedure?", "free_text",
      null, 1, 0, null, 1],
    ["follow_up", "surgery,post-op", "Are you experiencing any of these post-surgical concerns?", "multi_choice",
      JSON.stringify(["Increased pain", "Swelling", "Redness/warmth at site", "Drainage/discharge", "Fever", "None of these"]),
      2, 10, "urgent", 0],

    // ── LAB REVIEW ─────────────────────────
    ["lab_review", "lab,results,blood work,test results,bloodwork", "Do you know which tests were done?", "free_text",
      null, 1, 0, null, 0],
    ["lab_review", "lab,results,blood work", "Were you told any results were abnormal?", "single_choice",
      JSON.stringify(["Yes", "No", "I haven't heard anything yet", "I saw them in MyChart but don't understand"]),
      2, 5, null, 0],

    // ── PROCEDURE (MINOR) ──────────────────
    ["procedure_minor", "mole,skin tag,wart,removal,injection,shot", "Which area of the body is this for?", "free_text",
      null, 1, 0, null, 1],
    ["procedure_minor", "mole,skin", "Has this area changed recently (size, color, shape)?", "single_choice",
      JSON.stringify(["No changes", "Changed slightly", "Changed noticeably", "Changed rapidly"]),
      2, 5, "soon", 0],

    // ── PREVENTIVE / SCREENING ─────────────
    ["preventive_screening", "physical,annual,wellness,checkup,screening", "Are there any specific concerns you'd like addressed during your visit?", "free_text",
      null, 1, 5, null, 0],
    ["preventive_screening", "vaccination,vaccine,flu shot,immunization", "Which vaccine are you interested in?", "single_choice",
      JSON.stringify(["Flu shot", "COVID booster", "Shingles", "Tdap", "Pneumonia", "Other", "Not sure — I want to discuss"]),
      1, 0, null, 1],

    // ── NEW PATIENT ────────────────────────
    ["new_patient_intake", "new patient,first visit,first time,establishing care", "What is the main reason you're establishing care?", "single_choice",
      JSON.stringify(["Moving to the area", "Changing doctors", "Haven't had a doctor in a while", "Referred by another provider", "Specific health concern"]),
      1, 0, null, 1],
    ["new_patient_intake", "new patient,first visit", "Do you have any chronic conditions we should know about?", "multi_choice",
      JSON.stringify(["Diabetes", "High blood pressure", "Heart disease", "Asthma/COPD", "Thyroid disorder", "Mental health condition", "Cancer history", "None", "Other"]),
      2, 10, null, 1],
    ["new_patient_intake", "new patient,first visit", "How many prescription medications are you currently taking?", "single_choice",
      JSON.stringify(["None", "1-2", "3-5", "More than 5"]),
      3, 5, null, 0],

    // ── CONSULTATION ───────────────────────
    ["consultation", "second opinion,specialist,consult,discuss options", "What condition or diagnosis are you seeking a consultation for?", "free_text",
      null, 1, 0, null, 1],
    ["consultation", "second opinion,specialist", "Have you already received a diagnosis or treatment plan?", "single_choice",
      JSON.stringify(["Yes, I want a second opinion", "Yes, but I'd like to explore other options", "No, I'm looking for initial guidance"]),
      2, 5, null, 0],

    // ── URGENT CARE ────────────────────────
    ["urgent_care", "urgent,severe,emergency,bleeding,broken", "When did this start?", "single_choice",
      JSON.stringify(["Just now / within the hour", "Today", "Yesterday", "A few days ago"]),
      1, 0, "urgent", 1],
    ["urgent_care", "urgent,severe,emergency", "Is the condition getting worse?", "single_choice",
      JSON.stringify(["Stable", "Slowly worsening", "Rapidly worsening"]),
      2, 5, "emergency", 1],
  ];

  const insertMany = d.transaction(() => {
    for (const q of questions) {
      insert.run(...q);
    }
  });
  insertMany();
}

// ─────────────────────────────────────────────────────────
// QUERY HELPERS
// ─────────────────────────────────────────────────────────

export interface FollowUpQuestion {
  id: number;
  category: string;
  trigger_keywords: string;
  question_text: string;
  question_type: "single_choice" | "multi_choice" | "free_text" | "scale";
  options: any;
  priority: number;
  affects_duration: number;
  affects_urgency: string | null;
  required: boolean;
}

/**
 * Get follow-up questions relevant to the classified categories
 * and the specific keywords that matched in the patient's input.
 */
export function getFollowUpQuestions(
  categories: string[],
  matchedKeywords: string[]
): FollowUpQuestion[] {
  const d = getDb();

  // Get all active questions for the matched categories
  const placeholders = categories.map(() => "?").join(",");
  const rows = d.prepare(`
    SELECT * FROM follow_up_questions
    WHERE category IN (${placeholders})
    AND active = 1
    ORDER BY priority ASC
  `).all(...categories) as any[];

  // Filter by keyword relevance: the question's trigger_keywords
  // must overlap with what the patient actually said
  const lowerMatched = matchedKeywords.map(k => k.toLowerCase());

  const relevant = rows.filter(row => {
    const triggers = row.trigger_keywords.split(",").map((t: string) => t.trim().toLowerCase());
    // A question is relevant if any of its trigger keywords appear
    // in the patient's matched keywords OR in the patient's input categories
    return triggers.some((t: string) =>
      lowerMatched.some(m => m.includes(t) || t.includes(m))
    );
  });

  return relevant.map(row => ({
    ...row,
    options: row.options ? JSON.parse(row.options) : null,
    required: !!row.required,
  }));
}

// ─────────────────────────────────────────────────────────
// SESSION MANAGEMENT
// ─────────────────────────────────────────────────────────

export interface SessionData {
  id: string;
  patient_id: string | null;
  patient_name: string | null;
  mrn: string | null;
  is_new_patient: boolean;
  initial_input: string;
  classification_json: any;
  allocation_json: any;
  follow_up_answers_json: any;
  refined_classification_json: any;
  refined_allocation_json: any;
  status: string;
  selected_slot: string | null;
  booked_appointment_id: string | null;
  physician_notes: string | null;
  scheduler_override_minutes: number | null;
  urgency_level: string;
  created_at: string;
  updated_at: string;
}

export function createSession(data: {
  id: string;
  initial_input: string;
  patient_id?: string;
  patient_name?: string;
  mrn?: string;
  is_new_patient?: boolean;
}): void {
  const d = getDb();
  d.prepare(`
    INSERT INTO patient_sessions (id, initial_input, patient_id, patient_name, mrn, is_new_patient)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    data.id,
    data.initial_input,
    data.patient_id || null,
    data.patient_name || null,
    data.mrn || null,
    data.is_new_patient ? 1 : 0
  );
}

export function updateSession(id: string, updates: Partial<Record<string, any>>): void {
  const d = getDb();
  const fields = Object.keys(updates);
  const sets = fields.map(f => `${f} = ?`).join(", ");
  const values = fields.map(f => {
    const v = updates[f];
    return typeof v === "object" && v !== null ? JSON.stringify(v) : v;
  });
  d.prepare(`UPDATE patient_sessions SET ${sets}, updated_at = datetime('now') WHERE id = ?`)
    .run(...values, id);
}

export function getSession(id: string): SessionData | null {
  const d = getDb();
  const row = d.prepare("SELECT * FROM patient_sessions WHERE id = ?").get(id) as any;
  if (!row) return null;
  return {
    ...row,
    is_new_patient: !!row.is_new_patient,
    classification_json: row.classification_json ? JSON.parse(row.classification_json) : null,
    allocation_json: row.allocation_json ? JSON.parse(row.allocation_json) : null,
    follow_up_answers_json: row.follow_up_answers_json ? JSON.parse(row.follow_up_answers_json) : null,
    refined_classification_json: row.refined_classification_json ? JSON.parse(row.refined_classification_json) : null,
    refined_allocation_json: row.refined_allocation_json ? JSON.parse(row.refined_allocation_json) : null,
  };
}

export function getAllSessions(status?: string): SessionData[] {
  const d = getDb();
  let rows: any[];
  if (status) {
    rows = d.prepare("SELECT * FROM patient_sessions WHERE status = ? ORDER BY created_at DESC").all(status) as any[];
  } else {
    rows = d.prepare("SELECT * FROM patient_sessions ORDER BY created_at DESC").all() as any[];
  }
  return rows.map(row => ({
    ...row,
    is_new_patient: !!row.is_new_patient,
    classification_json: row.classification_json ? JSON.parse(row.classification_json) : null,
    allocation_json: row.allocation_json ? JSON.parse(row.allocation_json) : null,
    follow_up_answers_json: row.follow_up_answers_json ? JSON.parse(row.follow_up_answers_json) : null,
    refined_classification_json: row.refined_classification_json ? JSON.parse(row.refined_classification_json) : null,
    refined_allocation_json: row.refined_allocation_json ? JSON.parse(row.refined_allocation_json) : null,
  }));
}

// ─────────────────────────────────────────────────────────
// NLP EXTRACTION STORAGE
// ─────────────────────────────────────────────────────────

export function saveExtraction(data: {
  session_id: string;
  entity_type: string;
  entity_value: string;
  confidence: number;
  source_text?: string;
}): void {
  const d = getDb();
  d.prepare(`
    INSERT INTO nlp_extractions (session_id, entity_type, entity_value, confidence, source_text)
    VALUES (?, ?, ?, ?, ?)
  `).run(data.session_id, data.entity_type, data.entity_value, data.confidence, data.source_text || null);
}

export function getExtractions(sessionId: string): Array<{
  entity_type: string;
  entity_value: string;
  confidence: number;
  source_text: string | null;
}> {
  const d = getDb();
  return d.prepare(
    "SELECT entity_type, entity_value, confidence, source_text FROM nlp_extractions WHERE session_id = ?"
  ).all(sessionId) as any[];
}
