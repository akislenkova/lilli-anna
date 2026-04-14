import { useEffect, useState } from "react";
import { FeedbackForm } from "./FeedbackForm";
import { getConversationByAppointment } from "../../services/conversations";
import { getPhysicianEpicLaunchUrl } from "../../services/epic";
import { AppointmentMessageThread } from "../common/AppointmentMessageThread";
import type { ConversationState } from "../../services/conversations";
import type { Appointment } from "../../types";

interface Props {
  appointment: Appointment;
}

export function PhysicianAppointmentView({ appointment }: Props) {
  const [showTranscript, setShowTranscript] = useState(false);
  const [transcript, setTranscript] = useState<ConversationState | null>(null);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [epicUrl, setEpicUrl] = useState<string | null>(null);
  const [epicAvailable, setEpicAvailable] = useState(false);
  const [epicLoading, setEpicLoading] = useState(true);

  useEffect(() => {
    getPhysicianEpicLaunchUrl(appointment.patient_id)
      .then(({ url, available }) => {
        setEpicUrl(url);
        setEpicAvailable(available);
      })
      .catch(() => {})
      .finally(() => setEpicLoading(false));
  }, [appointment.patient_id]);

  // Fetch transcript on first expand
  useEffect(() => {
    if (showTranscript && !transcript) {
      setLoadingTranscript(true);
      getConversationByAppointment(appointment.id)
        .then(setTranscript)
        .catch(() => {})
        .finally(() => setLoadingTranscript(false));
    }
  }, [showTranscript, transcript, appointment.id]);

  return (
    <div className="space-y-6">
      {/* AI Summary Card */}
      <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          AI Intake Summary
        </h3>

        <div className="grid grid-cols-3 gap-4 p-4 bg-primary-50 rounded-lg">
          <div>
            <p className="text-xs text-primary-600">Suggested Duration</p>
            <p className="text-lg font-semibold text-primary-900">
              {appointment.ai_suggested_duration
                ? `${appointment.ai_suggested_duration} min`
                : "Pending"}
            </p>
          </div>
          <div>
            <p className="text-xs text-primary-600">Confidence</p>
            <p className="text-lg font-semibold text-primary-900">
              {appointment.ai_confidence != null
                ? `${Math.round(appointment.ai_confidence * 100)}%`
                : "N/A"}
            </p>
          </div>
          <div>
            <p className="text-xs text-primary-600">Duration Range</p>
            <p className="text-lg font-semibold text-primary-900">
              {appointment.ai_duration_range_min && appointment.ai_duration_range_max
                ? `${appointment.ai_duration_range_min}–${appointment.ai_duration_range_max} min`
                : "N/A"}
            </p>
          </div>
        </div>

        {appointment.scheduler_approved_duration && (
          <div className="mt-3 p-3 bg-emerald-50 rounded-lg flex items-center gap-2">
            <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm font-medium text-emerald-800">
              Scheduler approved: {appointment.scheduler_approved_duration} min
              {appointment.scheduler_override_reason && (
                <span className="text-emerald-600 font-normal ml-1">
                  — {appointment.scheduler_override_reason}
                </span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* Patient Info */}
      <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Patient Information
        </h3>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Patient ID</dt>
            <dd className="font-medium font-mono text-gray-900">
              {appointment.patient_id.slice(0, 8)}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Visit Type</dt>
            <dd className="font-medium text-gray-900">
              {appointment.visit_type === "yearly_checkup"
                ? "Yearly Checkup"
                : "Specific Concern"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">New Patient</dt>
            <dd className="font-medium text-gray-900">
              {appointment.is_new_patient ? "Yes" : "No"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Intake Status</dt>
            <dd className="font-medium text-gray-900">
              {appointment.status === "intake_complete"
                ? "Intake Complete"
                : appointment.status.replace("_", " ")}
            </dd>
          </div>
        </dl>
      </div>

      {/* Epic Chart */}
      <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50">
              {/* Epic logo colour is red/maroon */}
              <svg className="h-5 w-5 text-red-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h3 className="text-base font-semibold text-gray-900">Epic Patient Chart</h3>
              <p className="text-xs text-gray-500">Opens the full medical record in Epic EHR</p>
            </div>
          </div>
          {epicLoading ? (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-red-600" />
          ) : epicAvailable && epicUrl ? (
            <a
              href={epicUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 transition-colors"
            >
              Open in Epic
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          ) : (
            <span className="text-xs text-gray-400 italic">Epic not configured</span>
          )}
        </div>
      </div>

      {/* Conversation Transcript */}
      <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow p-6">
        <button
          onClick={() => setShowTranscript(!showTranscript)}
          className="flex items-center justify-between w-full"
        >
          <h3 className="text-lg font-semibold text-gray-900">
            Intake Conversation
          </h3>
          <span className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-800">
            {showTranscript ? (
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

        {showTranscript && (
          <div className="mt-4">
            {loadingTranscript ? (
              <div className="flex justify-center py-6">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
              </div>
            ) : transcript && transcript.messages.length > 0 ? (
              <div className="space-y-3">
                {transcript.messages
                  .filter((msg) => msg.role !== "system")
                  .map((msg, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-lg ${
                        msg.role === "patient"
                          ? "bg-primary-50 ml-8"
                          : "bg-gray-50 mr-8"
                      }`}
                    >
                      <p className="text-xs font-medium uppercase tracking-wide mb-1 ${
                        msg.role === 'patient' ? 'text-primary-500' : 'text-gray-400'
                      }">
                        {msg.role === "patient" ? "Patient" : "AI"}
                      </p>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">
                        {msg.content}
                      </p>
                    </div>
                  ))}
                <div className="text-xs text-gray-400 text-center pt-2">
                  {transcript.questions_asked_count} questions asked
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 py-4 text-center">
                No conversation transcript available.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Staff messages */}
      <AppointmentMessageThread appointmentId={appointment.id} />

      {/* Post-appointment feedback */}
      {appointment.status === "completed" && !appointment.feedback_submitted && (
        <FeedbackForm appointmentId={appointment.id} />
      )}
    </div>
  );
}
