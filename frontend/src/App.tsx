import { useState, useCallback } from "react";

// ════════════════════════════════════════════════════════════
// TYPES (mirrors backend response shapes)
// ════════════════════════════════════════════════════════════

interface ClassifiedIntent {
  category: string;
  confidence: number;
  matchedKeywords: string[];
  urgency: string;
}

interface DurationComponent {
  category: string;
  baseDuration: number;
  adjustedDuration: number;
  reason: string;
}

interface SchedulingFlag {
  type: string;
  message: string;
  severity: "info" | "warning" | "critical";
}

interface AllocationResponse {
  success: boolean;
  allocation: {
    recommendedDuration: number;
    minimumDuration: number;
    breakdown: DurationComponent[];
    bufferMinutes: number;
    flags: SchedulingFlag[];
    confidence: number;
    reasoning: string;
  };
  classification: {
    rawInput: string;
    intents: ClassifiedIntent[];
    primaryIntent: ClassifiedIntent;
    hasMultipleConcerns: boolean;
    flags: SchedulingFlag[];
  };
  timestamp: string;
}

// ════════════════════════════════════════════════════════════
// CONSTANTS
// ════════════════════════════════════════════════════════════

const ICONS: Record<string, string> = {
  routine_checkup: "\u{1FA7A}", follow_up: "\u{1F504}", acute_illness: "\u{1F912}", chronic_management: "\u{1F4CA}",
  mental_health: "\u{1F9E0}", prescription_refill: "\u{1F48A}", lab_review: "\u{1F52C}", procedure_minor: "\u{1FA79}",
  procedure_major: "\u{1F3E5}", new_patient_intake: "\u{1F4CB}", urgent_care: "\u{1F6A8}", preventive_screening: "\u{1F6E1}",
  consultation: "\u{1F4AC}", unknown: "\u2753",
};

const EPIC_MAP: Record<string, { id: string; name: string; dur: number } | null> = {
  routine_checkup: { id: "1001", name: "OFFICE VISIT - ESTABLISHED", dur: 20 },
  follow_up: { id: "1002", name: "FOLLOW UP VISIT", dur: 15 },
  acute_illness: { id: "1003", name: "SICK VISIT", dur: 20 },
  chronic_management: { id: "1004", name: "CHRONIC DISEASE MGMT", dur: 30 },
  mental_health: { id: "2001", name: "BEHAVIORAL HEALTH", dur: 45 },
  prescription_refill: { id: "1005", name: "MEDICATION MGMT", dur: 10 },
  lab_review: { id: "1006", name: "RESULTS REVIEW", dur: 15 },
  procedure_minor: { id: "3001", name: "MINOR PROCEDURE", dur: 30 },
  procedure_major: { id: "3002", name: "SURGICAL CONSULT", dur: 60 },
  new_patient_intake: { id: "1007", name: "NEW PATIENT VISIT", dur: 45 },
  urgent_care: { id: "4001", name: "URGENT CARE VISIT", dur: 25 },
  preventive_screening: { id: "1008", name: "PREVENTIVE CARE", dur: 30 },
  consultation: { id: "1009", name: "CONSULTATION", dur: 30 },
  unknown: null,
};

const MOCK_CONDITIONS = ["Essential Hypertension", "Type 2 Diabetes Mellitus", "Chronic Migraine", "Generalized Anxiety Disorder"];

const MOCK_QUEUE_RAW = [
  { id: "APT-001", patient: "Maria Santos", time: "9:00 AM", input: "Annual physical and blood pressure check", isNew: false, status: "confirmed", mrn: "MRN-4821" },
  { id: "APT-002", patient: "James Chen", time: "9:30 AM", input: "Follow up on knee surgery, still having pain", isNew: false, status: "confirmed", mrn: "MRN-7293" },
  { id: "APT-003", patient: "Aisha Patel", time: "10:15 AM", input: "I've been really anxious lately and can't sleep. Also need a refill on my thyroid medication", isNew: false, status: "pending", mrn: "MRN-1056" },
  { id: "APT-004", patient: "Robert Kim", time: "11:00 AM", input: "New patient, diabetes management and cholesterol concerns", isNew: true, status: "confirmed", mrn: "MRN-8834" },
  { id: "APT-005", patient: "Sofia Reyes", time: "11:45 AM", input: "Skin check and mole removal consultation", isNew: false, status: "pending", mrn: "MRN-2147" },
  { id: "APT-006", patient: "David Okonkwo", time: "1:30 PM", input: "Bad cough for a week, fever started yesterday", isNew: false, status: "confirmed", mrn: "MRN-6510" },
];

