import api from "./api";
import type { Appointment } from "../types";

interface AppointmentListResponse {
  items: Appointment[];
  total: number;
  page: number;
  per_page: number;
}

export async function requestReschedule(id: string, reason?: string): Promise<Appointment> {
  const { data } = await api.put<Appointment>(`/appointments/${id}`, {
    status: "reschedule_requested",
    scheduler_override_reason: reason,
  });
  return data;
}

export async function listAppointments(
  filters?: Record<string, unknown>,
): Promise<Appointment[]> {
  const { data } = await api.get<AppointmentListResponse>(
    "/appointments/",
    { params: filters },
  );
  return data.items;
}

export async function getAppointment(id: string): Promise<Appointment> {
  const { data } = await api.get<Appointment>(`/appointments/${id}`);
  return data;
}

export async function createAppointment(
  payload: Partial<Appointment>,
): Promise<Appointment> {
  const { data } = await api.post<Appointment>("/appointments/", payload);
  return data;
}

export async function updateAppointment(
  id: string,
  payload: Partial<Appointment>,
): Promise<Appointment> {
  const { data } = await api.put<Appointment>(
    `/appointments/${id}`,
    payload,
  );
  return data;
}

export async function getAvailableSlots(
  date: string,
  duration?: number,
): Promise<{ start: string; end: string; label: string }[]> {
  const { data } = await api.get("/appointments/available-slots", {
    params: { date, ...(duration ? { duration } : {}) },
  });
  return data;
}

export async function getConflicts(): Promise<unknown[]> {
  const { data } = await api.get("/appointments/conflicts");
  return data;
}

export async function getPriorityRanking(): Promise<unknown> {
  const { data } = await api.get("/appointments/priority-ranking");
  return data;
}

export async function cancelAppointment(id: string): Promise<Appointment> {
  const { data } = await api.put<Appointment>(`/appointments/${id}/cancel`);
  return data;
}

export async function approveDuration(
  appointmentId: string,
  duration: number,
  reason?: string,
): Promise<Appointment> {
  const { data } = await api.put<Appointment>(
    `/appointments/${appointmentId}`,
    {
      scheduler_approved_duration: duration,
      scheduler_override_reason: reason,
      status: "scheduled",
    },
  );
  return data;
}
