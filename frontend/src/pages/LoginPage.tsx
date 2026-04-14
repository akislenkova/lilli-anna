import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// ─── Logo mark ────────────────────────────────────────────────────────────────
function LoopLogo({ size = 20, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path d="M31 18a13 13 0 1 1-2.6-7.9" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M28 6.5l.5 5.4-5.4.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────────────
function EnvelopeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M2 7l10 7 10-7" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

function SparkleIcon({ size = 22, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
    </svg>
  );
}

// ─── Left-panel flow diagram ──────────────────────────────────────────────────
const INTAKE_ITEMS = [
  { text: "chest tight, hard to breathe · 3 days", active: true },
  { text: "checking in on blood pressure meds" },
  { text: "anxious, not sleeping well lately" },
  { text: "just my annual checkup" },
];

const SCHEDULE_ITEMS: { label: string; pct: string; shade: "bright" | "mid" | "dim" }[] = [
  { label: "60 min", pct: "82%", shade: "bright" },
  { label: "20 min", pct: "28%", shade: "mid" },
  { label: "40 min", pct: "56%", shade: "mid" },
  { label: "15 min", pct: "22%", shade: "dim" },
];

const BAR_COLORS: Record<typeof SCHEDULE_ITEMS[number]["shade"], string> = {
  bright: "bg-blue-300/80",
  mid: "bg-blue-300/45",
  dim: "bg-white/20",
};

function FlowDiagram() {
  return (
    <div className="w-full rounded-2xl border border-white/15 bg-white/[0.07] p-5 backdrop-blur-sm">
      <div className="grid grid-cols-[1fr_56px_1fr] items-center gap-3">
        {/* Input */}
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-blue-200">
            Patient says
          </p>
          <div className="flex flex-col gap-1.5">
            {INTAKE_ITEMS.map((item, i) => (
              <div
                key={i}
                className={`rounded-lg px-3 py-2 text-[11px] leading-snug ${
                  item.active
                    ? "border border-white/20 bg-white/15 text-white"
                    : "bg-white/[0.06] text-white/50"
                }`}
              >
                "{item.text}"
              </div>
            ))}
          </div>
        </div>

        {/* Center AI */}
        <div className="flex flex-col items-center gap-1.5">
          <div className="rounded-full border border-blue-300/30 bg-blue-400/20 p-3">
            <LoopLogo size={20} className="text-blue-200" />
          </div>
          <span className="text-[9px] font-bold uppercase tracking-widest text-blue-200">AI</span>
        </div>

        {/* Output */}
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-blue-200">
            Appointment
          </p>
          <div className="flex flex-col gap-1.5">
            {SCHEDULE_ITEMS.map((item, i) => (
              <div key={i} className="flex items-center gap-2">
                <div
                  className={`h-7 flex-shrink-0 rounded ${BAR_COLORS[item.shade]}`}
                  style={{ width: item.pct }}
                />
                <span className="whitespace-nowrap text-[11px] font-semibold text-white">
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export function LoginPage() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const { login }               = useAuth();
  const navigate                = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex min-h-screen"
      style={{
        background: "linear-gradient(160deg, #dce8f5 0%, #c4d9ee 45%, #b0cceb 100%)",
      }}
    >
      {/* ── Left panel ─────────────────────────────────────────────────────── */}
      <div
        className="hidden flex-col justify-between p-12 lg:flex lg:w-1/2"
        style={{
          background: "linear-gradient(155deg, #1a3a6e 0%, #0f2657 50%, #091d45 100%)",
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-white">
            <LoopLogo size={22} />
          </div>
          <span className="text-xl font-semibold tracking-tight text-white">Anilla</span>
        </div>

        {/* Flow illustration */}
        <div className="mx-auto w-full max-w-md">
          <FlowDiagram />
        </div>

        {/* Headline + stats */}
        <div>
          <p className="mb-3 text-3xl font-light leading-snug text-blue-100">
            Schedule patients by need,{" "}
            <span className="font-semibold text-white">not guesswork.</span>
          </p>
          <p className="text-sm text-blue-200 italic">
            AI that predicts visit length from patient intake data.
          </p>

          {/* Accuracy badge */}
          <div className="mt-6 flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.07] px-4 py-3">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-blue-400/20 border border-blue-300/20">
              <SparkleIcon size={18} className="text-blue-200" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">95.5% scheduling accuracy</p>
              <p className="text-xs text-blue-300">Validated on 22,000+ patient records</p>
            </div>
          </div>

          <p className="mt-5 text-xs text-blue-400 italic">
            Pending HIPAA compliance · All access is logged and audited.
          </p>
        </div>
      </div>

      {/* ── Right panel ────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        {/* Mobile logo */}
        <div className="mb-8 flex items-center gap-2.5 lg:hidden">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gray-900 text-white">
            <LoopLogo size={18} />
          </div>
          <span className="text-xl font-semibold tracking-tight text-gray-900">Anilla</span>
        </div>

        {/* Form card */}
        <div className="w-full max-w-sm rounded-2xl bg-white/70 p-8 shadow-sm backdrop-blur-sm">
          <h1 className="mb-1 text-2xl font-bold text-gray-900">Welcome back</h1>
          <p className="mb-6 text-sm text-gray-500">Sign in to continue to your account</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-gray-700">
                Email
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-gray-400">
                  <EnvelopeIcon />
                </span>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@clinic.com"
                  className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-10 pr-3.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-gray-700">
                Password
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-gray-400">
                  <LockIcon />
                </span>
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-10 pr-3.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </div>
            </div>

            {/* Forgot */}
            <div className="flex justify-end">
              <button type="button" className="text-xs text-gray-500 hover:text-gray-700">
                Forgot password?
              </button>
            </div>

            {error && (
              <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-2.5 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gray-900 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-800 disabled:opacity-50"
            >
              {loading ? "Signing in…" : (
                <>
                  Sign in
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </>
              )}
            </button>
          </form>
        </div>

        {/* AI tagline card */}
        <div className="mt-4 w-full max-w-sm rounded-2xl bg-white/60 px-5 py-4 backdrop-blur-sm shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-500">
              <SparkleIcon size={18} />
            </div>
            <p className="text-sm text-gray-600">
              AI scheduling for tailoring appointments to patient needs
            </p>
          </div>
        </div>
      </div>

      {/* Help button */}
      <button
        className="fixed bottom-5 right-5 flex h-9 w-9 items-center justify-center rounded-full bg-gray-800 text-white text-sm font-semibold shadow-md hover:bg-gray-700"
        aria-label="Help"
      >
        ?
      </button>
    </div>
  );
}
