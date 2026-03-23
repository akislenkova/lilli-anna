import http from "node:http";
import { AllocationRequest, AllocationResponse } from "../index";
import { classifyInput } from "./classifier";
import { allocateTime } from "./allocator";

const PORT = parseInt(process.env.PORT ?? "3000", 10);

const server = http.createServer(async (req, res) => {
  // CORS headers for dev
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Health check
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  // Main endpoint
  if (req.method === "POST" && req.url === "/allocate") {
    try {
      const body = await readBody(req);
      const request: AllocationRequest = JSON.parse(body);

      if (!request.patientInput || typeof request.patientInput !== "string") {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ success: false, error: "patientInput is required" }));
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

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(response, null, 2));
    } catch (err) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ success: false, error: "Invalid JSON body" }));
    }
    return;
  }

  // 404
  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
    req.on("error", reject);
  });
}

server.listen(PORT, () => {
  console.log(`Scheduling allocator running on http://localhost:${PORT}`);
  console.log(`POST /allocate — send { "patientInput": "..." }`);
  console.log(`GET  /health   — health check`);
});
