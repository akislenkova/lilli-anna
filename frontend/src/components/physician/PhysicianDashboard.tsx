import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppointments } from "../../services/appointments";
import { RedFlagBanner } from "../common/RedFlagBanner";
import type { Appointment } from "../../types";

function StatCard({ label, value, sub, color, to }: { label: string; value: number | string; sub?: string; color: string; to?: string }) {
  const inner = (
    <>
      <p className="text-sm font-medium opacity-75">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </>
  );
  if (to) {
    return <Link to={to} className={`block rounded-xl p-5 hover:opacity-90 transition-opacity ${color}`}>{inner}</Link>;
  }
  return <div className={`rounded-xl p-5 ${color}`}>{inner}</div>;
}

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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart.getTime() + 86400000);

  const today = appointments.filter(
    (a) => a.scheduled_start && new Date(a.scheduled_start) >= todayStart && new Date(a.scheduled_start) < todayEnd
  );
  const redFlagAppts = appointments.filter((a) => a.red_flags && a.red_flags.length > 0);
  const needsFeedback = appointments.filter((a) => a.status === "completed" && !a.feedback_submitted);
  const pendingIntake = appointments.filter((a) => a.status === "intake_complete");
  const newRequests = appointments.filter((a) => a.status === "pending_intake");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {redFlagAppts.length > 0 && (
        <RedFlagBanner flags={redFlagAppts.flatMap((a) => a.red_flags ?? [])} />
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Today" value={today.length} sub="appointments" color="bg-primary-50 text-primary-900" />
        <StatCard label="Needs Review" value={pendingIntake.length} sub="intake complete" color="bg-emerald-50 text-emerald-900" to="/appointments?filter=intake_complete" />
        <StatCard label="Red Flags" value={redFlagAppts.length} sub="require attention" color={redFlagAppts.length > 0 ? "bg-red-50 text-red-900" : "bg-gray-50 text-gray-700"} />
        <StatCard label="Feedback Due" value={needsFeedback.length} sub="completed visits" color={needsFeedback.length > 0 ? "bg-amber-50 text-amber-900" : "bg-gray-50 text-gray-700"} />
      </div>

      {/* New appointment requests awaiting patient intake */}
      {newRequests.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">New Appointment Requests</h2>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
            {newRequests.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="flex items-center justify-between text-sm text-amber-800 hover:text-amber-900"
              >
                <span>{appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}</span>
                <span className="text-amber-600 text-xs">Awaiting intake</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Today's schedule */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Today's Schedule</h2>
        {today.length === 0 ? (
          <div className="bg-gray-50 rounded-xl p-6 text-center text-gray-500 text-sm">
            No appointments scheduled for today.
          </div>
        ) : (
          <div className="space-y-2">
            {today
              .sort((a, b) => new Date(a.scheduled_start!).getTime() - new Date(b.scheduled_start!).getTime())
              .map((appt) => (
                <Link
                  key={appt.id}
                  to={`/appointments/${appt.id}`}
                  className="flex items-center gap-4 bg-white/70 backdrop-blur-sm rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow"
                >
                  <div className="text-sm font-semibold text-primary-700 w-16 shrink-0">
                    {new Date(appt.scheduled_start!).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">
                      {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                    </p>
                    <p className="text-xs text-gray-500">
                      {appt.visit_type === "yearly_checkup" ? "Yearly Checkup" : "Specific Concern"}
                      {appt.scheduler_approved_duration && ` · ${appt.scheduler_approved_duration} min`}
                    </p>
                  </div>
                  <span className={`shrink-0 px-2 py-0.5 text-xs rounded-full ${
                    appt.status === "in_progress" ? "bg-purple-100 text-purple-700" :
                    appt.status === "confirmed" ? "bg-primary-100 text-primary-700" :
                    "bg-gray-100 text-gray-600"
                  }`}>
                    {appt.status.replace(/_/g, " ")}
                  </span>
                </Link>
              ))}
          </div>
        )}
      </section>

      {/* Feedback needed */}
      {needsFeedback.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Feedback Needed</h2>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
            {needsFeedback.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="flex items-center justify-between text-sm text-amber-800 hover:text-amber-900"
              >
                <span>{appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}</span>
                <span className="text-amber-600 text-xs">
                  {appt.scheduled_start && new Date(appt.scheduled_start).toLocaleDateString()}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
