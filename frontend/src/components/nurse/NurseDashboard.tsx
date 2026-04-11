import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppointments } from "../../services/appointments";
import { RedFlagBanner } from "../common/RedFlagBanner";
import type { Appointment } from "../../types";

function StatCard({
  label,
  value,
  sub,
  color,
  to,
}: {
  label: string;
  value: number | string;
  sub?: string;
  color: string;
  to?: string;
}) {
  const inner = (
    <>
      <p className="text-sm font-medium opacity-75">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </>
  );
  if (to) {
    return (
      <Link to={to} className={`block rounded-xl p-5 hover:opacity-90 transition-opacity ${color}`}>
        {inner}
      </Link>
    );
  }
  return <div className={`rounded-xl p-5 ${color}`}>{inner}</div>;
}

const STATUS_LABEL: Record<string, string> = {
  pending_intake: "Pending Intake",
  intake_complete: "Intake Complete",
  scheduled: "Scheduled",
  confirmed: "Confirmed",
  checked_in: "Checked In",
  in_progress: "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No Show",
};

const STATUS_COLOR: Record<string, string> = {
  in_progress: "bg-purple-100 text-purple-700",
  checked_in: "bg-teal-100 text-teal-700",
  confirmed: "bg-primary-100 text-primary-700",
  intake_complete: "bg-emerald-100 text-emerald-700",
  scheduled: "bg-gray-100 text-gray-600",
};

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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart.getTime() + 86400000);

  const today = appointments
    .filter(
      (a) =>
        a.scheduled_start &&
        new Date(a.scheduled_start) >= todayStart &&
        new Date(a.scheduled_start) < todayEnd &&
        a.status !== "completed" &&
        a.status !== "cancelled"
    )
    .sort(
      (a, b) =>
        new Date(a.scheduled_start!).getTime() - new Date(b.scheduled_start!).getTime()
    );

  const redFlagAppts = appointments.filter(
    (a) => a.red_flags && a.red_flags.length > 0 && a.status !== "completed"
  );

  const intakeReady = appointments.filter((a) => a.status === "intake_complete");

  const upcoming = appointments.filter(
    (a) =>
      a.status !== "completed" &&
      a.status !== "cancelled" &&
      !(
        a.scheduled_start &&
        new Date(a.scheduled_start) >= todayStart &&
        new Date(a.scheduled_start) < todayEnd
      )
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Nursing Overview</h1>

      {redFlagAppts.length > 0 && (
        <RedFlagBanner flags={redFlagAppts.flatMap((a) => a.red_flags ?? [])} />
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Today"
          value={today.length}
          sub="appointments"
          color="bg-primary-50 text-primary-900"
        />
        <StatCard
          label="Intake Ready"
          value={intakeReady.length}
          sub="awaiting review"
          color="bg-emerald-50 text-emerald-900"
          to="/appointments?filter=intake_complete"
        />
        <StatCard
          label="Red Flags"
          value={redFlagAppts.length}
          sub="require attention"
          color={
            redFlagAppts.length > 0
              ? "bg-red-50 text-red-900"
              : "bg-gray-50 text-gray-700"
          }
        />
        <StatCard
          label="Upcoming"
          value={upcoming.length}
          sub="not today"
          color="bg-gray-50 text-gray-700"
        />
      </div>

      {/* Red-flag patients — surfaced at top for triage */}
      {redFlagAppts.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
            Red Flag Patients
          </h2>
          <div className="space-y-2">
            {redFlagAppts.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="flex items-center gap-4 bg-white border border-red-100 rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {appt.visit_type === "yearly_checkup"
                      ? "Yearly Checkup"
                      : "Specific Concern"}
                    {appt.scheduled_start &&
                      ` · ${new Date(appt.scheduled_start).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}`}
                  </p>
                  {appt.summary && (
                    <p className="text-xs text-gray-600 mt-1 bg-gray-50 rounded px-2 py-1 truncate">
                      {appt.summary}
                    </p>
                  )}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-1">
                  {appt.red_flags?.map((f) => (
                    <span
                      key={f.id}
                      className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                        f.severity === "emergency"
                          ? "bg-red-200 text-red-800"
                          : f.severity === "urgent"
                          ? "bg-orange-100 text-orange-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {f.severity.toUpperCase()}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Intake-ready queue */}
      {intakeReady.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
            Ready for Review
          </h2>
          <div className="space-y-2">
            {intakeReady.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="flex items-center gap-4 bg-white border border-emerald-100 rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {appt.visit_type === "yearly_checkup"
                      ? "Yearly Checkup"
                      : "Specific Concern"}
                  </p>
                  {appt.summary && (
                    <p className="text-xs text-gray-600 mt-1 bg-gray-50 rounded px-2 py-1 truncate">
                      {appt.summary}
                    </p>
                  )}
                </div>
                <span className="shrink-0 px-2 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-700 font-medium">
                  Intake Complete
                </span>
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
            {today.map((appt) => (
              <Link
                key={appt.id}
                to={`/appointments/${appt.id}`}
                className="flex items-center gap-4 bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow"
              >
                <div className="text-sm font-semibold text-primary-700 w-16 shrink-0">
                  {new Date(appt.scheduled_start!).toLocaleTimeString(undefined, {
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                  </p>
                  <p className="text-xs text-gray-500">
                    {appt.visit_type === "yearly_checkup"
                      ? "Yearly Checkup"
                      : "Specific Concern"}
                    {appt.ai_suggested_duration &&
                      ` · ${appt.ai_suggested_duration} min`}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {appt.red_flags && appt.red_flags.length > 0 && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-medium">
                      RED FLAG
                    </span>
                  )}
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full ${
                      STATUS_COLOR[appt.status] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {STATUS_LABEL[appt.status] ?? appt.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Upcoming (non-today) */}
      {upcoming.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Upcoming</h2>
          <div className="space-y-2">
            {upcoming
              .filter((a) => a.scheduled_start)
              .sort(
                (a, b) =>
                  new Date(a.scheduled_start!).getTime() -
                  new Date(b.scheduled_start!).getTime()
              )
              .slice(0, 10)
              .map((appt) => (
                <Link
                  key={appt.id}
                  to={`/appointments/${appt.id}`}
                  className="flex items-center gap-4 bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow"
                >
                  <div className="text-sm font-semibold text-gray-500 w-24 shrink-0">
                    {new Date(appt.scheduled_start!).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                    <br />
                    <span className="text-xs font-normal">
                      {new Date(appt.scheduled_start!).toLocaleTimeString(undefined, {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">
                      {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                    </p>
                    <p className="text-xs text-gray-500">
                      {appt.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 px-2 py-0.5 text-xs rounded-full ${
                      STATUS_COLOR[appt.status] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {STATUS_LABEL[appt.status] ?? appt.status}
                  </span>
                </Link>
              ))}
          </div>
        </section>
      )}
    </div>
  );
}
