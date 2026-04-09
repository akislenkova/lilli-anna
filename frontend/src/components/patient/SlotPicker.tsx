import { useEffect, useState } from "react";
import { getAvailableSlots, updateAppointment } from "../../services/appointments";

interface Slot {
  start: string;
  end: string;
  label: string;
}

interface Props {
  appointmentId: string;
  duration?: number;
  onBooked: (start: string) => void;
}

function nextDays(n: number): string[] {
  const days: string[] = [];
  const d = new Date();
  d.setDate(d.getDate() + 1); // start tomorrow
  while (days.length < n) {
    if (d.getDay() !== 0 && d.getDay() !== 6) {
      days.push(d.toISOString().slice(0, 10));
    }
    d.setDate(d.getDate() + 1);
  }
  return days;
}

function formatDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function SlotPicker({ appointmentId, duration, onBooked }: Props) {
  const days = nextDays(7);
  const [selectedDay, setSelectedDay] = useState(days[0] ?? "");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<Slot | null>(null);

  useEffect(() => {
    if (!selectedDay) return;
    setLoading(true);
    setSelected(null);
    getAvailableSlots(selectedDay, duration)
      .then(setSlots)
      .catch(() => setSlots([]))
      .finally(() => setLoading(false));
  }, [selectedDay, duration]);

  const handleBook = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await updateAppointment(appointmentId, { scheduled_start: selected.start });
      onBooked(selected.start);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Day selector */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {days.map((day) => (
          <button
            key={day}
            onClick={() => setSelectedDay(day)}
            className={`shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selectedDay === day
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {formatDate(day)}
          </button>
        ))}
      </div>

      {/* Slots */}
      {loading ? (
        <div className="flex justify-center py-6">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
        </div>
      ) : slots.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">
          No availability on this day. Try another day.
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {slots.map((slot) => (
            <button
              key={slot.start}
              onClick={() => setSelected(slot)}
              className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                selected?.start === slot.start
                  ? "bg-blue-600 text-white"
                  : "bg-gray-50 text-gray-700 border border-gray-200 hover:border-blue-400 hover:text-blue-600"
              }`}
            >
              {slot.label}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="flex items-center justify-between bg-blue-50 rounded-lg p-3">
          <p className="text-sm text-blue-800 font-medium">
            {formatDate(selectedDay)} at {selected.label}
          </p>
          <button
            onClick={handleBook}
            disabled={saving}
            className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Request this time"}
          </button>
        </div>
      )}
    </div>
  );
}
