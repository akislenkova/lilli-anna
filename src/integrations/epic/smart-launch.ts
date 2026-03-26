// src/integrations/epic/smart-launch.ts
// ─────────────────────────────────────────────────────────
// SMART on FHIR launch handlers for embedding within MyChart.
//
// There are two launch modes:
//
// 1. EHR LAUNCH (provider-facing):
//    Epic passes a "launch" token when a provider opens
//    the app from within Hyperspace. We get patient context
//    automatically.
//
// 2. STANDALONE LAUNCH (patient-facing / MyChart):
//    Patient opens the app from MyChart. They authenticate
//    through MyChart's OAuth flow. We get their identity
//    from the token response.
// ─────────────────────────────────────────────────────────

import { EpicFhirClient, EpicConfig, EpicSession, DEFAULT_SCOPES } from "./epic-fhir-client";
import crypto from "crypto";

// In-memory session store (replace with Redis/DB in production)
const pendingLaunches = new Map<string, { config: EpicConfig; timestamp: number }>();
const activeSessions = new Map<string, { client: EpicFhirClient; session: EpicSession }>();

/**
 * GET /launch
 *
 * Entry point for SMART on FHIR launch. Epic redirects here
 * with `iss` (FHIR server URL) and optionally `launch` token.
 *
 * For MyChart: patient clicks "Smart Scheduling" in the MyChart menu.
 * Epic sends them here with their FHIR server URL.
 */
export async function handleLaunch(req: {
  query: { iss?: string; launch?: string };
}): Promise<{ redirect: string }> {
  const { iss, launch } = req.query;

  if (!iss) {
    throw new Error("Missing 'iss' parameter — this endpoint must be called by an Epic SMART launch.");
  }

  // Discover OAuth endpoints from the FHIR server metadata
  const endpoints = await EpicFhirClient.discoverEndpoints(iss);

  const config: EpicConfig = {
    fhirBaseUrl: iss,
    tokenEndpoint: endpoints.tokenEndpoint,
    authorizeEndpoint: endpoints.authorizeEndpoint,
    clientId: process.env.EPIC_CLIENT_ID || "your-client-id",
    redirectUri: process.env.EPIC_REDIRECT_URI || "https://your-app.com/callback",
    scopes: DEFAULT_SCOPES,
  };

  // Generate a state parameter to prevent CSRF
  const state = crypto.randomUUID();
  pendingLaunches.set(state, { config, timestamp: Date.now() });

  // Clean up old pending launches (>10 min)
  for (const [key, val] of pendingLaunches) {
    if (Date.now() - val.timestamp > 600_000) pendingLaunches.delete(key);
  }

  const client = new EpicFhirClient(config);
  const authUrl = client.getAuthorizationUrl(state, launch);

  return { redirect: authUrl };
}

/**
 * GET /callback
 *
 * OAuth2 redirect handler. Epic sends the patient/provider back
 * here after they authorize the app.
 */
export async function handleCallback(req: {
  query: { code?: string; state?: string; error?: string };
}): Promise<{
  sessionId: string;
  patientId: string | null;
  practitionerId: string | null;
}> {
  const { code, state, error } = req.query;

  if (error) {
    throw new Error(`Authorization denied: ${error}`);
  }

  if (!code || !state) {
    throw new Error("Missing code or state parameter");
  }

  const pending = pendingLaunches.get(state);
  if (!pending) {
    throw new Error("Invalid or expired state parameter");
  }
  pendingLaunches.delete(state);

  // Exchange the auth code for tokens
  const client = new EpicFhirClient(pending.config);
  const session = await client.exchangeAuthCode(code);

  // Store the session
  const sessionId = crypto.randomUUID();
  activeSessions.set(sessionId, { client, session });

  return {
    sessionId,
    patientId: session.patientFhirId,
    practitionerId: session.practitionerFhirId,
  };
}

/**
 * Retrieves an active session by ID.
 * Used by the API routes to get the authenticated Epic client.
 */
export function getSession(sessionId: string): {
  client: EpicFhirClient;
  session: EpicSession;
} | null {
  return activeSessions.get(sessionId) || null;
}
