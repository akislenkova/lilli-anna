import api from "./api";
import type { AIReport, RedFlagAlert } from "../types";

export async function getReport(appointmentId: string): Promise<AIReport> {
  const { data } = await api.get<{ data: AIReport }>(
    `/appointments/${appointmentId}/report`,
  );
  return data.data;
}

export async function getRedFlags(
  appointmentId: string,
): Promise<RedFlagAlert[]> {
  const { data } = await api.get<{ data: RedFlagAlert[] }>(
    `/appointments/${appointmentId}/red-flags`,
  );
  return data.data;
}

export async function acknowledgeRedFlag(
  appointmentId: string,
  flagId: string,
): Promise<RedFlagAlert> {
  const { data } = await api.post<{ data: RedFlagAlert }>(
    `/appointments/${appointmentId}/red-flags/${flagId}/acknowledge`,
  );
  return data.data;
}
