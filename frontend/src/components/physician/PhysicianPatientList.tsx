import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listAppointments } from "../../services/appointments";
import type { Appointment } from "../../types";

const STATUS_FILTERS = [
  { key: "", label: "All" },
  { key: "pending_intake", label: "Pending Intake" },
  { key: "intake_complete", label: "Ready to Review" },
  { key: "scheduled", label: "Scheduled" },
  { key: "completed", label: "Completed" },
];

const STATUS_STYLES: Record<string, string> = {
  pending_intake: "bg-amber-100 text-amber-700",
  intake_complete: "bg-emerald-100 text-emerald-700",
  scheduled: "bg-primary-100 text-primary-700",
  confirmed: "bg-primary-100 text-primary-700",
  in_progress: "bg-purple-100 text-purple-700",
  completed: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-600",
};

export function PhysicianPatientList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState(searchParams.get("filter") ?? "");

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

  const filtered = filter ? appointments.filter((a) => a.status === filter) : appointments;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My Patients</h1>
        <span className="text-sm text-gray-500">{filtered.length} appointment{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => {
              setFilter(f.key);
              if (f.key) setSearchParams({ filter: f.key });
              else setSearchParams({});
            }}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === f.key
                ? "bg-primary-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-8 text-center text-gray-500">
          No patients in this category.
        </div>
      ) : filter === "intake_complete" ? (
        /* Checklist view for needs-review */
        <div className="bg-white rounded-xl shadow-sm divide-y divide-gray-100">
          {filtered.map((appt) => (
            <Link
              key={appt.id}
              to={`/appointments/${appt.id}`}
              className="flex items-center gap-4 px-5 py-4 hover:bg-emerald-50 transition-colors"
            >
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-emerald-400">
                <div className="h-2 w-2 rounded-full bg-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900">
                  {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                </p>
                <p className="text-sm text-gray-500">
                  {appt.visit_type === "yearly_checkup" ? "Yearly Checkup" : "Specific Concern"}
                  {appt.initial_reason && ` · ${appt.initial_reason}`}
                </p>
              </div>
              <div className="shrink-0 text-right">
                {appt.ai_suggested_duration && (
                  <p className="text-sm font-medium text-primary-700">{appt.ai_suggested_duration} min</p>
                )}
                <p className="text-xs text-emerald-600 font-medium">Review intake →</p>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((appt) => (
            <Link
              key={appt.id}
              to={`/appointments/${appt.id}`}
              className="block bg-white rounded-xl shadow-sm p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900">
                    {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                  </p>
                  <p className="text-sm text-gray-500 mt-0.5">
                    {appt.visit_type === "yearly_checkup" ? "Yearly Checkup" : "Specific Concern"}
                  </p>
                  <p className="text-sm text-gray-400 mt-0.5">
                    {appt.scheduled_start
                      ? new Date(appt.scheduled_start).toLocaleString(undefined, {
                          weekday: "short", month: "short", day: "numeric",
                          hour: "numeric", minute: "2-digit",
                        })
                      : "Not yet scheduled"}
                  </p>
                </div>
                <div className="shrink-0 text-right space-y-1">
                  <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${STATUS_STYLES[appt.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {appt.status.replace(/_/g, " ")}
                  </span>
                  {appt.scheduler_approved_duration && (
                    <p className="text-xs text-gray-500">{appt.scheduler_approved_duration} min</p>
                  )}
                  {appt.ai_suggested_duration && !appt.scheduler_approved_duration && (
                    <p className="text-xs text-primary-600">AI: {appt.ai_suggested_duration} min</p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
