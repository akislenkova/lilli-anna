import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppointments } from "../../services/appointments";
import { RedFlagBanner } from "../common/RedFlagBanner";
import type { Appointment } from "../../types";

export function NurseDashboard() {
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Nursing Overview</h1>

      {redFlagAppts.length > 0 && (
        <RedFlagBanner flags={redFlagAppts.flatMap((a) => a.red_flags ?? [])} />
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
                      {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      {appt.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                      {appt.scheduled_start &&
                        ` — ${new Date(appt.scheduled_start).toLocaleString()}`}
                    </p>
                    {appt.summary && (
                      <p className="text-sm text-gray-600 mt-2 bg-gray-50 rounded p-2">
                        {appt.summary}
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    {appt.ai_suggested_duration && (
                      <p className="text-sm font-medium text-blue-700">
                        {appt.ai_suggested_duration} min
                      </p>
                    )}
                    {appt.red_flags && appt.red_flags.length > 0 && (
                      <span className="inline-block mt-1 px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-medium">
                        RED FLAG
                      </span>
                    )}
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
