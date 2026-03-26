import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getAppointment } from "../services/appointments";
import { getReport } from "../services/reports";
import { PhysicianAppointmentView } from "../components/physician/PhysicianAppointmentView";
import { RedFlagBanner } from "../components/common/RedFlagBanner";
import type { Appointment, AIReport } from "../types";

export function AppointmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [report, setReport] = useState<AIReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
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

      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Appointment Details
          </h2>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              appointment.status === "completed"
                ? "bg-green-100 text-green-700"
                : appointment.status === "cancelled"
                ? "bg-red-100 text-red-700"
                : "bg-blue-100 text-blue-700"
            }`}
          >
            {appointment.status.replace("_", " ").toUpperCase()}
          </span>
        </div>

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

      {user?.role === "physician" && report && (
        <PhysicianAppointmentView appointment={appointment} report={report} />
      )}

      {user?.role === "scheduler" && (
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-gray-900 mb-3">
            Patient Reason for Visit
          </h3>
          <p className="text-gray-700">{appointment.initial_reason ?? "N/A"}</p>
          {report && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm font-medium text-blue-800">
                AI Recommended: {report.suggested_duration} minutes
                {report.duration_range_min && report.duration_range_max && (
                  <span className="text-blue-600 ml-1">
                    (range: {report.duration_range_min}–
                    {report.duration_range_max} min)
                  </span>
                )}
              </p>
            </div>
          )}
        </div>
      )}

      {user?.role === "nurse" && report && (
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-gray-900 mb-3">Visit Summary</h3>
          <p className="text-gray-700">{report.summary}</p>
        </div>
      )}
    </div>
  );
}
