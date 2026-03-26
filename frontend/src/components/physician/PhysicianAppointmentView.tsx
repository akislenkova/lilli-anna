import { useState } from "react";
import { FeedbackForm } from "./FeedbackForm";
import type { Appointment, AIReport } from "../../types";

interface Props {
  appointment: Appointment;
  report: AIReport;
}

export function PhysicianAppointmentView({ appointment, report }: Props) {
  const [showTranscript, setShowTranscript] = useState(false);

  return (
    <div className="space-y-6">
      {/* AI Report */}
      <div className="bg-white rounded-xl shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">AI Report</h3>

        {report.probable_diagnoses && report.probable_diagnoses.length > 0 && (
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Probable Areas of Inquiry
            </h4>
            <div className="space-y-2">
              {report.probable_diagnoses.map((dx, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{dx.condition}</p>
                    <p className="text-sm text-gray-500">{dx.reasoning}</p>
                  </div>
                  <div className="text-right">
                    <div className="w-16 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${dx.confidence * 100}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {Math.round(dx.confidence * 100)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4 p-4 bg-blue-50 rounded-lg">
          <div>
            <p className="text-xs text-blue-600">Suggested Duration</p>
            <p className="text-lg font-semibold text-blue-900">
              {report.suggested_duration} min
            </p>
          </div>
          <div>
            <p className="text-xs text-blue-600">Confidence</p>
            <p className="text-lg font-semibold text-blue-900">
              {Math.round((report.confidence_level ?? 0) * 100)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-blue-600">Complexity</p>
            <p className="text-lg font-semibold text-blue-900">
              {report.complexity_score != null
                ? (report.complexity_score <= 0.3
                    ? "Low"
                    : report.complexity_score <= 0.6
                    ? "Medium"
                    : "High")
                : "N/A"}
            </p>
          </div>
        </div>

        {report.medication_interactions && report.medication_interactions.length > 0 && (
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <h4 className="text-sm font-medium text-amber-800 mb-2">
              Potential Medication Interactions
            </h4>
            <ul className="text-sm text-amber-700 space-y-1">
              {report.medication_interactions.map((interaction, i) => (
                <li key={i}>- {interaction}</li>
              ))}
            </ul>
          </div>
        )}

        {report.full_report && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Full Report
            </h4>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">
              {report.full_report}
            </p>
          </div>
        )}
      </div>

      {/* Transcript */}
      <div className="bg-white rounded-xl shadow p-6">
        <button
          onClick={() => setShowTranscript(!showTranscript)}
          className="flex items-center justify-between w-full"
        >
          <h3 className="text-lg font-semibold text-gray-900">
            Conversation Transcript
          </h3>
          <span className="text-gray-400">{showTranscript ? "Hide" : "Show"}</span>
        </button>
        {showTranscript && appointment.transcript && (
          <div className="mt-4 space-y-3">
            {appointment.transcript.map((msg, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg ${
                  msg.role === "patient"
                    ? "bg-blue-50 ml-8"
                    : msg.role === "ai"
                    ? "bg-gray-50 mr-8"
                    : "bg-yellow-50"
                }`}
              >
                <p className="text-xs font-medium text-gray-500 mb-1">
                  {msg.role === "patient" ? "Patient" : msg.role === "ai" ? "AI" : "System"}
                </p>
                <p className="text-sm text-gray-700">{msg.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Post-appointment feedback */}
      {appointment.status === "completed" && !appointment.feedback_submitted && (
        <FeedbackForm appointmentId={appointment.id} />
      )}
    </div>
  );
}
