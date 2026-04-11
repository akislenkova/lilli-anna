import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { Role } from "../types";

const ROLES: { value: Role; label: string }[] = [
  { value: "patient", label: "Patient" },
  { value: "scheduler", label: "Scheduling Clerk" },
  { value: "nurse", label: "Nurse" },
  { value: "physician", label: "Physician" },
];

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRole, setSelectedRole] = useState<Role>("patient");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

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
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left panel — brand */}
      <div className="hidden lg:flex lg:w-1/2 bg-primary-700 flex-col justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/20 text-white text-lg font-bold">
            A
          </div>
          <span className="text-white text-xl font-semibold tracking-tight">Anilla</span>
        </div>
        <div>
          <p className="text-primary-100 text-3xl font-light leading-snug mb-4">
            Smarter scheduling for <br />
            <span className="text-white font-semibold">better patient care.</span>
          </p>
          <p className="text-primary-200 text-sm">
            AI-powered clinic scheduling that matches patients to the right slot, every time.
          </p>
        </div>
        <p className="text-primary-300 text-xs">
          HIPAA-compliant · All access is logged and audited.
        </p>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-10 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white font-bold">
              A
            </div>
            <span className="text-gray-900 text-lg font-semibold tracking-tight">Anilla</span>
          </div>

          <h2 className="text-2xl font-semibold text-gray-900 mb-1">Welcome back</h2>
          <p className="text-sm text-gray-500 mb-8">Sign in to your account</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                I am a...
              </label>
              <div className="grid grid-cols-2 gap-2">
                {ROLES.map((role) => (
                  <button
                    key={role.value}
                    type="button"
                    onClick={() => setSelectedRole(role.value)}
                    className={`py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
                      selectedRole === role.value
                        ? "bg-primary-600 text-white border-primary-600"
                        : "bg-white text-gray-600 border-gray-200 hover:border-primary-300 hover:text-primary-700"
                    }`}
                  >
                    {role.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
                placeholder="you@clinic.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
            </div>

            {error && (
              <div className="bg-red-50 text-red-700 px-4 py-2.5 rounded-lg text-sm border border-red-100">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-primary-700 transition-colors disabled:opacity-50 mt-2"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
