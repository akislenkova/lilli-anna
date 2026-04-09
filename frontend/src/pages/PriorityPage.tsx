import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPriorityRanking } from "../services/appointments";

interface PriorityPatient {
  appointment_id: string;
  patient_id: string;
  urgency_score: number;
  reason: string[];
  visit_type: string;
  is_new_patient: boolean;
  created_at: string;
}

export function PriorityPage() {
  const [patients, setPatients] = useState<PriorityPatient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPriorityRanking()
      .then((data) => {
        const d = data as { patients: PriorityPatient[] };
        setPatients(d.patients ?? []);
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
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Priority Queue</h1>
      <p className="text-sm text-gray-500">
        Patients ranked by urgency — schedule the highest scores first.
      </p>

      {patients.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-8 text-center text-gray-500">
          No pending appointments to prioritize.
        </div>
      ) : (
        <div className="space-y-3">
          {patients.map((p, i) => (
            <Link
              key={p.appointment_id}
              to={`/appointments/${p.appointment_id}`}
              className="block bg-white rounded-xl shadow p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 font-bold text-sm">
                  #{i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-gray-900">
                      Patient #{p.patient_id.slice(0, 8)}
                    </p>
                    {p.is_new_patient && (
                      <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">
                        New Patient
                      </span>
                    )}
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                      {p.visit_type === "yearly_checkup" ? "Yearly Checkup" : "Specific Concern"}
                    </span>
                  </div>
                  {p.reason.length > 0 && (
                    <p className="text-sm text-gray-500 mt-1">{p.reason.join(" · ")}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-0.5">
                    Waiting since {new Date(p.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-400">Urgency</p>
                  <p className={`text-lg font-bold ${
                    p.urgency_score >= 0.7 ? "text-red-600" :
                    p.urgency_score >= 0.4 ? "text-amber-600" : "text-green-600"
                  }`}>
                    {Math.round(p.urgency_score * 100)}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
