import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppointments, approveDuration, updateAppointment } from "../../services/appointments";
import type { Appointment } from "../../types";

type CalendarView = "today" | "week" | "month";

export function SchedulerDashboard() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [view, setView] = useState<CalendarView>("today");
  const [loading, setLoading] = useState(true);
  const [approveId, setApproveId] = useState<string | null>(null);
  const [approveTime, setApproveTime] = useState("");
  const [approveDurationVal, setApproveDurationVal] = useState("");

  useEffect(() => {
    setLoading(true);
    listAppointments({ view }).then((data) => {
      setAppointments(data);
      setLoading(false);
    });
  }, [view]);

  const handleApprove = async (apptId: string) => {
    if (!approveTime || !approveDurationVal) return;
    const duration = parseInt(approveDurationVal);
    const start = new Date(approveTime).toISOString();
    await approveDuration(apptId, duration);
    await updateAppointment(apptId, { scheduled_start: start });
    setAppointments((prev) =>
      prev.map((a) =>
        a.id === apptId
          ? { ...a, scheduler_approved_duration: duration, scheduled_start: start, status: "scheduled" }
          : a
      )
    );
    setApproveId(null);
    setApproveTime("");
    setApproveDurationVal("");
  };

  const viewButtons: { key: CalendarView; label: string }[] = [
    { key: "today", label: "Today" },
    { key: "week", label: "This Week" },
    { key: "month", label: "Monthly" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Scheduling Dashboard</h1>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {viewButtons.map((v) => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                view === v.key ? "bg-white shadow text-blue-600" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : appointments.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
          No appointments for this period.
        </div>
      ) : (
        <div className="space-y-4">
          {appointments.map((appt) => {
            const hasConflict =
              appt.ai_suggested_duration &&
              appt.scheduler_approved_duration &&
              appt.ai_suggested_duration > appt.scheduler_approved_duration;

            return (
              <div
                key={appt.id}
                className={`bg-white rounded-xl shadow p-5 ${
                  hasConflict ? "border-l-4 border-amber-500" : ""
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <Link
                      to={`/appointments/${appt.id}`}
                      className="text-lg font-medium text-gray-900 hover:text-blue-600"
                    >
                      {appt.patient_name ?? `Patient #${appt.patient_id?.slice(0, 8)}`}
                    </Link>
                    <p className="text-sm text-gray-500 mt-1">
                      {appt.visit_type === "yearly_checkup" ? "Yearly Checkup" : "Specific Concern"}
                      {appt.scheduled_start &&
                        ` — ${new Date(appt.scheduled_start).toLocaleString()}`}
                    </p>
                    {appt.initial_reason && (
                      <p className="text-sm text-gray-700 mt-2 bg-gray-50 rounded p-2">
                        {appt.initial_reason}
                      </p>
                    )}
                  </div>

                  <div className="text-right ml-4">
                    {appt.ai_suggested_duration && (
                      <div className="text-sm">
                        <span className="text-gray-500">AI suggests: </span>
                        <span className="font-semibold text-blue-700">
                          {appt.ai_suggested_duration} min
                        </span>
                        {appt.ai_confidence != null && (
                          <span className="text-gray-400 text-xs ml-1">
                            ({Math.round(appt.ai_confidence * 100)}%)
                          </span>
                        )}
                      </div>
                    )}
                    {appt.ai_duration_range_min && appt.ai_duration_range_max && (
                      <p className="text-xs text-gray-400">
                        Range: {appt.ai_duration_range_min}–{appt.ai_duration_range_max} min
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100">
                  {!appt.scheduler_approved_duration ? (
                    <button
                      onClick={() => {
                        setApproveId(approveId === appt.id ? null : appt.id);
                        setApproveDurationVal(String(appt.ai_suggested_duration ?? ""));
                      }}
                      className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700"
                    >
                      Schedule &amp; Approve
                    </button>
                  ) : (
                    <span className="text-green-600 text-sm font-medium">
                      Approved: {appt.scheduler_approved_duration} min
                      {appt.scheduled_start && (
                        <span className="text-gray-500 font-normal ml-2">
                          — {new Date(appt.scheduled_start).toLocaleString()}
                        </span>
                      )}
                    </span>
                  )}
                </div>

                {approveId === appt.id && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg flex items-end gap-3 flex-wrap">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Date &amp; Time</label>
                      <input
                        type="datetime-local"
                        value={approveTime}
                        onChange={(e) => setApproveTime(e.target.value)}
                        className="px-3 py-2 border rounded-lg text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Duration (min)</label>
                      <input
                        type="number"
                        min={5}
                        max={120}
                        step={5}
                        value={approveDurationVal}
                        onChange={(e) => setApproveDurationVal(e.target.value)}
                        className="w-24 px-3 py-2 border rounded-lg text-sm"
                      />
                    </div>
                    <button
                      onClick={() => handleApprove(appt.id)}
                      disabled={!approveTime || !approveDurationVal}
                      className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                    >
                      Confirm
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
