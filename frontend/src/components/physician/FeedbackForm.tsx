import { useState } from "react";
import { submitFeedback } from "../../services/feedback";

interface Props {
  appointmentId: string;
}

export function FeedbackForm({ appointmentId }: Props) {
  const [accuracy, setAccuracy] = useState<"accurate" | "too_short" | "too_long" | "">("");
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accuracy) return;
    setLoading(true);
    try {
      await submitFeedback({
        appointment_id: appointmentId,
        time_accuracy: accuracy,
        actual_vs_suggested_delta: delta ? parseInt(delta) : 0,
        reason_text: reason,
      });
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
        <p className="text-green-700 font-medium">
          Thank you for your feedback. This helps improve future time estimates.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Post-Appointment Feedback
      </h3>
      <p className="text-sm text-gray-500 mb-4">
        Was the suggested appointment duration accurate?
      </p>

      <div className="flex gap-3 mb-4">
        {[
          { value: "accurate" as const, label: "Accurate", color: "green" },
          { value: "too_short" as const, label: "Too Short", color: "red" },
          { value: "too_long" as const, label: "Too Long", color: "amber" },
        ].map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setAccuracy(opt.value)}
            className={`flex-1 py-3 rounded-lg text-sm font-medium transition-colors border-2 ${
              accuracy === opt.value
                ? opt.color === "green"
                  ? "border-green-500 bg-green-50 text-green-700"
                  : opt.color === "red"
                  ? "border-red-500 bg-red-50 text-red-700"
                  : "border-amber-500 bg-amber-50 text-amber-700"
                : "border-gray-200 text-gray-600 hover:border-gray-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {accuracy && accuracy !== "accurate" && (
        <>
          <div className="mb-4">
            <label className="block text-sm text-gray-700 mb-1">
              How many minutes off? (optional)
            </label>
            <input
              type="number"
              value={delta}
              onChange={(e) => setDelta(e.target.value)}
              placeholder="e.g., 10"
              className="w-32 px-3 py-2 border rounded-lg text-sm"
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm text-gray-700 mb-1">
              Why was the estimate off? (optional)
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="e.g., Patient had additional concerns not captured in intake..."
              className="w-full px-3 py-2 border rounded-lg text-sm"
            />
          </div>
        </>
      )}

      <button
        type="submit"
        disabled={!accuracy || loading}
        className="bg-primary-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
      >
        {loading ? "Submitting..." : "Submit Feedback"}
      </button>
    </form>
  );
}
