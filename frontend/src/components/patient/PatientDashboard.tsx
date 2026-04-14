import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { cancelAppointment, listAppointments } from "../../services/appointments";
import { SlotPicker } from "./SlotPicker";
import type { Appointment, AppointmentStatus } from "../../types";

/* ── Status badge styling ── */
const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  pending_intake: { bg: "bg-amber-100", text: "text-amber-700", label: "Intake Pending" },
  intake_complete: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Intake Complete" },
  scheduled: { bg: "bg-primary-100", text: "text-primary-700", label: "Scheduled" },
  confirmed: { bg: "bg-primary-100", text: "text-primary-700", label: "Confirmed" },
  checked_in: { bg: "bg-indigo-100", text: "text-indigo-700", label: "Checked In" },
  in_progress: { bg: "bg-purple-100", text: "text-purple-700", label: "In Progress" },
  completed: { bg: "bg-gray-100", text: "text-gray-600", label: "Completed" },
  cancelled: { bg: "bg-red-100", text: "text-red-600", label: "Cancelled" },
  no_show: { bg: "bg-gray-100", text: "text-gray-500", label: "No Show" },
};

function StatusBadge({ status }: { status: AppointmentStatus }) {
  const s = STATUS_STYLES[status] ?? { bg: "bg-gray-100", text: "text-gray-600", label: status };
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

/* ── Status icon for active appointments ── */
function StatusIcon({ status }: { status: AppointmentStatus }) {
  if (status === "pending_intake") {
    return (
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100">
        <svg className="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
    );
  }
  if (status === "intake_complete") {
    return (
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-100">
        <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
    );
  }
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-100">
      <svg className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    </div>
  );
}

/* ── Active statuses (not yet scheduled / awaiting scheduling) ── */
const ACTIVE_STATUSES = new Set<AppointmentStatus>(["pending_intake", "intake_complete"]);

/* ── Past / done statuses ── */
const PAST_STATUSES = new Set<AppointmentStatus>(["completed", "cancelled", "no_show"]);

