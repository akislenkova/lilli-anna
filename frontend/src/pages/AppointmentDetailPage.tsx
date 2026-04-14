import { cancelAppointment, requestReschedule } from "../services/appointments";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getAppointment } from "../services/appointments";
import { getReport } from "../services/reports";
import { getConversationByAppointment } from "../services/conversations";
import { PhysicianAppointmentView } from "../components/physician/PhysicianAppointmentView";
import { RedFlagBanner } from "../components/common/RedFlagBanner";
import { AppointmentMessageThread } from "../components/common/AppointmentMessageThread";
import type { Appointment, AIReport } from "../types";
import type { ConversationState } from "../services/conversations";

export function AppointmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [report, setReport] = useState<AIReport | null>(null);
  const [nurseTranscript, setNurseTranscript] = useState<ConversationState | null>(null);
  const [showNurseTranscript, setShowNurseTranscript] = useState(false);
  const [loadingNurseTranscript, setLoadingNurseTranscript] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);
const [cancelError, setCancelError] = useState("");

const handleCancel = async () => {
  if (!id || !window.confirm("Are you sure you want to cancel this appointment?")) return;
  setCancelling(true);
  setCancelError("");
  try {
    const updated = await cancelAppointment(id);
    setAppointment(updated);
  } catch {
    setCancelError("Failed to cancel appointment. Please try again.");
  } finally {
    setCancelling(false);
  }
};

const [showRescheduleForm, setShowRescheduleForm] = useState(false);
const [rescheduleReason, setRescheduleReason] = useState("");
const [rescheduling, setRescheduling] = useState(false);
const [rescheduleError, setRescheduleError] = useState("");

