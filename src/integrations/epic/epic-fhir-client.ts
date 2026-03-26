// src/integrations/epic/epic-fhir-client.ts
// ─────────────────────────────────────────────────────────
// FHIR R4 client for Epic EHR / MyChart integration.
//
// This module handles OAuth2 auth, patient context, and
// the core FHIR resources needed for scheduling:
//   - Patient (demographics, history, conditions)
//   - Appointment.$find (discover available slots)
//   - Appointment.$book (book a slot)
//   - Appointment.Read (read existing appointments)
//   - Condition (active problems list)
//   - Schedule / Slot (provider availability)
//
// INTEGRATION PATH:
//   Option A: SMART on FHIR launch (embedded in MyChart)
//   Option B: Backend service (server-to-server with JWT)
//
// REQUIREMENTS:
//   - Register your app at https://open.epic.com
//   - For MyChart embedding, register through Epic Showroom
//   - HIPAA BAA with the health system
// ─────────────────────────────────────────────────────────

export interface EpicConfig {
  /** Base FHIR URL for the Epic instance, e.g. https://fhir.hospital.org/api/FHIR/R4 */
  fhirBaseUrl: string;

  /** OAuth2 token endpoint from the metadata/conformance response */
  tokenEndpoint: string;

  /** OAuth2 authorize endpoint (for SMART on FHIR launches) */
  authorizeEndpoint: string;

  /** Your registered client ID from open.epic.com */
  clientId: string;

  /** For backend service auth: path to your private key (JWT) */
  privateKeyPath?: string;

  /** Redirect URI registered with Epic */
  redirectUri: string;

  /** Scopes needed for scheduling integration */
  scopes: string[];
}

export const DEFAULT_SCOPES = [
  "patient/Patient.read",
  "patient/Appointment.read",
  "patient/Appointment.write",
  "patient/Condition.read",
  "patient/Schedule.read",
  "patient/Slot.read",
  "launch",
  "openid",
  "fhirUser",
];

/**
 * Represents an authenticated session with an Epic FHIR server.
 * Created after successful SMART on FHIR launch or backend auth.
 */
export interface EpicSession {
  accessToken: string;
  tokenType: string;
  expiresAt: Date;
  patientFhirId: string | null;  // set in patient-facing (MyChart) context
  practitionerFhirId: string | null;  // set in provider-facing context
  scope: string;
  refreshToken?: string;
}

// ─────────────────────────────────────────────────────────
// FHIR Resource Types (scheduling-relevant subset)
// ─────────────────────────────────────────────────────────

export interface FhirPatient {
  resourceType: "Patient";
  id: string;
  name: { family: string; given: string[]; use: string }[];
  birthDate: string;
  gender: string;
  identifier: { system: string; value: string }[];
  telecom: { system: string; value: string }[];
  address: { line: string[]; city: string; state: string; postalCode: string }[];
}

export interface FhirCondition {
  resourceType: "Condition";
  id: string;
  clinicalStatus: { coding: { code: string }[] };
  code: { coding: { system: string; code: string; display: string }[]; text: string };
  onsetDateTime?: string;
  category: { coding: { code: string; display: string }[] }[];
}

export interface FhirAppointment {
  resourceType: "Appointment";
  id: string;
  status: "proposed" | "pending" | "booked" | "arrived" | "fulfilled" | "cancelled" | "noshow";
  serviceType: { coding: { code: string; display: string }[] }[];
  start: string;
  end: string;
  minutesDuration: number;
  participant: {
    actor: { reference: string; display: string };
    status: string;
  }[];
  description?: string;
  comment?: string;
}

export interface FhirSlot {
  resourceType: "Slot";
  id: string;
  status: "free" | "busy" | "busy-unavailable" | "busy-tentative";
  start: string;
  end: string;
  schedule: { reference: string };
  serviceType?: { coding: { code: string; display: string }[] }[];
}

// ─────────────────────────────────────────────────────────
// EPIC FHIR CLIENT
// ─────────────────────────────────────────────────────────

export class EpicFhirClient {
  private config: EpicConfig;
  private session: EpicSession | null = null;

  constructor(config: EpicConfig) {
    this.config = config;
  }

  // ── Authentication ──────────────────────────────────

  /**
   * SMART on FHIR Launch — Step 1: Generate authorization URL.
   *
   * In MyChart context, Epic redirects here after the user
   * opens your app from the MyChart menu.
   */
  getAuthorizationUrl(state: string, launchToken?: string): string {
    const params = new URLSearchParams({
      response_type: "code",
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      scope: this.config.scopes.join(" "),
      state,
      aud: this.config.fhirBaseUrl,
    });

    if (launchToken) {
      params.set("launch", launchToken);
    }

    return `${this.config.authorizeEndpoint}?${params.toString()}`;
  }

