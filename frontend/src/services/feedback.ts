import api from "./api";
import type { PhysicianFeedback, TimeAccuracy } from "../types";

export interface FeedbackPayload {
  appointment_id: string;
  time_accuracy: TimeAccuracy;
  actual_duration?: number;
  reason?: string;
  additional_notes?: string;
}

export async function submitFeedback(
  payload: FeedbackPayload,
): Promise<PhysicianFeedback> {
  const { data } = await api.post<{ data: PhysicianFeedback }>(
    "/feedback",
    payload,
  );
  return data.data;
}

export async function getFeedback(
  appointmentId: string,
): Promise<PhysicianFeedback | null> {
  try {
    const { data } = await api.get<{ data: PhysicianFeedback }>(
      `/feedback/${appointmentId}`,
    );
    return data.data;
  } catch {
    return null;
  }
}
