import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { AllocationRequest, AllocationResponse } from "../index";
import { classifyInput } from "./classifier";
import { allocateTime } from "./allocator";
import {
  getDb,
  createSession,
  updateSession,
  getSession as getDbSession,
  getAllSessions,
} from "./database";
import {
  extractEntities,
  generateFollowUpFlow,
  processFollowUpAnswers,
  FollowUpAnswer,
} from "./nlp-engine";

const PORT = parseInt(process.env.PORT ?? "3000", 10);

const server = http.createServer(async (req, res) => {
  // CORS headers for dev
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url || "/", `http://localhost:${PORT}`);
  const pathname = url.pathname;

  try {
    // ── Serve frontend ─────────────────────────────────
    if (req.method === "GET" && (pathname === "/" || pathname === "/index.html")) {
      let htmlPath = path.join(__dirname, "public", "index.html");
      if (!fs.existsSync(htmlPath)) {
        htmlPath = path.join(__dirname, "..", "src", "public", "index.html");
      }
      const html = fs.readFileSync(htmlPath, "utf-8");
      res.writeHead(200, { "Content-Type": "text/html" });
      res.end(html);
      return;
    }

    // ── Health check ───────────────────────────────────
    if (req.method === "GET" && pathname === "/health") {
      json(res, 200, { status: "ok", database: "connected" });
      return;
    }

    // ══════════════════════════════════════════════════════
    // API ENDPOINTS
    // ══════════════════════════════════════════════════════

    // ── POST /api/intake ───────────────────────────────
    // Patient submits initial input. Creates a session,
    // classifies, extracts entities, generates follow-up questions.
    if (req.method === "POST" && pathname === "/api/intake") {
      const body = JSON.parse(await readBody(req));
      const { patientInput, isNewPatient, patientName, mrn } = body;

      if (!patientInput || typeof patientInput !== "string") {
        json(res, 400, { error: "patientInput is required" });
        return;
      }

      // Create session
      const sessionId = crypto.randomUUID();
      createSession({
        id: sessionId,
        initial_input: patientInput,
        patient_name: patientName,
        mrn,
        is_new_patient: isNewPatient,
      });

      // Classify
      const classification = classifyInput(patientInput);
      const allocation = allocateTime(classification, { patientInput, isNewPatient });

      // Extract NLP entities
      const entities = extractEntities(patientInput);

      // Generate follow-up questions
      const followUp = generateFollowUpFlow(patientInput, classification, sessionId);

      // Update session
      updateSession(sessionId, {
        classification_json: classification,
        allocation_json: allocation,
        status: followUp.questions.length > 0 ? "follow_up" : "classified",
        urgency_level: classification.primaryIntent.urgency,
      });

      json(res, 200, {
        sessionId,
        classification,
        allocation,
        entities,
        followUp: {
          questions: followUp.questions,
          reasoning: followUp.reasoning,
          hasQuestions: followUp.questions.length > 0,
        },
      });
      return;
    }

    // ── POST /api/sessions/:id/follow-up ───────────────
    // Patient submits follow-up answers. Refines classification
    // and allocation based on answers.
    if (req.method === "POST" && pathname.match(/^\/api\/sessions\/[^/]+\/follow-up$/)) {
      const sessionId = pathname.split("/")[3];
      const body = JSON.parse(await readBody(req));
      const { answers } = body as { answers: FollowUpAnswer[] };

      const session = getDbSession(sessionId);
      if (!session) {
        json(res, 404, { error: "Session not found" });
        return;
      }

      // Get the original follow-up flow to have the questions
      const originalClassification = session.classification_json;
      const followUp = generateFollowUpFlow(
        session.initial_input,
        originalClassification,
        sessionId
      );

      // Process answers and refine
      const refined = processFollowUpAnswers(
        session.initial_input,
        originalClassification,
        answers,
        followUp.questions,
        session.is_new_patient
      );

      // Update session
      updateSession(sessionId, {
        follow_up_answers_json: answers,
        refined_classification_json: refined.classification,
        refined_allocation_json: refined.allocation,
        status: "classified",
        urgency_level: refined.classification.primaryIntent.urgency,
      });

      json(res, 200, {
        sessionId,
        classification: refined.classification,
        allocation: refined.allocation,
        adjustments: refined.adjustments,
        originalDuration: session.allocation_json?.recommendedDuration,
        refinedDuration: refined.allocation.recommendedDuration,
      });
      return;
    }

    // ── GET /api/sessions ──────────────────────────────
    // List all sessions (for scheduler and physician views).
    if (req.method === "GET" && pathname === "/api/sessions") {
      const status = url.searchParams.get("status") || undefined;
      const sessions = getAllSessions(status);
      json(res, 200, { sessions });
      return;
    }

    // ── GET /api/sessions/:id ──────────────────────────
    // Get a specific session.
    if (req.method === "GET" && pathname.match(/^\/api\/sessions\/[^/]+$/)) {
      const sessionId = pathname.split("/")[3];
      const session = getDbSession(sessionId);
      if (!session) {
        json(res, 404, { error: "Session not found" });
        return;
      }
      json(res, 200, { session });
      return;
    }

    // ── PATCH /api/sessions/:id ────────────────────────
    // Update a session (scheduler overrides, physician notes, booking).
    if (req.method === "PATCH" && pathname.match(/^\/api\/sessions\/[^/]+$/)) {
      const sessionId = pathname.split("/")[3];
      const body = JSON.parse(await readBody(req));
      const session = getDbSession(sessionId);
      if (!session) {
        json(res, 404, { error: "Session not found" });
        return;
      }

      const allowed = [
        "status", "selected_slot", "booked_appointment_id",
        "physician_notes", "scheduler_override_minutes", "urgency_level",
      ];
      const updates: Record<string, any> = {};
      for (const key of allowed) {
        if (body[key] !== undefined) updates[key] = body[key];
      }

      updateSession(sessionId, updates);
      const updated = getDbSession(sessionId);
      json(res, 200, { session: updated });
      return;
    }

    // ── POST /allocate ─────────────────────────────────
    // Legacy endpoint (kept for backward compatibility).
    if (req.method === "POST" && pathname === "/allocate") {
      const body = await readBody(req);
      const request: AllocationRequest = JSON.parse(body);

      if (!request.patientInput || typeof request.patientInput !== "string") {
        json(res, 400, { error: "patientInput is required" });
        return;
      }

      const classification = classifyInput(request.patientInput);
      const allocation = allocateTime(classification, request);

      const response: AllocationResponse = {
        success: true,
        allocation,
        classification,
        timestamp: new Date().toISOString(),
      };

      json(res, 200, response);
      return;
    }

    // ── 404 ────────────────────────────────────────────
    json(res, 404, { error: "Not found" });
  } catch (err: any) {
    console.error("Server error:", err);
    json(res, 500, { error: err.message || "Internal server error" });
  }
});

function json(res: http.ServerResponse, status: number, data: any): void {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data, null, 2));
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
    req.on("error", reject);
  });
}

// Initialize DB on startup
getDb();

server.listen(PORT, () => {
  console.log(`\n🏥 Smart Scheduling System running on http://localhost:${PORT}`);
  console.log(`\n  Endpoints:`);
  console.log(`  GET  /              — Frontend UI`);
  console.log(`  GET  /health        — Health check`);
  console.log(`  POST /api/intake    — Patient intake (classify + follow-up questions)`);
  console.log(`  POST /api/sessions/:id/follow-up  — Submit follow-up answers`);
  console.log(`  GET  /api/sessions  — List all sessions (scheduler/physician)`);
  console.log(`  GET  /api/sessions/:id  — Get session details`);
  console.log(`  PATCH /api/sessions/:id — Update session (notes, override, book)`);
  console.log(`  POST /allocate      — Legacy allocation endpoint\n`);
});
