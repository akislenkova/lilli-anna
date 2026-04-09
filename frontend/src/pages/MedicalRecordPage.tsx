import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMyProfile, getMyRecords, getMyMedications } from "../services/patients";
import type { PatientProfile } from "../services/patients";
import type { Appointment } from "../types";

export function MedicalRecordPage() {
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [records, setRecords] = useState<Appointment[]>([]);
  const [medications, setMedications] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMyProfile(), getMyRecords(), getMyMedications()])
      .then(([prof, recs, meds]) => {
        setProfile(prof);
        setRecords(recs);
        setMedications(meds);
      })
      .catch(() => setError("Unable to load your medical record. Please try again."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-12 bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My Medical Record</h1>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          ← Back to Dashboard
        </Link>
      </div>

      {/* Profile */}
      {profile && (
        <section className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Profile</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Date of Birth</p>
              <p className="font-medium text-gray-900 mt-0.5">
                {new Date(profile.date_of_birth + "T00:00:00").toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            </div>
            <div>
              <p className="text-gray-500">Language Preference</p>
              <p className="font-medium text-gray-900 mt-0.5 uppercase">
                {profile.language_preference}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Current medications */}
      <section className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-800">Current Medications</h2>
        {medications.length === 0 ? (
          <p className="text-sm text-gray-500">No medications on file.</p>
        ) : (
          <ul className="space-y-2">
            {medications.map((med, i) => (
              <li key={i} className="flex items-center gap-3 text-sm text-gray-800">
                <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />
                {med}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Visit history */}
      <section className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-800">Visit History</h2>
        {records.length === 0 ? (
          <p className="text-sm text-gray-500">No past visits on record.</p>
        ) : (
          <div className="space-y-3">
            {records.map((rec) => (
              <Link
                key={rec.id}
                to={`/appointments/${rec.id}`}
                className="block border border-gray-100 rounded-lg p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900 text-sm">
                      {rec.visit_type === "yearly_checkup"
                        ? "Yearly Checkup"
                        : "Specific Concern"}
                    </p>
                    {rec.summary && (
                      <p className="text-xs text-gray-500 mt-1 max-w-sm truncate">{rec.summary}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-xs text-gray-500">
                      {rec.scheduled_start
                        ? new Date(rec.scheduled_start).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })
                        : new Date(rec.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                    </p>
                    <span
                      className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full font-medium ${
                        rec.status === "completed"
                          ? "bg-gray-100 text-gray-600"
                          : "bg-red-100 text-red-600"
                      }`}
                    >
                      {rec.status === "completed" ? "Completed" : "Cancelled"}
                    </span>
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
