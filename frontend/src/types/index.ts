/* ──────────────────────────── Roles & Users ──────────────────────────── */

export type Role = "patient" | "scheduler" | "nurse" | "physician" | "admin";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  assigned_physician_id?: string;
  created_at: string;
  updated_at: string;
}

/* ──────────────────────────── Appointments ──────────────────────────── */

export type AppointmentStatus =
  | "pending_intake"
  | "intake_complete"
  | "scheduled"
  | "confirmed"
  | "checked_in"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "no_show";

export type VisitType = "yearly_checkup" | "specific_concern";

export interface Appointment {
  id: string;
  patient_id: string;
  physician_id: string;
  scheduler_id?: string;
  visit_type: VisitType;
  status: AppointmentStatus;
  scheduled_start?: string;
  scheduled_end?: string;
  ai_suggested_duration: number | null;
  ai_confidence?: number | null;
  ai_duration_range_min?: number | null;
  ai_duration_range_max?: number | null;
  scheduler_approved_duration: number | null;
  scheduler_override_reason?: string;
  actual_duration?: number | null;
  initial_reason?: string;
  is_new_patient?: boolean;
  is_updated?: boolean;
  version?: number;
  red_flags?: RedFlagAlert[];
  summary?: string;
  feedback_submitted?: boolean;
  patient_name?: string;
  created_at: string;
  updated_at?: string;
}

/* ──────────────────────── Conversation / Intake ──────────────────────── */

export interface ConversationSession {
  id: string;
  appointment_id: string;
  patient_id: string;
  visit_type: VisitType;
  status: "in_progress" | "completed" | "abandoned";
  disclaimer_accepted: boolean;
  current_question_index: number;
  total_questions: number;
  max_questions: number;
  concerns: string[];
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  role: "system" | "assistant" | "patient";
  content: string;
  question_type?: "yes_no" | "short_answer" | "multiple_choice" | "ranking";
  options?: string[];
  timestamp: string;
}

/* ──────────────────────────── AI Reports ──────────────────────────── */

export interface AIReport {
  id: string;
  suggested_duration: number;
  confidence_level?: number;
  duration_range_min?: number;
  duration_range_max?: number;
  red_flags: RedFlagAlert[];
  complexity_score?: number;
  summary?: string;
  full_report?: string;
  probable_diagnoses?: DiagnosisSuggestion[];
  medication_interactions?: MedicationAlert[];
}

export interface DiagnosisSuggestion {
  condition: string;
  confidence: number;
  reasoning: string;
}

export interface RedFlagAlert {
  id: string;
  trigger_description: string;
  severity: "elevated" | "urgent" | "emergency";
  session_completed: boolean;
  acknowledged: boolean;
  created_at: string;
}

export interface MedicationAlert {
  drugs: string[];
  severity: "critical" | "high" | "moderate";
  description: string;
  recommendation: string;
}

/* ──────────────────────── Physician Feedback ──────────────────────── */

export type TimeAccuracy = "accurate" | "too_short" | "too_long";

export interface PhysicianFeedback {
  id: string;
  appointment_id: string;
  physician_id: string;
  time_accuracy: TimeAccuracy;
  actual_duration?: number;
  reason?: string;
  additional_notes?: string;
  created_at: string;
}

/* ──────────────────────── Scheduler Override ──────────────────────── */

export interface SchedulerOverride {
  id: string;
  appointment_id: string;
  scheduler_id: string;
  original_duration: number;
  overridden_duration: number;
  reason: string;
  created_at: string;
}

/* ────────────────────────── Calendar Types ────────────────────────── */

export type CalendarViewType = "day" | "week" | "month";

export interface CalendarSlot {
  date: string;
  time: string;
  duration: number;
  available: boolean;
  appointment_id?: string;
  appointment?: Appointment;
}

export interface CalendarView {
  view_type: CalendarViewType;
  start_date: string;
  end_date: string;
  slots: CalendarSlot[];
  conflicts: SchedulingConflict[];
}

export interface SchedulingConflict {
  id: string;
  appointment_id: string;
  type: "overlap" | "insufficient_time" | "physician_unavailable";
  description: string;
  suggested_alternatives: AlternativeSlot[];
}

export interface AlternativeSlot {
  date: string;
  time: string;
  duration: number;
  physician_id: string;
  physician_name: string;
}

/* ──────────────────────── Priority Ranking ──────────────────────── */

export interface PriorityItem {
  appointment_id: string;
  patient_name: string;
  priority_score: number;
  reason: string;
  red_flag_count: number;
  waiting_days: number;
}

/* ────────────────────── API Response Wrappers ────────────────────── */

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface AppointmentFilters {
  status?: AppointmentStatus;
  visit_type?: VisitType;
  physician_id?: string;
  patient_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  per_page?: number;
}
