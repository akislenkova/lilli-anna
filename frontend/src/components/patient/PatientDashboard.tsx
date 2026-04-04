import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppointments } from "../../services/appointments";
import type { Appointment } from "../../types";

export function PatientDashboard() {
  const [upcoming, setUpcoming] = useState<Appointment[]>([]);
  const [past, setPast] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAppointments({})
      .then((data) => {
        const now = new Date();
        setUpcoming(
          data.filter(
            (a) =>
              a.scheduled_start && new Date(a.scheduled_start) >= now && a.status !== "cancelled"
          )
        );
        setPast(
          data.filter(
            (a) =>
              a.status === "completed" ||
              (a.scheduled_start && new Date(a.scheduled_start) < now)
          )
        );
      })
      .catch(() => {
        // API may not have appointments yet
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My Dashboard</h1>
        <Link
          to="/intake"
          className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Schedule New Visit
        </Link>
      </div>

      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Upcoming Appointments
        </h2>
        {upcoming.length === 0 ? (
          <div className="bg-gray-50 rounded-lg p-6 text-center text-gray-500">
            No upcoming appointments.{" "}
            <Link to="/intake" className="text-blue-600 hover:underline">
              Schedule one now
            </Link>
            .
          </div>
        ) : (
          <div className="space-y-3">
            {upcoming.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="block bg-white rounded-xl shadow p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">
                      {appt.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                    </p>
                    <p className="text-sm text-gray-500">
                      {appt.scheduled_start
                        ? new Date(appt.scheduled_start).toLocaleDateString(
                            undefined,
                            {
                              weekday: "long",
                              month: "long",
                              day: "numeric",
                              hour: "numeric",
                              minute: "2-digit",
                            }
                          )
                        : "Time pending"}
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                    {appt.status.replace("_", " ")}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Past Appointments
        </h2>
        {past.length === 0 ? (
          <p className="text-gray-500 text-sm">No past appointments.</p>
        ) : (
          <div className="space-y-3">
            {past.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="block bg-white rounded-xl shadow p-4 hover:shadow-md transition-shadow opacity-75"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-700">
                      {appt.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                    </p>
                    <p className="text-sm text-gray-500">
                      {appt.scheduled_start &&
                        new Date(appt.scheduled_start).toLocaleDateString()}
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                    {appt.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