const UPC: Record<string, { bg: string; border: string; text: string }> = {
  emergency: { bg: "#2D0A0A", border: "#7F1D1D", text: "#FCA5A5" },
  urgent: { bg: "#2D1B0A", border: "#7C4A1D", text: "#FED7AA" },
  soon: { bg: "#2D280A", border: "#7C6E1D", text: "#FEF08A" },
  routine: { bg: "#0A2D1A", border: "#1D7C4A", text: "#A7F3D0" },
};

const fmt = (c: string) => c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());

// ════════════════════════════════════════════════════════════
// PATIENT VIEW — MyChart Embedded Experience
// ════════════════════════════════════════════════════════════

function PatientView() {
  const [input, setInput] = useState("");
  const [isNew, setIsNew] = useState(false);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<AllocationResponse | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [fhirLog, setFhirLog] = useState<{ time: string; msg: string }[]>([]);

  const addLog = (msg: string) => setFhirLog(p => [...p, { time: new Date().toLocaleTimeString(), msg }]);

  const handleSubmit = useCallback(async () => {
    if (!input.trim()) return;
    setStep(1);
    setFhirLog([]);
    addLog("SMART on FHIR session active — patient context loaded");

    setTimeout(() => addLog("GET /Patient/eABC123 → 200 OK"), 300);
    setTimeout(() => addLog("GET /Condition?patient=eABC123&clinical-status=active → 4 conditions"), 600);

    try {
      const res = await fetch("/allocate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patientInput: input, isNewPatient: isNew }),
      });
      const data: AllocationResponse = await res.json();

      if (!data.success) throw new Error("Classification failed");

      const primary = data.classification.primaryIntent;
      const epicType = EPIC_MAP[primary.category];

      addLog(`AI Classification: ${fmt(primary.category)} (${Math.round(primary.confidence * 100)}%)`);
      addLog(`Time Allocation: ${data.allocation.recommendedDuration}min recommended`);
      addLog(`Epic Mapping: ${epicType ? epicType.name : "MANUAL TRIAGE"} (${epicType ? `Type ${epicType.id}` : "no match"})`);

      setResult(data);

      setTimeout(() => {
        addLog("POST /Appointment/$find → 6 available slots");
        setStep(2);
      }, 500);
    } catch {
      addLog("ERROR: Failed to classify patient input");
      setStep(0);
    }
  }, [input, isNew]);

  const handleBook = () => {
    if (!selectedSlot || !result) return;
    addLog(`POST /Appointment/$book { slot: "${selectedSlot}", comment: "[AI] ${result.allocation.recommendedDuration}min..." }`);
    addLog("→ 201 Created — Appointment booked successfully");
    addLog("POST /Communication → Sent to provider In Basket");
    setStep(3);
  };

  const slots = [
    { time: "9:30 AM", date: "Thu, Mar 13" }, { time: "10:15 AM", date: "Thu, Mar 13" },
    { time: "1:00 PM", date: "Thu, Mar 13" }, { time: "9:00 AM", date: "Fri, Mar 14" },
    { time: "11:30 AM", date: "Fri, Mar 14" }, { time: "2:00 PM", date: "Mon, Mar 17" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#F7F6F3", fontFamily: "'Outfit',sans-serif" }}>
      {/* MyChart-style header */}
      <div style={{ background: "#fff", borderBottom: "3px solid #1B6B3A", padding: "14px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#1B6B3A", color: "#fff", fontWeight: 800, fontSize: 14, padding: "8px 14px", borderRadius: 8, letterSpacing: "0.02em" }}>MyChart</div>
          <div style={{ fontSize: 14, color: "#666" }}>{"\u203A"}</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#1B6B3A" }}>Smart Scheduling</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#666" }}>
          <div style={{ width: 8, height: 8, borderRadius: 4, background: "#22C55E" }} />
          Connected to Epic FHIR
        </div>
      </div>

      <div style={{ maxWidth: 680, margin: "0 auto", padding: "28px 24px 60px" }}>
        {step === 0 && (
          <div style={{ animation: "fadeIn 0.4s ease" }}>
            <h2 style={{ fontFamily: "'Source Serif 4',Georgia,serif", fontSize: 24, fontWeight: 600, color: "#1a1a1a", marginBottom: 8 }}>Schedule an Appointment</h2>
            <p style={{ fontSize: 15, color: "#666", lineHeight: 1.6, marginBottom: 28 }}>Tell us what's going on and we'll find the right time for your visit. Your medical history helps us recommend the best appointment length.</p>

            <div style={{ background: "#E8F5ED", border: "1px solid #B8E0C5", borderRadius: 10, padding: "12px 16px", marginBottom: 24, fontSize: 13, color: "#1B6B3A", display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 16 }}>{"\u{1F512}"}</span>
              Your data stays in Epic. Our AI analyzes your input locally and queries your chart securely via FHIR.
            </div>

            <label style={{ display: "block", fontSize: 14, fontWeight: 600, color: "#333", marginBottom: 8 }}>What brings you in today?</label>
            <textarea value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit(); }}
              placeholder="Describe what's going on — for example: 'I've been having headaches and need to renew my blood pressure medication'"
              rows={4} style={{ width: "100%", background: "#fff", border: "2px solid #D9D5CC", borderRadius: 12, padding: "14px 16px", fontSize: 15, fontFamily: "'Source Serif 4',Georgia,serif", color: "#1a1a1a", resize: "none", lineHeight: 1.6, boxSizing: "border-box" }} />

            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14, marginBottom: 24 }}>
              {["Annual checkup", "I'm feeling sick", "Prescription refill", "Follow-up visit", "Discuss anxiety/mood", "Lab results review"].map(c => (
                <button key={c} onClick={() => setInput(c)} style={{ padding: "7px 14px", borderRadius: 20, border: input === c ? "2px solid #1B6B3A" : "2px solid #E0DCD4", background: input === c ? "#E8F5ED" : "#fff", color: input === c ? "#1B6B3A" : "#666", fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}>{c}</button>
              ))}
            </div>

            <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28, cursor: "pointer", fontSize: 14, color: "#555" }}>
              <div onClick={() => setIsNew(!isNew)} style={{ width: 20, height: 20, borderRadius: 5, border: isNew ? "none" : "2px solid #BBB", background: isNew ? "#1B6B3A" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                {isNew && <span style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>{"\u2713"}</span>}
              </div>
              I'm a new patient
            </label>

            <button onClick={handleSubmit} disabled={!input.trim()} style={{ width: "100%", padding: "15px", borderRadius: 12, border: "none", fontSize: 16, fontWeight: 700, cursor: input.trim() ? "pointer" : "default", background: input.trim() ? "#1B6B3A" : "#D9D5CC", color: input.trim() ? "#fff" : "#999", boxShadow: input.trim() ? "0 4px 16px rgba(27,107,58,0.25)" : "none", fontFamily: "inherit" }}>
              Find Available Times
            </button>
          </div>
        )}

        {step === 1 && (
          <div style={{ animation: "fadeIn 0.3s ease", textAlign: "center", padding: "60px 20px" }}>
            <div style={{ width: 48, height: 48, borderRadius: "50%", border: "3px solid #D9D5CC", borderTopColor: "#1B6B3A", margin: "0 auto 20px", animation: "spin 1s linear infinite" }} />
            <div style={{ fontFamily: "'Source Serif 4',Georgia,serif", fontSize: 18, color: "#555", marginBottom: 20 }}>Analyzing your needs & checking availability...</div>
            <FhirLog entries={fhirLog} />
          </div>
        )}

        {step === 2 && result && (
          <div style={{ animation: "fadeIn 0.5s ease" }}>
            {/* What we found */}
            <div style={{ background: "#fff", border: "1px solid #E0DCD4", borderRadius: 14, padding: 24, marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.06em", color: "#888", marginBottom: 12 }}>Your visit plan</div>
              <div style={{ display: "flex", flexDirection: "column" as const, gap: 10 }}>
                {result.classification.intents.slice(0, 3).map((intent, idx) => (
                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 20 }}>{ICONS[intent.category]}</span>
                    <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 600 }}>{fmt(intent.category)}</div></div>
                    <div style={{ fontSize: 12, color: "#888", fontFamily: "'JetBrains Mono',monospace" }}>{result.allocation.breakdown[idx]?.adjustedDuration || 0}min</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 14, padding: "12px 16px", background: "#F0FAF3", borderRadius: 10, display: "flex", alignItems: "center", gap: 10, fontSize: 14 }}>
                <span style={{ fontSize: 18 }}>{"\u23F1"}</span>
                <span>We've allocated <strong style={{ color: "#1B6B3A" }}>{result.allocation.recommendedDuration} minutes</strong> for your visit</span>
              </div>
              {(() => { const et = EPIC_MAP[result.classification.primaryIntent.category]; return et ? (
                <div style={{ marginTop: 10, padding: "10px 16px", background: "#F5F3EE", borderRadius: 10, fontSize: 12, color: "#777", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", background: "#E8E5DE", padding: "2px 8px", borderRadius: 4, fontWeight: 600, fontSize: 11 }}>EPIC</span>
                  Visit type: {et.name}
                  {result.allocation.recommendedDuration !== et.dur && (
                    <span style={{ color: "#B45309", fontWeight: 600 }}> (extended from {et.dur}min default)</span>
                  )}
                </div>
              ) : null; })()}
            </div>

            {/* Conditions from chart */}
            <div style={{ background: "#fff", border: "1px solid #E0DCD4", borderRadius: 14, padding: 20, marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.06em", color: "#888", marginBottom: 10 }}>From your medical record</div>
              <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 6 }}>
                {MOCK_CONDITIONS.map((c, i) => (
                  <span key={i} style={{ padding: "5px 12px", borderRadius: 6, background: "#F5F3EE", fontSize: 12, fontWeight: 500, color: "#555", border: "1px solid #E8E5DE" }}>{c}</span>
                ))}
              </div>
              <div style={{ fontSize: 12, color: "#999", marginTop: 8 }}>Your provider will see these conditions noted alongside your visit reason.</div>
            </div>

            {/* Available slots */}
            <div style={{ background: "#fff", border: "1px solid #E0DCD4", borderRadius: 14, padding: 24, marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.06em", color: "#888", marginBottom: 14 }}>Available times</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {slots.map((s, i) => {
                  const key = s.time + " " + s.date;
                  return (
                    <button key={i} onClick={() => setSelectedSlot(key)} style={{
                      padding: "14px", borderRadius: 10, border: selectedSlot === key ? "2px solid #1B6B3A" : "2px solid #E8E5DE",
                      background: selectedSlot === key ? "#E8F5ED" : "#fff", cursor: "pointer", textAlign: "left" as const, fontFamily: "inherit",
                    }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#1a1a1a" }}>{s.time}</div>
                      <div style={{ fontSize: 12, color: "#888" }}>{s.date}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <button onClick={handleBook} disabled={!selectedSlot} style={{ width: "100%", padding: "15px", borderRadius: 12, border: "none", fontSize: 16, fontWeight: 700, cursor: selectedSlot ? "pointer" : "default", background: selectedSlot ? "#1B6B3A" : "#D9D5CC", color: selectedSlot ? "#fff" : "#999", fontFamily: "inherit" }}>
              Confirm Appointment
            </button>

            <FhirLog entries={fhirLog} style={{ marginTop: 16 }} />
          </div>
        )}

        {step === 3 && result && (
          <div style={{ animation: "fadeIn 0.5s ease", textAlign: "center", padding: "60px 20px" }}>
            <div style={{ width: 64, height: 64, borderRadius: "50%", background: "#E8F5ED", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32, margin: "0 auto 20px" }}>{"\u2713"}</div>
            <h2 style={{ fontFamily: "'Source Serif 4',Georgia,serif", fontSize: 24, fontWeight: 600, marginBottom: 8 }}>You're booked!</h2>
            <p style={{ fontSize: 15, color: "#666", marginBottom: 24 }}>Your {result.allocation.recommendedDuration}-minute appointment has been scheduled. Your provider has been notified with a summary of your concerns.</p>
            <div style={{ background: "#fff", border: "1px solid #E0DCD4", borderRadius: 14, padding: 20, textAlign: "left" as const, maxWidth: 360, margin: "0 auto 24px" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#1B6B3A", marginBottom: 4 }}>{selectedSlot}</div>
              <div style={{ fontSize: 14, color: "#555" }}>Dr. Sarah Thompson</div>
              <div style={{ fontSize: 13, color: "#888" }}>Greenwood Family Medicine</div>
              <div style={{ fontSize: 12, color: "#999", marginTop: 8 }}>{result.allocation.recommendedDuration} min {"\u00B7"} {EPIC_MAP[result.classification.primaryIntent.category]?.name || "Office Visit"}</div>
            </div>
            <FhirLog entries={fhirLog} />
            <button onClick={() => { setStep(0); setResult(null); setSelectedSlot(null); setFhirLog([]); setInput(""); }} style={{ marginTop: 20, padding: "10px 24px", borderRadius: 10, border: "2px solid #E0DCD4", background: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", color: "#555" }}>
              Schedule another visit
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// SCHEDULER VIEW
// ════════════════════════════════════════════════════════════

interface QueueItem {
  id: string; patient: string; time: string; input: string; isNew: boolean;
  status: string; mrn: string; allocation: AllocationResponse["allocation"];
  classification: AllocationResponse["classification"];
  epicType: { id: string; name: string; dur: number } | null;
}

function SchedulerView({ queue }: { queue: QueueItem[] }) {
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const queueWithFinal = queue.map(a => ({ ...a, finalDuration: overrides[a.id] ?? a.allocation.recommendedDuration }));
  const totalMin = queueWithFinal.reduce((s, a) => s + a.finalDuration, 0);

  return (
    <div style={{ minHeight: "100vh", background: "#0A0E14", color: "#C8CDD5", fontFamily: "'Outfit',sans-serif" }}>
      <div style={{ background: "#0F1319", borderBottom: "1px solid #1C222D", padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: 7, background: "linear-gradient(135deg,#2563EB,#1D4ED8)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>{"\u{1F4C5}"}</div>
          <span style={{ fontWeight: 700, fontSize: 14, color: "#E8ECF0" }}>Schedule Manager</span>
          <span style={{ fontSize: 12, color: "#4B5563", marginLeft: 4 }}>Dr. Thompson {"\u00B7"} Wed, Mar 12</span>
        </div>
        <div style={{ display: "flex", gap: 12, fontSize: 11, fontWeight: 600 }}>
          <div style={{ padding: "5px 10px", borderRadius: 5, background: "#111827", border: "1px solid #1C222D" }}><span style={{ color: "#6B7280" }}>Patients </span><span style={{ color: "#60A5FA" }}>{queue.length}</span></div>
          <div style={{ padding: "5px 10px", borderRadius: 5, background: "#111827", border: "1px solid #1C222D" }}><span style={{ color: "#6B7280" }}>Total </span><span style={{ color: "#60A5FA" }}>{Math.floor(totalMin / 60)}h {totalMin % 60}m</span></div>
          <div style={{ padding: "5px 10px", borderRadius: 5, background: "#0D1F14", border: "1px solid #166534" }}><span style={{ color: "#6EE7A0" }}>Epic FHIR {"\u2713"}</span></div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 400px" : "1fr" }}>
        <div style={{ padding: "12px 16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "70px 120px 1fr 80px 80px 70px 80px", gap: 6, padding: "6px 14px", fontSize: 10, fontWeight: 700, color: "#4B5563", textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 2 }}>
            <div>Time</div><div>Patient</div><div>Reason</div><div>Epic Type</div><div>AI Alloc</div><div>Final</div><div>Status</div>
          </div>
          {queueWithFinal.map((apt, idx) => {
            const isSel = selected?.id === apt.id;
            const urg = apt.classification.primaryIntent.urgency;
            return (
              <div key={apt.id} onClick={() => setSelected(isSel ? null : apt)}
                style={{ display: "grid", gridTemplateColumns: "70px 120px 1fr 80px 80px 70px 80px", gap: 6, padding: "12px 14px", marginBottom: 1, borderRadius: 6, cursor: "pointer", background: isSel ? "#131A24" : idx % 2 === 0 ? "#0D1117" : "transparent", border: isSel ? "1px solid #1E3A5F" : "1px solid transparent", alignItems: "center", animation: `fadeIn 0.3s ease ${idx * 0.04}s both` }}>
                <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: "#9CA3AF" }}>{apt.time}</div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#E8ECF0" }}>{apt.patient}</div>
                  <div style={{ fontSize: 10, color: "#4B5563", fontFamily: "'JetBrains Mono',monospace" }}>{apt.mrn}</div>
                </div>
                <div style={{ fontSize: 12, color: "#6B7280", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>{apt.input}</div>
                <div style={{ fontSize: 10, fontFamily: "'JetBrains Mono',monospace", color: "#9CA3AF", background: "#111827", padding: "3px 6px", borderRadius: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>{apt.epicType?.name?.split(" ")[0] || "MANUAL"}</div>
                <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 600, color: "#60A5FA" }}>{apt.allocation.recommendedDuration}m</div>
                <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: apt.finalDuration !== apt.allocation.recommendedDuration ? "#F59E0B" : "#E8ECF0" }}>{apt.finalDuration}m</div>
                <span style={{ padding: "2px 8px", borderRadius: 3, fontSize: 10, fontWeight: 600, background: urg !== "routine" ? UPC[urg]?.bg : apt.status === "confirmed" ? "#071F0E" : "#1A1606", color: urg !== "routine" ? UPC[urg]?.text : apt.status === "confirmed" ? "#6EE7A0" : "#FDE68A", border: `1px solid ${urg !== "routine" ? UPC[urg]?.border : apt.status === "confirmed" ? "#166534" : "#854D0E"}` }}>
                  {urg !== "routine" ? `\u26A1${urg}` : apt.status}
                </span>
              </div>
            );
          })}
        </div>

        {selected && (
          <div style={{ borderLeft: "1px solid #1C222D", background: "#0D1117", padding: 20, animation: "fadeIn 0.25s ease", overflowY: "auto" as const }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#E8ECF0" }}>{selected.patient}</div>
                <div style={{ fontSize: 12, color: "#6B7280" }}>{selected.mrn} {"\u00B7"} {selected.time}</div>
              </div>
              <button onClick={() => setSelected(null)} style={{ background: "none", border: "none", color: "#6B7280", fontSize: 18, cursor: "pointer" }}>{"\u2715"}</button>
            </div>

            <div style={{ fontSize: 10, fontWeight: 700, color: "#4B5563", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>Patient's Words</div>
            <div style={{ background: "#0A0E14", border: "1px solid #1C222D", borderRadius: 8, padding: 12, fontSize: 13, fontStyle: "italic", color: "#9CA3AF", lineHeight: 1.5, marginBottom: 16 }}>"{selected.input}"</div>

            <div style={{ fontSize: 10, fontWeight: 700, color: "#4B5563", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>Epic FHIR Mapping</div>
            <div style={{ background: "#0A0E14", border: "1px solid #1C222D", borderRadius: 8, padding: 12, marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span style={{ color: "#9CA3AF" }}>Visit Type</span>
                <span style={{ color: "#60A5FA", fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{selected.epicType?.name || "NEEDS MANUAL SELECTION"}</span>
              </div>
              {selected.epicType && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginTop: 6 }}>
                  <span style={{ color: "#6B7280" }}>Epic Default / AI Recommended</span>
                  <span style={{ color: selected.allocation.recommendedDuration !== selected.epicType.dur ? "#F59E0B" : "#6EE7A0", fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>
                    {selected.epicType.dur}m / {selected.allocation.recommendedDuration}m
                  </span>
                </div>
              )}
            </div>

            <div style={{ fontSize: 10, fontWeight: 700, color: "#4B5563", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>AI Breakdown</div>
            <div style={{ display: "flex", flexDirection: "column" as const, gap: 6, marginBottom: 16 }}>
              {selected.allocation.breakdown.map((c, i) => (
                <div key={i} style={{ background: "#0A0E14", border: "1px solid #1C222D", borderRadius: 6, padding: "8px 12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span style={{ color: "#E8ECF0" }}>{ICONS[c.category]} {fmt(c.category)}</span>
                    <span style={{ color: "#60A5FA", fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{c.adjustedDuration}m</span>
                  </div>
                  <div style={{ height: 3, background: "#1C222D", borderRadius: 2, marginTop: 4, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 2, width: `${(c.adjustedDuration / selected.allocation.recommendedDuration) * 100}%`, background: i === 0 ? "#3B82F6" : i === 1 ? "#8B5CF6" : "#6B7280" }} />
                  </div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 10, fontWeight: 700, color: "#4B5563", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>Override Duration</div>
            <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" as const }}>
              {[selected.allocation.recommendedDuration - 10, selected.allocation.recommendedDuration - 5, selected.allocation.recommendedDuration, selected.allocation.recommendedDuration + 5, selected.allocation.recommendedDuration + 10, selected.allocation.recommendedDuration + 15].filter(d => d > 0).map(d => (
                <button key={d} onClick={() => setOverrides(p => ({ ...p, [selected.id]: d }))} style={{ padding: "6px 10px", borderRadius: 5, fontSize: 12, fontWeight: 600, fontFamily: "'JetBrains Mono',monospace", cursor: "pointer", border: (overrides[selected.id] ?? selected.allocation.recommendedDuration) === d ? "2px solid #3B82F6" : "1px solid #1C222D", background: (overrides[selected.id] ?? selected.allocation.recommendedDuration) === d ? "#0D2847" : "#0A0E14", color: (overrides[selected.id] ?? selected.allocation.recommendedDuration) === d ? "#60A5FA" : "#6B7280" }}>{d}m</button>
              ))}
            </div>

            <button style={{ width: "100%", padding: "10px", borderRadius: 8, border: "none", background: "#2563EB", color: "#fff", fontWeight: 700, fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}>Confirm in Epic</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// PHYSICIAN VIEW
// ════════════════════════════════════════════════════════════

function PhysicianView({ queue }: { queue: QueueItem[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const next = queue[0];

  if (!next) return null;

  return (
    <div style={{ minHeight: "100vh", background: "#FCFCFA", color: "#1A1A1A", fontFamily: "'Outfit',sans-serif" }}>
      <div style={{ background: "#fff", borderBottom: "2px solid #E8E5E0", padding: "14px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: "#1A1A1A", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: "#fff", fontWeight: 700 }}>Dr</div>
          <div>
            <div style={{ fontFamily: "'Source Serif 4',Georgia,serif", fontSize: 17, fontWeight: 600 }}>Dr. Sarah Thompson</div>
            <div style={{ fontSize: 11, color: "#888" }}>Wed, Mar 12 {"\u00B7"} {queue.length} patients {"\u00B7"} Epic Hyperspace</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, padding: "4px 10px", borderRadius: 5, background: "#E8F5ED", color: "#1B6B3A", fontWeight: 600, border: "1px solid #B8E0C5" }}>FHIR Sync {"\u2713"}</span>
          <span style={{ fontSize: 11, padding: "4px 10px", borderRadius: 5, background: "#FEF3C7", color: "#92400E", fontWeight: 600, border: "1px solid #FDE68A" }}>AI Assist ON</span>
        </div>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 24px 60px" }}>
        {/* Next patient card */}
        <div style={{ background: "#fff", border: "2px solid #1A1A1A", borderRadius: 14, padding: 24, marginBottom: 24, boxShadow: "0 2px 16px rgba(0,0,0,0.05)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 4 }}>Next Patient</div>
              <div style={{ fontFamily: "'Source Serif 4',Georgia,serif", fontSize: 24, fontWeight: 600 }}>{next.patient}</div>
              <div style={{ fontSize: 13, color: "#888" }}>{next.time} {"\u00B7"} {next.mrn}</div>
            </div>
            <div style={{ textAlign: "right" as const }}>
              <div style={{ fontSize: 36, fontWeight: 800, fontFamily: "'JetBrains Mono',monospace", lineHeight: 1 }}>{next.allocation.recommendedDuration}</div>
              <div style={{ fontSize: 11, color: "#888", fontWeight: 600 }}>MINUTES (AI)</div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>Chief Complaint</div>
              <div style={{ fontSize: 14, lineHeight: 1.5, color: "#444", fontFamily: "'Source Serif 4',Georgia,serif", fontStyle: "italic" }}>"{next.input}"</div>
              <div style={{ marginTop: 10, fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>Epic Visit Type</div>
              <div style={{ fontSize: 13, padding: "6px 12px", background: "#F5F3EE", borderRadius: 6, display: "inline-block", fontFamily: "'JetBrains Mono',monospace", fontWeight: 500 }}>{next.epicType?.name || "UNASSIGNED"}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>AI Assessment</div>
              {next.allocation.breakdown.map((c, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid #F0EDE8" }}>
                  <span style={{ fontSize: 13 }}>{ICONS[c.category]} {fmt(c.category)}</span>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600 }}>{c.adjustedDuration}m</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Schedule */}
        <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 10 }}>Full Schedule</div>
        <div style={{ display: "flex", flexDirection: "column" as const, gap: 2 }}>
          {queue.map((apt, idx) => {
            const isExp = expanded === apt.id;
            return (
              <div key={apt.id}>
                <div onClick={() => setExpanded(isExp ? null : apt.id)} style={{
                  display: "grid", gridTemplateColumns: "60px 1fr 100px 60px 40px", alignItems: "center", gap: 10, padding: "12px 16px",
                  borderRadius: isExp ? "10px 10px 0 0" : 10, background: idx === 0 ? "#F8F7F4" : "#fff", cursor: "pointer",
                  border: `1px solid ${isExp ? "#D0CCC5" : "#EDEBE8"}`, borderBottom: isExp ? "none" : undefined,
                }}>
                  <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: "#888" }}>{apt.time}</div>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{apt.patient}</span>
                    {apt.isNew && <span style={{ fontSize: 9, fontWeight: 700, marginLeft: 6, color: "#2563EB", background: "#DBEAFE", padding: "1px 5px", borderRadius: 3 }}>NEW</span>}
                    <div style={{ fontSize: 11, color: "#999", marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>{apt.input}</div>
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    {apt.classification.intents.slice(0, 2).map((intent, j) => (
                      <span key={j} style={{ fontSize: 10, padding: "2px 6px", borderRadius: 3, background: "#F3F1ED", color: "#666" }}>{ICONS[intent.category]}</span>
                    ))}
                  </div>
                  <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 15, fontWeight: 700, textAlign: "center" as const }}>{apt.allocation.recommendedDuration}m</div>
                  <div style={{ textAlign: "right" as const, fontSize: 13, color: "#888" }}>{isExp ? "\u25B2" : "\u25BC"}</div>
                </div>
                {isExp && (
                  <div style={{ border: "1px solid #D0CCC5", borderTop: "1px dashed #D0CCC5", borderRadius: "0 0 10px 10px", padding: 18, background: "#FAFAF8", animation: "fadeIn 0.2s ease" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                      <div>
                        <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, marginBottom: 6 }}>FHIR Details</div>
                        <div style={{ fontSize: 12, color: "#666", lineHeight: 1.8 }}>
                          <div><strong>Epic Type:</strong> {apt.epicType?.name || "Unassigned"}</div>
                          <div><strong>Type ID:</strong> {apt.epicType?.id || "N/A"}</div>
                          <div><strong>Epic Default:</strong> {apt.epicType?.dur || "N/A"}min</div>
                          <div><strong>AI Recommended:</strong> {apt.allocation.recommendedDuration}min</div>
                          {apt.allocation.recommendedDuration !== (apt.epicType?.dur) && <div style={{ color: "#B45309", fontWeight: 600 }}>{"\u26A0"} Duration mismatch — extended slot</div>}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase" as const, marginBottom: 6 }}>Pre-Visit Notes</div>
                        <textarea value={notes[apt.id] || ""} onChange={e => setNotes(p => ({ ...p, [apt.id]: e.target.value }))}
                          placeholder="Add notes..." rows={3}
                          style={{ width: "100%", background: "#fff", border: "1px solid #EDEBE8", borderRadius: 6, padding: "8px 10px", fontSize: 12, fontFamily: "'Source Serif 4',Georgia,serif", color: "#333", resize: "none", boxSizing: "border-box" }} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// FHIR LOG COMPONENT (shows API calls in real-time)
// ════════════════════════════════════════════════════════════

function FhirLog({ entries, style = {} }: { entries: { time: string; msg: string }[]; style?: React.CSSProperties }) {
  if (!entries.length) return null;
  return (
    <div style={{ background: "#0F1319", borderRadius: 10, padding: 14, maxHeight: 180, overflowY: "auto" as const, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, ...style }}>
      <div style={{ fontSize: 9, fontWeight: 700, color: "#4B5563", textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 6 }}>FHIR API Log</div>
      {entries.map((e, i) => (
        <div key={i} style={{ color: e.msg.includes("\u2192") ? "#60A5FA" : e.msg.includes("201") ? "#6EE7A0" : "#9CA3AF", padding: "2px 0", animation: `fadeIn 0.3s ease ${i * 0.05}s both` }}>
          <span style={{ color: "#4B5563" }}>{e.time}</span> {e.msg}
        </div>
      ))}
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// MAIN APP
// ════════════════════════════════════════════════════════════

const VIEWS = [
  { id: "patient", label: "Patient Portal", icon: "\u{1F464}", desc: "MyChart experience" },
  { id: "scheduler", label: "Scheduler", icon: "\u{1F4C5}", desc: "Epic Cadence" },
  { id: "physician", label: "Physician", icon: "\u{1FA7A}", desc: "Hyperspace view" },
];

export default function App() {
  const [view, setView] = useState("patient");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [queueLoaded, setQueueLoaded] = useState(false);

  // Load the mock queue by calling the backend for each patient
  const loadQueue = useCallback(async () => {
    if (queueLoaded) return;
    setQueueLoaded(true);

    const items: QueueItem[] = [];
    for (const raw of MOCK_QUEUE_RAW) {
      try {
        const res = await fetch("/allocate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ patientInput: raw.input, isNewPatient: raw.isNew }),
        });
        const data: AllocationResponse = await res.json();
        items.push({
          ...raw,
          allocation: data.allocation,
          classification: data.classification,
          epicType: EPIC_MAP[data.classification.primaryIntent.category],
        });
      } catch {
        // Skip on error
      }
    }
    setQueue(items);
  }, [queueLoaded]);

  // Load queue when switching to scheduler or physician view
  if ((view === "scheduler" || view === "physician") && !queueLoaded) {
    loadQueue();
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" as const }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600&family=JetBrains+Mono:wght@400;500&display=swap');*{box-sizing:border-box;margin:0;padding:0;}@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}@keyframes spin{to{transform:rotate(360deg)}}textarea:focus{outline:none;}`}</style>
      <div style={{ background: "#fff", borderBottom: "2px solid #E5E5E5", padding: "0 16px", display: "flex", justifyContent: "center", gap: 0, position: "sticky" as const, top: 0, zIndex: 100, fontFamily: "'Outfit',sans-serif" }}>
        {VIEWS.map(v => (
          <button key={v.id} onClick={() => setView(v.id)} style={{ padding: "12px 24px", border: "none", background: "none", cursor: "pointer", borderBottom: view === v.id ? "3px solid #1A1A1A" : "3px solid transparent", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 15 }}>{v.icon}</span>
            <span style={{ fontWeight: view === v.id ? 700 : 500, fontSize: 13, color: view === v.id ? "#1A1A1A" : "#888" }}>{v.label}</span>
            <span style={{ fontSize: 10, color: "#BBB" }}>{v.desc}</span>
          </button>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {view === "patient" && <PatientView />}
        {view === "scheduler" && <SchedulerView queue={queue} />}
        {view === "physician" && <PhysicianView queue={queue} />}
      </div>
    </div>
  );
}
