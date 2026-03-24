// src/integrations/epic/index.ts
// ─────────────────────────────────────────────────────────
// Epic / MyChart integration public API.
// ─────────────────────────────────────────────────────────

// FHIR client
export {
  EpicFhirClient,
  EpicConfig,
  EpicSession,
  DEFAULT_SCOPES,
} from "./epic-fhir-client";

// SMART on FHIR launch flow
export {
  handleLaunch,
  handleCallback,
  getSession,
} from "./smart-launch";

// Scheduling orchestration
export {
  getSchedulingRecommendation,
  bookWithRecommendation,
  SchedulingContext,
  SchedulingRecommendation,
} from "./scheduling-orchestrator";

// Visit type mapping
export {
  resolveVisitType,
  EpicVisitType,
  VisitTypeMapping,
  EXAMPLE_VISIT_TYPE_MAP,
} from "./visit-type-mapping";
