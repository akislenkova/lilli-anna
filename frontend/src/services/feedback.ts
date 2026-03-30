import api from "./api";
import type { TimeAccuracy } from "../types";

export interface FeedbackPayload {
  appointment_id: string;
  time_accuracy: TimeAccuracy;
  actual_vs_suggested_delta: number;
  reason_text?: string;
}

interface FeedbackResponse {
  id: string;
  appointment_id: string;
  time_accuracy: string;
  actual_vs_suggested_delta: number;
  created_at: string;
}

export async function submitFeedback(
  payload: FeedbackPayload,
): Promise<FeedbackResponse> {
  const { data } = await api.post<FeedbackResponse>(
    "/feedback",
    payload,
  );
  return data;
}

export async function getFeedback(
  appointmentId: string,
): Promise<FeedbackResponse | null> {
  try {
    const { data } = await api.get<FeedbackResponse>(
      `/feedback/appointment/${appointmentId}`,
    );
    return data;
  } catch {
    return null;
  }
}
