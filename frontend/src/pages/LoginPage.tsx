import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// ─── Anilla loop logo ─────────────────────────────────────────────────────────
// The loop mark represents continuous optimization — intake in, schedule out.
function LoopLogo({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M31 18a13 13 0 1 1-2.6-7.9"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <path
        d="M28 6.5l.5 5.4-5.4.5"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
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
  { label: "60 min", pct: "82%",  shade: "bright" },
  { label: "20 min", pct: "28%",  shade: "mid"    },
  { label: "40 min", pct: "56%",  shade: "mid"    },
  { label: "15 min", pct: "22%",  shade: "dim"    },
];

const BAR_COLORS: Record<typeof SCHEDULE_ITEMS[number]["shade"], string> = {
  bright: "bg-accent-400/80",
  mid:    "bg-accent-400/45",
  dim:    "bg-white/20",
};

function FlowDiagram() {
  return (
    <div className="w-full rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur-sm">
      <div className="grid grid-cols-[1fr_56px_1fr] items-center gap-3">

        {/* ── Input: messy patient language ── */}
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-primary-300">
            Patient says
          </p>
          <div className="flex flex-col gap-1.5">
            {INTAKE_ITEMS.map((item, i) => (
              <div
                key={i}
                className={`rounded-lg px-3 py-2 text-[11px] leading-snug ${
                  item.active
                    ? "border border-white/20 bg-white/15 text-white"
                    : "bg-white/[0.06] text-white/55"
                }`}
              >
                "{item.text}"
              </div>
            ))}
          </div>
        </div>

        {/* ── Center: AI processor ── */}
        <div className="flex flex-col items-center gap-1.5">
          <div className="rounded-full border border-accent-400/30 bg-accent-500/20 p-3">
            <LoopLogo size={20} className="text-accent-300" />
          </div>
          <span className="text-[9px] font-bold uppercase tracking-widest text-accent-300">
            AI
          </span>
        </div>

        {/* ── Output: clean time blocks ── */}
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-primary-300">
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
    <div className="flex min-h-screen bg-gray-50">

      {/* ── Left panel ─────────────────────────────────────────────────────── */}
      <div
        className="hidden flex-col justify-between p-12 lg:flex lg:w-1/2"
        style={{ background: "linear-gradient(155deg, #1a5c54 0%, #162847 100%)" }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 text-white">
            <LoopLogo size={24} />
          </div>
          <span className="text-xl font-semibold tracking-tight text-white">Anilla</span>
        </div>

        {/* Flow illustration */}
        <div className="mx-auto w-full max-w-md">
          <FlowDiagram />
        </div>

        {/* Headline */}
        <div>
          <p className="mb-3 text-3xl font-light leading-snug text-primary-100">
            Schedule patients by need,{" "}
            <span className="font-semibold text-white">not guesswork.</span>
          </p>
          <p className="text-sm text-primary-200">
            AI that predicts visit length from patient intake data.
          </p>
          <p className="mt-6 text-xs text-primary-400 italic">
            Pending HIPAA compliance · All access is logged and audited.
          </p>
        </div>
      </div>

      {/* ── Right panel ────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">

          {/* Mobile logo */}
          <div className="mb-10 flex items-center gap-2.5 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600 text-white">
              <LoopLogo size={22} />
            </div>
            <span className="text-lg font-semibold tracking-tight text-gray-900">Anilla</span>
          </div>

          <h2 className="mb-1 text-2xl font-semibold text-gray-900">Welcome back</h2>
          <p className="mb-8 text-sm text-gray-500">Sign in to continue</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@clinic.com"
                className="w-full rounded-lg border border-gray-200 bg-white px-3.5 py-2.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3.5 py-2.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-2.5 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full rounded-lg bg-primary-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>

            <p className="text-center text-xs text-gray-400">
              We'll route you to the right view automatically
            </p>
          </form>

          {/* Trust indicator */}
          <div className="mt-8 flex items-center gap-3 rounded-xl border border-primary-100 bg-primary-50 px-4 py-3">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary-100">
              <LoopLogo size={18} className="text-primary-600" />
            </div>
            <div>
              <p className="text-xs font-semibold text-primary-700">95.5% scheduling accuracy</p>
              <p className="text-xs text-gray-500">Validated on 22,000+ patient records</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