const handleRescheduleRequest = async () => {
  if (!id) return;
  setRescheduling(true);
  setRescheduleError("");
  try {
    const updated = await requestReschedule(id, rescheduleReason);
    setAppointment(updated);
    setShowRescheduleForm(false);
    setRescheduleReason("");
  } catch {
    setRescheduleError("Failed to submit reschedule request. Please try again.");
  } finally {
    setRescheduling(false);
  }
};

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        const [appt, rpt] = await Promise.all([
          getAppointment(id),
          getReport(id).catch(() => null),
        ]);
        setAppointment(appt);
        setReport(rpt);
      } catch {
        setError("Unable to load appointment details.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  useEffect(() => {
    if (!id || user?.role !== "nurse" || !showNurseTranscript || nurseTranscript) return;
    setLoadingNurseTranscript(true);
    getConversationByAppointment(id)
      .then(setNurseTranscript)
      .catch(() => {})
      .finally(() => setLoadingNurseTranscript(false));
  }, [id, user?.role, showNurseTranscript, nurseTranscript]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error || !appointment) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error || "Appointment not found."}</div>
    );
  }

  const redFlags = report?.red_flags ?? [];

  return (
    <div className="space-y-6">
      {redFlags.length > 0 && <RedFlagBanner flags={redFlags} />}

      <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
<div className="flex items-center justify-between mb-4">
  <div>
    <h2 className="text-xl font-semibold text-gray-900">
      Appointment Details
    </h2>
    <span
      className={`mt-1 inline-block px-3 py-1 rounded-full text-xs font-medium ${
        appointment.status === "completed"
          ? "bg-green-100 text-green-700"
          : appointment.status === "cancelled"
          ? "bg-red-100 text-red-700"
          : appointment.status === "reschedule_requested"
          ? "bg-yellow-100 text-yellow-700"
          : "bg-primary-100 text-primary-700"
      }`}
    >
      {appointment.status.replace(/_/g, " ").toUpperCase()}
    </span>
  </div>
  <div className="flex items-center gap-3">
    {cancelError && (
      <p className="text-sm text-red-600">{cancelError}</p>
    )}
    {appointment.status !== "cancelled" && appointment.status !== "completed" && (
      <button
        onClick={handleCancel}
        disabled={cancelling}
        className="px-4 py-1.5 rounded-lg text-sm font-medium bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50 transition-colors"
      >
        {cancelling ? "Cancelling…" : "Cancel Appointment"}
      </button>
    )}
    {appointment.status !== "cancelled" &&
      appointment.status !== "completed" &&
      appointment.status !== "reschedule_requested" &&
      user?.role === "patient" && (
      <button
        onClick={() => setShowRescheduleForm(!showRescheduleForm)}
        className="px-4 py-1.5 rounded-lg text-sm font-medium bg-yellow-50 text-yellow-700 border border-yellow-200 hover:bg-yellow-100 transition-colors"
      >
        Request Reschedule
      </button>
    )}
  </div>
</div>

{showRescheduleForm && (
  <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
    <p className="text-sm font-medium text-yellow-800 mb-2">Reason for rescheduling (optional)</p>
    <textarea
      value={rescheduleReason}
      onChange={(e) => setRescheduleReason(e.target.value)}
      placeholder="e.g. conflict with work schedule..."
      className="w-full text-sm border border-yellow-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-yellow-400 bg-white"
      rows={2}
    />
    {rescheduleError && <p className="text-sm text-red-600 mt-1">{rescheduleError}</p>}
    <div className="flex gap-2 mt-3">
      <button
        onClick={handleRescheduleRequest}
        disabled={rescheduling}
        className="px-4 py-1.5 rounded-lg text-sm font-medium bg-yellow-600 text-white hover:bg-yellow-700 disabled:opacity-50 transition-colors"
      >
        {rescheduling ? "Submitting…" : "Submit Request"}
      </button>
      <button
        onClick={() => setShowRescheduleForm(false)}
        className="px-4 py-1.5 rounded-lg text-sm font-medium text-yellow-700 hover:bg-yellow-100 transition-colors"
      >
        Cancel
      </button>
    </div>
  </div>
)}
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Visit Type</dt>
            <dd className="font-medium">
              {appointment.visit_type === "yearly_checkup"
                ? "Yearly Checkup"
                : "Specific Concern"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Scheduled</dt>
            <dd className="font-medium">
              {appointment.scheduled_start
                ? new Date(appointment.scheduled_start).toLocaleString()
                : "Not yet scheduled"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">AI Suggested Duration</dt>
            <dd className="font-medium">
              {appointment.ai_suggested_duration
                ? `${appointment.ai_suggested_duration} min`
                : "Pending"}
              {appointment.ai_confidence != null && (
                <span className="text-gray-400 ml-1">
                  ({Math.round(appointment.ai_confidence * 100)}% confidence)
                </span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Approved Duration</dt>
            <dd className="font-medium">
              {appointment.scheduler_approved_duration
                ? `${appointment.scheduler_approved_duration} min`
                : "Awaiting scheduler"}
            </dd>
          </div>
        </dl>
      </div>

      {user?.role === "physician" && (
        <PhysicianAppointmentView appointment={appointment} />
      )}

      {user?.role === "scheduler" && (
        <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
          <h3 className="font-semibold text-gray-900 mb-3">
            Patient Reason for Visit
          </h3>
          <p className="text-gray-700">{appointment.initial_reason ?? "N/A"}</p>
          {report && (
            <div className="mt-4 p-4 bg-primary-50 rounded-lg">
              <p className="text-sm font-medium text-primary-800">
                AI Recommended: {report.suggested_duration} minutes
                {report.duration_range_min && report.duration_range_max && (
                  <span className="text-primary-600 ml-1">
                    (range: {report.duration_range_min}–
                    {report.duration_range_max} min)
                  </span>
                )}
              </p>
            </div>
          )}
        </div>
      )}

      {user?.role === "nurse" && (
        <>
          {report?.summary && (
            <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
              <h3 className="font-semibold text-gray-900 mb-3">AI Intake Summary</h3>
              <p className="text-gray-700 text-sm">{report.summary}</p>
            </div>
          )}

          {/* Intake conversation — nurses can read, no medical record or Epic */}
          <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
            <button
              onClick={() => setShowNurseTranscript(!showNurseTranscript)}
              className="flex items-center justify-between w-full"
            >
              <h3 className="text-lg font-semibold text-gray-900">Intake Conversation</h3>
              <span className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-800">
                {showNurseTranscript ? (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                    </svg>
                    Hide
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                    Show transcript
                  </>
                )}
              </span>
            </button>

            {showNurseTranscript && (
              <div className="mt-4">
                {loadingNurseTranscript ? (
                  <div className="flex justify-center py-6">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
                  </div>
                ) : nurseTranscript && nurseTranscript.messages.length > 0 ? (
                  <div className="space-y-3">
                    {nurseTranscript.messages
                      .filter((msg) => msg.role !== "system")
                      .map((msg, i) => (
                        <div
                          key={i}
                          className={`p-3 rounded-lg ${
                            msg.role === "patient" ? "bg-primary-50 ml-8" : "bg-gray-50 mr-8"
                          }`}
                        >
                          <p className="text-xs font-medium uppercase tracking-wide mb-1 text-gray-400">
                            {msg.role === "patient" ? "Patient" : "AI"}
                          </p>
                          <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      ))}
                    <p className="text-xs text-gray-400 text-center pt-2">
                      {nurseTranscript.questions_asked_count} questions asked
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 py-4 text-center">
                    No conversation transcript available.
                  </p>
                )}
              </div>
            )}
          </div>

          <AppointmentMessageThread appointmentId={appointment.id} />
        </>
      )}

      {user?.role === "scheduler" && (
        <AppointmentMessageThread appointmentId={appointment.id} />
      )}
    </div>
  );
}
