import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getMyProfile,
  getMyRecords,
  getMyMedications,
} from "../services/patients";
import {
  getEpicStatus,
  startEpicAuth,
  getEpicRecords,
  disconnectEpic,
  type EpicRecordsResponse,
  type EpicStatus,
} from "../services/epic";
import type { PatientProfile } from "../services/patients";
import type { Appointment } from "../types";

// ── Small shared components ────────────────────────────────────────────────

function SectionCard({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function EpicBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700 ring-1 ring-inset ring-red-100">
      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
      {label}
    </span>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="text-sm text-gray-400 italic">{text}</p>;
}

// ── Epic connect panel ─────────────────────────────────────────────────────

function EpicConnectPanel({
  epicStatus,
  epicRecords,
  onConnect,
  onDisconnect,
  connecting,
}: {
  epicStatus: EpicStatus | null;
  epicRecords: EpicRecordsResponse | null;
  onConnect: () => void;
  onDisconnect: () => void;
  connecting: boolean;
}) {
  if (!epicStatus) return null;

  const isConnected = epicStatus.available && epicStatus.connected && epicRecords?.connected;
  const hasError = epicRecords?.error;

  return (
    <section
      className={`flex items-start justify-between gap-4 rounded-xl border p-5 ${
        isConnected
          ? "border-red-100 bg-red-50"
          : epicStatus.available
          ? "border-gray-200 bg-gray-50"
          : "border-gray-100 bg-gray-50"
      }`}
    >
      <div className="flex items-start gap-4">
        {/* Epic "E" logo placeholder */}
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-white shadow-sm">
          <svg className="h-5 w-5 text-red-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">
            Epic MyChart
            {isConnected && (
              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                Connected
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">
            {isConnected
              ? `Health records synced from your Epic account${epicRecords?.last_synced ? ` · last updated ${new Date(epicRecords.last_synced).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}`
              : epicStatus.available
              ? "Connect your Epic account to pull your conditions, medications, allergies, and vitals directly into Anilla"
              : "Epic integration coming soon — your clinic will enable this when it's ready"}
          </p>
          {hasError && (
            <p className="mt-1 text-xs text-red-600">{epicRecords.error}</p>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {isConnected ? (
          <button
            onClick={onDisconnect}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Disconnect
          </button>
        ) : epicStatus.available ? (
          <button
            onClick={onConnect}
            disabled={connecting}
            className="rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-800 disabled:opacity-50"
          >
            {connecting ? "Connecting…" : hasError ? "Retry" : "Connect Epic"}
          </button>
        ) : (
          <span className="text-xs italic text-gray-400">Not configured</span>
        )}
      </div>
    </section>
  );
}

// ── FHIR data sections ─────────────────────────────────────────────────────

function EpicDataSections({ records }: { records: EpicRecordsResponse }) {
  if (!records.connected) return null;

  const criticality: Record<string, string> = {
    high: "text-red-600 bg-red-50",
    low: "text-yellow-600 bg-yellow-50",
    unable_to_assess: "text-gray-500 bg-gray-50",
  };

  return (
    <>
      {/* Conditions */}
      <SectionCard
        title="Conditions"
        action={<EpicBadge label="from Epic" />}
      >
        {records.conditions.length === 0 ? (
          <EmptyState text="No active conditions on file." />
        ) : (
          <ul className="space-y-2">
            {records.conditions.map((c) => (
              <li key={c.id} className="flex items-start gap-3 text-sm">
                <span className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-primary-400" />
                <div>
                  <span className="text-gray-900">{c.code_display}</span>
                  {c.onset_date && (
                    <span className="ml-2 text-xs text-gray-400">
                      since{" "}
                      {new Date(c.onset_date).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                      })}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* Medications */}
      <SectionCard
        title="Medications"
        action={<EpicBadge label="from Epic" />}
      >
        {records.medications.length === 0 ? (
          <EmptyState text="No active medications on file." />
        ) : (
          <ul className="space-y-3">
            {records.medications.map((m) => (
              <li key={m.id} className="flex items-start gap-3 text-sm">
                <span className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-accent-400" />
                <div>
                  <p className="font-medium text-gray-900">{m.medication_display}</p>
                  {m.dosage && (
                    <p className="text-xs text-gray-500">{m.dosage}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* Allergies */}
      <SectionCard
        title="Allergies"
        action={<EpicBadge label="from Epic" />}
      >
        {records.allergies.length === 0 ? (
          <EmptyState text="No allergies on file." />
        ) : (
          <ul className="space-y-2">
            {records.allergies.map((a) => (
              <li key={a.id} className="flex items-start gap-3 text-sm">
                <span
                  className={`mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    criticality[a.criticality ?? ""] ?? "text-gray-500 bg-gray-50"
                  }`}
                >
                  {a.criticality ?? "—"}
                </span>
                <div>
                  <span className="text-gray-900">{a.substance_display}</span>
                  {a.reaction && (
                    <span className="ml-1.5 text-xs text-gray-400">→ {a.reaction}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* Vitals */}
      {records.observations.length > 0 && (
        <SectionCard
          title="Recent Vitals"
          action={<EpicBadge label="from Epic" />}
        >
          <div className="grid grid-cols-2 gap-3">
            {records.observations.map((o) => (
              <div
                key={o.id}
                className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5"
              >
                <p className="text-[11px] font-medium text-gray-500">{o.code_display}</p>
                <p className="mt-0.5 text-sm font-semibold text-gray-900">{o.value}</p>
                {o.effective_date && (
                  <p className="mt-0.5 text-[10px] text-gray-400">
                    {new Date(o.effective_date).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export function MedicalRecordPage() {
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [records, setRecords] = useState<Appointment[]>([]);
  const [medications, setMedications] = useState<string[]>([]);
  const [epicStatus, setEpicStatus] = useState<EpicStatus | null>(null);
  const [epicRecords, setEpicRecords] = useState<EpicRecordsResponse | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getMyProfile(),
      getMyRecords(),
      getMyMedications(),
      getEpicStatus().catch(() => null),
    ])
      .then(async ([prof, recs, meds, status]) => {
        setProfile(prof);
        setRecords(recs);
        setMedications(meds);
        setEpicStatus(status);

        // Auto-fetch FHIR records if already connected
        if (status?.available && status.connected) {
          const fhirRecords = await getEpicRecords().catch(() => null);
          setEpicRecords(fhirRecords);
        }
      })
      .catch(() => setError("Unable to load your medical record. Please try again."))
      .finally(() => setLoading(false));
  }, []);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const { available, url } = await startEpicAuth();
      if (!available || !url) return;
      window.location.href = url;
    } catch {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    await disconnectEpic().catch(() => {});
    setEpicStatus((s) => (s ? { ...s, connected: false } : s));
    setEpicRecords(null);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-12 rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        {error}
      </div>
    );
  }

  const epicConnected = epicStatus?.available && epicStatus.connected && epicRecords?.connected;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My Health Record</h1>
        <Link to="/" className="text-sm text-primary-600 hover:underline">
          ← Dashboard
        </Link>
      </div>

      {/* Epic connect / status panel */}
      <EpicConnectPanel
        epicStatus={epicStatus}
        epicRecords={epicRecords}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        connecting={connecting}
      />

      {/* FHIR data from Epic (when connected) */}
      {epicConnected && epicRecords && <EpicDataSections records={epicRecords} />}

      {/* Profile */}
      {profile && (
        <SectionCard title="Profile">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Date of Birth</p>
              <p className="mt-0.5 font-medium text-gray-900">
                {new Date(profile.date_of_birth + "T00:00:00").toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            </div>
            <div>
              <p className="text-gray-500">Language</p>
              <p className="mt-0.5 font-medium uppercase text-gray-900">
                {profile.language_preference}
              </p>
            </div>
          </div>
        </SectionCard>
      )}

      {/* Medications from Anilla (shown only when Epic is NOT providing them) */}
      {!epicConnected && (
        <SectionCard title="Medications">
          {medications.length === 0 ? (
            <EmptyState text="No medications on file." />
          ) : (
            <ul className="space-y-2">
              {medications.map((med, i) => (
                <li key={i} className="flex items-center gap-3 text-sm text-gray-800">
                  <span className="h-2 w-2 flex-shrink-0 rounded-full bg-accent-400" />
                  {med}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      )}

      {/* Visit history */}
      <SectionCard title="Visit History">
        {records.length === 0 ? (
          <EmptyState text="No past visits on record." />
        ) : (
          <div className="space-y-2">
            {records.map((rec) => (
              <Link
                key={rec.id}
                to={`/appointments/${rec.id}`}
                className="block rounded-lg border border-gray-100 p-4 transition-colors hover:bg-gray-50"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {rec.visit_type === "yearly_checkup" ? "Yearly Checkup" : "Specific Concern"}
                    </p>
                    {rec.summary && (
                      <p className="mt-1 max-w-sm truncate text-xs text-gray-500">
                        {rec.summary}
                      </p>
                    )}
                  </div>
                  <div className="ml-4 shrink-0 text-right">
                    <p className="text-xs text-gray-500">
                      {new Date(
                        rec.scheduled_start ?? rec.created_at
                      ).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </p>
                    <span
                      className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        rec.status === "completed"
                          ? "bg-gray-100 text-gray-600"
                          : "bg-red-100 text-red-600"
                      }`}
                    >
                      {rec.status === "completed" ? "Completed" : "Cancelled"}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
