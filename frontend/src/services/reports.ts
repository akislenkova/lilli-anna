import api from "./api";
import type { AIReport, RedFlagAlert } from "../types";

export async function getReport(appointmentId: string): Promise<AIReport> {
  const { data } = await api.get<AIReport>(
    `/reports/${appointmentId}`,
  );
  return data;
}

export async function getRedFlags(
  appointmentId: string,
): Promise<RedFlagAlert[]> {
  const { data } = await api.get<RedFlagAlert[]>(
    `/reports/${appointmentId}/red-flags`,
  );
  return data;
}

export async function acknowledgeRedFlag(
  appointmentId: string,
  flagId: string,
): Promise<RedFlagAlert> {
  const { data } = await api.put<RedFlagAlert>(
    `/reports/${appointmentId}/red-flags/${flagId}/acknowledge`,
  );
  return data;
}
