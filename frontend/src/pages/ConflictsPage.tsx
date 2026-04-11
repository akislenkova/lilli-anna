import { useEffect, useState } from "react";
import { getConflicts } from "../services/appointments";

interface Conflict {
  appointment_id: string;
  conflicting_appointment_id: string;
  conflict_start: string;
  conflict_end: string;
  suggested_alternative_start?: string;
}

export function ConflictsPage() {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getConflicts()
      .then((data) => setConflicts(data as Conflict[]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Scheduling Conflicts</h1>

      {conflicts.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center">
          <p className="text-green-700 font-medium">No scheduling conflicts detected.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {conflicts.map((c, i) => (
            <div key={i} className="bg-white rounded-xl shadow p-5 border-l-4 border-red-500">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-gray-900">Conflict Detected</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {new Date(c.conflict_start).toLocaleString()} –{" "}
                    {new Date(c.conflict_end).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    Appt: {c.appointment_id.slice(0, 8)} &amp;{" "}
                    {c.conflicting_appointment_id.slice(0, 8)}
                  </p>
                </div>
                {c.suggested_alternative_start && (
                  <div className="text-right">
                    <p className="text-xs text-gray-500">Suggested alternative</p>
                    <p className="text-sm font-medium text-primary-700">
                      {new Date(c.suggested_alternative_start).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