export function PatientDashboard() {
  const [active, setActive] = useState<Appointment[]>([]);
  const [upcoming, setUpcoming] = useState<Appointment[]>([]);
  const [slotPickerOpen, setSlotPickerOpen] = useState<string | null>(null);
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [past, setPast] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAppointments({})
      .then((data) => {
        const now = new Date();
        const activeList: Appointment[] = [];
        const upcomingList: Appointment[] = [];
        const pastList: Appointment[] = [];

        for (const a of data) {
          if (a.status === "cancelled") {
            pastList.push(a);
          } else if (ACTIVE_STATUSES.has(a.status)) {
            // Pending intake or intake complete — no schedule yet
            activeList.push(a);
          } else if (PAST_STATUSES.has(a.status)) {
            pastList.push(a);
          } else if (a.scheduled_start && new Date(a.scheduled_start) < now) {
            pastList.push(a);
          } else {
            // Scheduled, confirmed, checked_in, in_progress with future date
            upcomingList.push(a);
          }
        }

        setActive(activeList);
        setUpcoming(upcomingList);
        setPast(pastList);
      })
      .catch(() => {
        // API may not have appointments yet
      })
      .finally(() => setLoading(false));
  }, []);

  const handleDeleteActive = async (id: string) => {
    if (!window.confirm("Remove this intake? You can start a new one at any time.")) return;
    setDeleteError(null);
    try {
      await cancelAppointment(id);
      setActive((prev) => prev.filter((a) => a.id !== id));
    } catch {
      setDeleteError("Failed to remove the intake. Please try again.");
    }
  };

  const handleCancel = async (id: string) => {
    if (!window.confirm("Are you sure you want to cancel this appointment?")) return;
    setCancelError(null);
    try {
      await cancelAppointment(id);
      const cancelled = upcoming.find((a) => a.id === id);
      setUpcoming((prev) => prev.filter((a) => a.id !== id));
      if (cancelled) setPast((prev) => [{ ...cancelled, status: "cancelled" as AppointmentStatus }, ...prev]);
    } catch {
      setCancelError("Failed to cancel the appointment. Please try again.");
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My Dashboard</h1>
        <div className="flex items-center gap-3">
          <Link
            to="/my-record"
            className="text-sm text-gray-600 border border-gray-300 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            My Medical Record
          </Link>
          <Link
            to="/intake"
            className="bg-primary-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors"
          >
            Schedule New Visit
          </Link>
        </div>
      </div>

      {/* ── Active / In-Progress Appointments ── */}
      {active.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Active
          </h2>

          {deleteError && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {deleteError}
            </div>
          )}

          <div className="space-y-3">
            {active.map((appt) => (
              <div key={appt.id} className="rounded-xl bg-white shadow-sm hover:shadow-md transition-shadow">
                <Link
                  to={appt.status === "pending_intake" ? `/intake?appointmentId=${appt.id}` : `/appointments/${appt.id}`}
                  className="block"
                >
                  <div className="flex items-center gap-4 p-4">
                    <StatusIcon status={appt.status} />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900">
                        {appt.visit_type === "yearly_checkup"
                          ? "Yearly Checkup"
                          : "Specific Concern"}
                      </p>
                      <p className="text-sm text-gray-500">
                        {appt.status === "pending_intake"
                          ? "Complete your intake to continue"
                          : "Awaiting scheduling — a coordinator will reach out soon"}
                      </p>
                      <p className="mt-0.5 text-xs text-gray-400">
                        Created {new Date(appt.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </p>
                    </div>
                    <StatusBadge status={appt.status} />
                  </div>
                </Link>

                {/* Progress indicator / slot picker / delete */}
                {appt.status === "pending_intake" && (
                  <div className="border-t border-gray-100 px-4 py-2.5 flex items-center gap-4">
                    <div className="flex items-center gap-2 flex-1">
                      <div className="h-1.5 flex-1 rounded-full bg-gray-100">
                        <div className="h-1.5 w-1/4 rounded-full bg-amber-400" />
                      </div>
                      <span className="text-xs text-amber-600 font-medium">Intake needed</span>
                    </div>
                    <button
                      onClick={() => handleDeleteActive(appt.id)}
                      className="text-xs font-medium text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
                  </div>
                )}
                {appt.status === "intake_complete" && (
                  <div className="border-t border-gray-100 px-4 py-3">
                    {appt.scheduled_start ? (
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-emerald-600 font-medium">
                          Requested: {new Date(appt.scheduled_start).toLocaleString()} — awaiting confirmation
                        </p>
                        <button
                          onClick={() => handleDeleteActive(appt.id)}
                          className="text-xs font-medium text-red-500 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    ) : slotPickerOpen === appt.id ? (
                      <div onClick={(e) => e.preventDefault()}>
                        <SlotPicker
                          appointmentId={appt.id}
                          duration={appt.ai_suggested_duration ?? 30}
                          onBooked={(start) => {
                            setActive((prev) =>
                              prev.map((a) =>
                                a.id === appt.id ? { ...a, scheduled_start: start } : a
                              )
                            );
                            setSlotPickerOpen(null);
                          }}
                        />
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            setSlotPickerOpen(appt.id);
                          }}
                          className="text-sm text-primary-600 font-medium hover:text-primary-800"
                        >
                          Pick a time that works for you →
                        </button>
                        <button
                          onClick={() => handleDeleteActive(appt.id)}
                          className="text-xs font-medium text-red-500 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Upcoming Appointments ── */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Upcoming Appointments
        </h2>

        {cancelError && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {cancelError}
          </div>
        )}

        {upcoming.length === 0 ? (
          <div className="bg-gray-50 rounded-lg p-6 text-center text-gray-500">
            No upcoming appointments.{" "}
            <Link to="/intake" className="text-primary-600 hover:underline">
              Schedule one now
            </Link>
            .
          </div>
        ) : (
          <div className="space-y-3">
            {upcoming.map((appt) => (
              <div key={appt.id} className="bg-white/70 backdrop-blur-sm rounded-xl shadow-sm hover:shadow-md transition-shadow">
                <Link
                  to={`/appointments/${appt.id}`}
                  className="block p-4"
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
                    <StatusBadge status={appt.status} />
                  </div>
                </Link>

                {/* Reschedule / Cancel actions */}
                <div className="border-t border-gray-100 px-4 py-2.5">
                  {reschedulingId === appt.id ? (
                    <div className="py-2">
                      <SlotPicker
                        appointmentId={appt.id}
                        duration={appt.ai_suggested_duration ?? 30}
                        onBooked={(start) => {
                          setUpcoming((prev) =>
                            prev.map((a) =>
                              a.id === appt.id ? { ...a, scheduled_start: start } : a
                            )
                          );
                          setReschedulingId(null);
                        }}
                      />
                      <button
                        onClick={() => setReschedulingId(null)}
                        className="mt-2 text-xs text-gray-500 hover:text-gray-700"
                      >
                        Never mind
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-4">
                      <button
                        onClick={() => setReschedulingId(appt.id)}
                        className="text-sm font-medium text-primary-600 hover:text-primary-800"
                      >
                        Reschedule
                      </button>
                      <button
                        onClick={() => handleCancel(appt.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Cancel appointment
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Past Appointments ── */}
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
                className="block bg-white/70 backdrop-blur-sm rounded-xl shadow-sm p-4 hover:shadow-md transition-shadow opacity-75"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-700">
                      {appt.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                    </p>
                    <p className="text-sm text-gray-500">
                      {appt.scheduled_start
                        ? new Date(appt.scheduled_start).toLocaleDateString()
                        : new Date(appt.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <StatusBadge status={appt.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
