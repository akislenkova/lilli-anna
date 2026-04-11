import api from "./api";

// ── Existing: MyChart deep-link ───────────────────────────────────────────────

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

// ── New: patient SMART on FHIR connection (reads records INTO Anilla) ─────────

export interface EpicStatus {
  available: boolean;
  connected: boolean;
  epic_patient_id?: string | null;
  scope?: string | null;
}

export interface FhirCondition {
  id: string;
  code_display: string;
  clinical_status: string;
  onset_date?: string | null;
}

export interface FhirMedication {
  id: string;
  medication_display: string;
  status: string;
  dosage?: string | null;
  authored_on?: string | null;
}

export interface FhirAllergy {
  id: string;
  substance_display: string;
  criticality?: string | null;
  reaction?: string | null;
}

export interface FhirObservation {
  id: string;
  code_display: string;
  value: string;
  effective_date?: string | null;
}

export interface EpicRecordsResponse {
  available: boolean;
  connected: boolean;
  error?: string;
  patient?: {
    name?: string | null;
    birth_date?: string | null;
    gender?: string | null;
  } | null;
  conditions: FhirCondition[];
  medications: FhirMedication[];
  allergies: FhirAllergy[];
  observations: FhirObservation[];
  last_synced?: string | null;
}

/** Check whether the patient has connected their Epic account. */
export async function getEpicStatus(): Promise<EpicStatus> {
  const { data } = await api.get<EpicStatus>("/patients/me/epic/status");
  return data;
}

/** Kick off the SMART on FHIR auth flow — returns the authorization URL. */
export async function startEpicAuth(): Promise<{ available: boolean; url: string | null }> {
  const { data } = await api.get<{ available: boolean; url: string | null }>(
    "/patients/me/epic/auth-url"
  );
  return data;
}

/** Exchange the OAuth authorization code returned by Epic's callback. */
export async function connectEpic(body: {
  code: string;
  state: string;
}): Promise<{ connected: boolean; epic_patient_id?: string }> {
  const { data } = await api.post("/patients/me/epic/connect", body);
  return data;
}

/** Fetch live FHIR records from Epic for the authenticated patient. */
export async function getEpicRecords(): Promise<EpicRecordsResponse> {
  const { data } = await api.get<EpicRecordsResponse>("/patients/me/epic/records");
  return data;
}

/** Remove the patient's stored Epic tokens. */
export async function disconnectEpic(): Promise<void> {
  await api.delete("/patients/me/epic/disconnect");
}
