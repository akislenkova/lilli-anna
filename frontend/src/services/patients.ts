import api from "./api";
import type { Appointment } from "../types";

export interface PatientProfile {
  id: string;
  user_id: string;
  date_of_birth: string;
  primary_physician_id: string | null;
  language_preference: string;
}

export async function getMyProfile(): Promise<PatientProfile> {
  const { data } = await api.get<PatientProfile>("/patients/me/profile");
  return data;
}

export async function getMyRecords(): Promise<Appointment[]> {
  const { data } = await api.get<Appointment[]>("/patients/me/records");
  return data;
}

export async function getMyMedications(): Promise<string[]> {
  const { data } = await api.get<{ medications: string[] }>("/patients/me/medications");
  return data.medications;
}
