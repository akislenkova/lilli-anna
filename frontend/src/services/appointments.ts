import api from "./api";
import type {
  Appointment,
  AppointmentFilters,
  CalendarView,
  CalendarViewType,
  PaginatedResponse,
  PriorityItem,
  SchedulingConflict,
} from "../types";

export async function listAppointments(
  filters?: AppointmentFilters,
): Promise<PaginatedResponse<Appointment>> {
  const { data } = await api.get<PaginatedResponse<Appointment>>(
    "/appointments",
    { params: filters },
  );
  return data;
}

export async function getAppointment(id: string): Promise<Appointment> {
  const { data } = await api.get<{ data: Appointment }>(
    `/appointments/${id}`,
  );
  return data.data;
}

export async function createAppointment(
  payload: Partial<Appointment>,
): Promise<Appointment> {
  const { data } = await api.post<{ data: Appointment }>(
    "/appointments",
    payload,
  );
  return data.data;
}

export async function updateAppointment(
  id: string,
  payload: Partial<Appointment>,
): Promise<Appointment> {
  const { data } = await api.patch<{ data: Appointment }>(
    `/appointments/${id}`,
    payload,
  );
  return data.data;
}

export async function cancelAppointment(id: string): Promise<void> {
  await api.post(`/appointments/${id}/cancel`);
}

export async function getCalendar(
  viewType: CalendarViewType,
  date?: string,
): Promise<CalendarView> {
  const { data } = await api.get<{ data: CalendarView }>("/calendar", {
    params: { view: viewType, date },
  });
  return data.data;
}

export async function getConflicts(): Promise<SchedulingConflict[]> {
  const { data } = await api.get<{ data: SchedulingConflict[] }>(
    "/appointments/conflicts",
  );
  return data.data;
}

export async function getPriorityRanking(): Promise<PriorityItem[]> {
  const { data } = await api.get<{ data: PriorityItem[] }>(
    "/appointments/priority",
  );
  return data.data;
}

export async function approveDuration(
  appointmentId: string,
  duration: number,
  reason?: string,
): Promise<Appointment> {
  const { data } = await api.post<{ data: Appointment }>(
    `/appointments/${appointmentId}/approve-duration`,
    { duration, reason },
  );
  return data.data;
}
