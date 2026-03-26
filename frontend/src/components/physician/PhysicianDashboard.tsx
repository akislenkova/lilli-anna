import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppointments } from "../../services/appointments";
import { RedFlagBanner } from "../common/RedFlagBanner";
import type { Appointment } from "../../types";

export function PhysicianDashboard() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAppointments({}).then((data) => {
      setAppointments(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const redFlagAppts = appointments.filter(
    (a) => a.red_flags && a.red_flags.length > 0
  );
  const upcoming = appointments.filter(
    (a) => a.status !== "completed" && a.status !== "cancelled"
  );
  const needsFeedback = appointments.filter(
    (a) => a.status === "completed" && !a.feedback_submitted
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">My Patients</h1>

      {redFlagAppts.length > 0 && (
        <RedFlagBanner
          flags={redFlagAppts.flatMap((a) => a.red_flags ?? [])}
        />
      )}

      {needsFeedback.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <h3 className="font-medium text-amber-800 mb-2">
            Feedback Needed ({needsFeedback.length})
          </h3>
          <p className="text-sm text-amber-700 mb-3">
            Please provide post-appointment feedback to help improve time
            estimation accuracy.
          </p>
          <div className="space-y-2">
            {needsFeedback.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="block text-sm text-amber-800 hover:text-amber-900 hover:underline"
              >
                Patient #{appt.patient_id?.slice(0, 8)} —{" "}
                {appt.scheduled_start &&
                  new Date(appt.scheduled_start).toLocaleDateString()}
              </Link>
            ))}
          </div>
        </div>
      )}

      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Upcoming Appointments ({upcoming.length})
        </h2>
        {upcoming.length === 0 ? (
          <p className="text-gray-500 text-sm">No upcoming appointments.</p>
        ) : (
          <div className="space-y-3">
            {upcoming.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="block bg-white rounded-xl shadow p-5 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">
                      Patient #{appt.patient_id?.slice(0, 8)}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      {appt.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                    </p>
                    <p className="text-sm text-gray-500">
                      {appt.scheduled_start
                        ? new Date(appt.scheduled_start).toLocaleString()
                        : "Not yet scheduled"}
                    </p>
                  </div>
                  <div className="text-right">
                    {appt.ai_suggested_duration && (
                      <p className="text-sm font-medium text-blue-700">
                        {appt.ai_suggested_duration} min
                      </p>
                    )}
                    {appt.is_updated && (
                      <span className="inline-block mt-1 px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded-full">
                        Updated
                      </span>
                    )}
                    <span
                      className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${
                        appt.status === "intake_complete"
                          ? "bg-green-100 text-green-700"
                          : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {appt.status.replace("_", " ")}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
