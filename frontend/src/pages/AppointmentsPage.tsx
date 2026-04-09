import { useAuth } from "../context/AuthContext";
import { SchedulerDashboard } from "../components/scheduler/SchedulerDashboard";
import { PhysicianDashboard } from "../components/physician/PhysicianDashboard";
import { PatientDashboard } from "../components/patient/PatientDashboard";
import { NurseDashboard } from "../components/nurse/NurseDashboard";

export function AppointmentsPage() {
  const { user } = useAuth();
  if (!user) return null;

  switch (user.role) {
    case "scheduler": return <SchedulerDashboard />;
    case "physician": return <PhysicianDashboard />;
    case "patient": return <PatientDashboard />;
    case "nurse": return <NurseDashboard />;
    default: return null;
  }
}