  /**
   * SMART on FHIR Launch — Step 2: Exchange auth code for tokens.
   *
   * Called from your redirect URI handler after Epic redirects
   * back with an authorization code.
   */
  async exchangeAuthCode(code: string): Promise<EpicSession> {
    const response = await fetch(this.config.tokenEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code,
        redirect_uri: this.config.redirectUri,
        client_id: this.config.clientId,
      }),
    });

    if (!response.ok) {
      throw new Error(`Token exchange failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    this.session = {
      accessToken: data.access_token,
      tokenType: data.token_type,
      expiresAt: new Date(Date.now() + data.expires_in * 1000),
      patientFhirId: data.patient || null,
      practitionerFhirId: data.practitioner || null,
      scope: data.scope,
      refreshToken: data.refresh_token,
    };

    return this.session;
  }

  /**
   * Backend service auth using JWT assertion (for server-to-server).
   *
   * Used by the scheduler service to access the FHIR API without
   * a user in the loop. Requires a registered public key with Epic.
   */
  async authenticateBackendService(): Promise<EpicSession> {
    // TODO: Implement JWT creation + signing with private key
    // See: https://fhir.epic.com/Documentation?docId=oauth2&section=BackendOAuth2Guide
    //
    // 1. Create JWT with claims: iss=clientId, sub=clientId, aud=tokenEndpoint, jti=uuid, exp=now+5min
    // 2. Sign with RS384 using your registered private key
    // 3. POST to token endpoint with grant_type=client_credentials
    //    and client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer

    throw new Error("Backend service auth not yet implemented — see code comments for guide");
  }

  // ── FHIR Resource Operations ────────────────────────

  /**
   * Generic FHIR GET request with auth headers.
   */
  private async fhirGet<T>(path: string, params?: Record<string, string>): Promise<T> {
    this.assertAuthenticated();

    const url = new URL(`${this.config.fhirBaseUrl}/${path}`);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }

    const response = await fetch(url.toString(), {
      headers: {
        Authorization: `Bearer ${this.session!.accessToken}`,
        Accept: "application/fhir+json",
      },
    });

    if (!response.ok) {
      throw new Error(`FHIR GET ${path} failed: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Generic FHIR POST request with auth headers.
   */
  private async fhirPost<T>(path: string, body: unknown): Promise<T> {
    this.assertAuthenticated();

    const response = await fetch(`${this.config.fhirBaseUrl}/${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.session!.accessToken}`,
        "Content-Type": "application/fhir+json",
        Accept: "application/fhir+json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`FHIR POST ${path} failed: ${response.status}`);
    }

    return response.json();
  }

  // ── Patient ─────────────────────────────────────────

  /**
   * Get patient demographics from the authenticated context.
   * In MyChart launch, the patient FHIR ID comes from the token response.
   */
  async getPatient(patientId?: string): Promise<FhirPatient> {
    const id = patientId || this.session?.patientFhirId;
    if (!id) throw new Error("No patient ID available");
    return this.fhirGet<FhirPatient>(`Patient/${id}`);
  }

  // ── Conditions (Active Problems) ────────────────────

  /**
   * Get patient's active conditions / problem list.
   *
   * This enriches our AI classification — if a patient says
   * "check on my condition" we can cross-reference their
   * known diagnoses to allocate appropriate time.
   */
  async getActiveConditions(patientId?: string): Promise<FhirCondition[]> {
    const id = patientId || this.session?.patientFhirId;
    if (!id) throw new Error("No patient ID available");

    const bundle = await this.fhirGet<{ entry?: { resource: FhirCondition }[] }>("Condition", {
      patient: id,
      "clinical-status": "active",
      category: "problem-list-item",
    });

    return (bundle.entry || []).map((e) => e.resource);
  }

  // ── Appointment Discovery ($find) ───────────────────

  /**
   * Epic's custom Appointment.$find operation.
   *
   * Searches for available appointment slots matching the criteria.
   * This is the core API for our smart scheduling integration —
   * after we determine the needed duration, we call $find to get
   * slots that fit.
   */
  async findAvailableAppointments(params: {
    startTime: string;
    endTime: string;
    visitTypeId?: string;
    departmentId?: string;
    practitionerId?: string;
    patientId?: string;
  }): Promise<FhirAppointment[]> {
    const patientId = params.patientId || this.session?.patientFhirId;
    if (!patientId) throw new Error("No patient ID available");

    const findParams: Record<string, unknown> = {
      resourceType: "Parameters",
      parameter: [
        { name: "start", valueDateTime: params.startTime },
        { name: "end", valueDateTime: params.endTime },
        { name: "patient", valueReference: { reference: `Patient/${patientId}` } },
      ],
    };

    const paramList = findParams.parameter as Record<string, unknown>[];

    if (params.visitTypeId) {
      paramList.push({
        name: "service-type",
        valueCodeableConcept: {
          coding: [{ system: "urn:oid:1.2.840.114350.1.13.861.1.7.3.808267.11", code: params.visitTypeId }],
        },
      });
    }

    if (params.departmentId) {
      paramList.push({
        name: "location",
        valueReference: { reference: `Location/${params.departmentId}` },
      });
    }

    if (params.practitionerId) {
      paramList.push({
        name: "practitioner",
        valueReference: { reference: `Practitioner/${params.practitionerId}` },
      });
    }

    const bundle = await this.fhirPost<{ entry?: { resource: FhirAppointment }[] }>("Appointment/$find", findParams);
    return (bundle.entry || []).map((e) => e.resource);
  }

  // ── Appointment Booking ($book) ─────────────────────

  /**
   * Epic's custom Appointment.$book operation.
   *
   * Books a specific appointment returned by $find.
   * The appointment ID comes from the $find results.
   */
  async bookAppointment(params: {
    appointmentId: string;
    patientId?: string;
    comment?: string;
  }): Promise<FhirAppointment> {
    const patientId = params.patientId || this.session?.patientFhirId;
    if (!patientId) throw new Error("No patient ID available");

    const bookParams: Record<string, unknown> = {
      resourceType: "Parameters",
      parameter: [
        { name: "appointment", valueReference: { reference: `Appointment/${params.appointmentId}` } },
        { name: "patient", valueReference: { reference: `Patient/${patientId}` } },
      ],
    };

    const paramList = bookParams.parameter as Record<string, unknown>[];

    if (params.comment) {
      paramList.push({ name: "comment", valueString: params.comment });
    }

    return this.fhirPost<FhirAppointment>("Appointment/$book", bookParams);
  }

  // ── Existing Appointments ───────────────────────────

  /**
   * Get a patient's upcoming appointments.
   */
  async getUpcomingAppointments(patientId?: string): Promise<FhirAppointment[]> {
    const id = patientId || this.session?.patientFhirId;
    if (!id) throw new Error("No patient ID available");

    const bundle = await this.fhirGet<{ entry?: { resource: FhirAppointment }[] }>("Appointment", {
      patient: id,
      date: `ge${new Date().toISOString().split("T")[0]}`,
      status: "booked",
      _sort: "date",
    });

    return (bundle.entry || []).map((e) => e.resource);
  }

  // ── Provider Slots ──────────────────────────────────

  /**
   * Get raw slot data for a provider's schedule.
   * Lower-level than $find — useful for the scheduler view.
   */
  async getProviderSlots(scheduleId: string, startDate: string, endDate: string): Promise<FhirSlot[]> {
    const bundle = await this.fhirGet<{ entry?: { resource: FhirSlot }[] }>("Slot", {
      schedule: `Schedule/${scheduleId}`,
      start: `ge${startDate}`,
      end: `le${endDate}`,
      status: "free",
    });

    return (bundle.entry || []).map((e) => e.resource);
  }

  // ── Helpers ─────────────────────────────────────────

  /**
   * Discover the FHIR server's OAuth endpoints from its metadata.
   * Call this first if you don't already have the token/authorize URLs.
   */
  static async discoverEndpoints(fhirBaseUrl: string): Promise<{
    tokenEndpoint: string;
    authorizeEndpoint: string;
  }> {
    const response = await fetch(`${fhirBaseUrl}/metadata`, {
      headers: { Accept: "application/fhir+json" },
    });

    if (!response.ok) {
      throw new Error(`Metadata fetch failed: ${response.status}`);
    }

    const metadata = await response.json();

    // OAuth URLs are in the security extension of the rest[0] element
    const security = metadata.rest?.[0]?.security;
    const oauthExt = security?.extension?.find(
      (e: { url: string }) => e.url === "http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris"
    );

    if (!oauthExt) {
      throw new Error("Could not find OAuth endpoints in FHIR metadata");
    }

    const tokenEndpoint = oauthExt.extension.find((e: { url: string; valueUri?: string }) => e.url === "token")?.valueUri;
    const authorizeEndpoint = oauthExt.extension.find((e: { url: string; valueUri?: string }) => e.url === "authorize")?.valueUri;

    if (!tokenEndpoint || !authorizeEndpoint) {
      throw new Error("Missing token or authorize endpoint in FHIR metadata");
    }

    return { tokenEndpoint, authorizeEndpoint };
  }

  private assertAuthenticated(): void {
    if (!this.session) {
      throw new Error("Not authenticated. Call exchangeAuthCode() or authenticateBackendService() first.");
    }
    if (this.session.expiresAt < new Date()) {
      throw new Error("Session expired. Re-authenticate or refresh the token.");
    }
  }
}
