import api from "./api";

export interface EpicLaunchResponse {
  url: string | null;
  available: boolean;
}

/** Patient: get MyChart link for the authenticated patient's own record. */
export async function getPatientEpicLaunchUrl(): Promise<EpicLaunchResponse> {
  const { data } = await api.get<EpicLaunchResponse>("/patients/me/epic-launch");
  return data;
}

/** Physician: get SMART on FHIR launch URL for a specific patient chart. */
export async function getPhysicianEpicLaunchUrl(patientId: string): Promise<EpicLaunchResponse> {
  const { data } = await api.get<EpicLaunchResponse>(`/patients/${patientId}/epic-launch`);
  return data;
}
