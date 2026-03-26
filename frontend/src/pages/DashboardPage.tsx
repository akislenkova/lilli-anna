import { useAuth } from "../context/AuthContext";
import { SchedulerDashboard } from "../components/scheduler/SchedulerDashboard";
import { PhysicianDashboard } from "../components/physician/PhysicianDashboard";
import { NurseDashboard } from "../components/nurse/NurseDashboard";
import { PatientDashboard } from "../components/patient/PatientDashboard";

export function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  switch (user.role) {
    case "patient":
      return <PatientDashboard />;
    case "scheduler":
      return <SchedulerDashboard />;
    case "physician":
      return <PhysicianDashboard />;
    case "nurse":
      return <NurseDashboard />;
    default:
      return (
        <div className="text-center py-12 text-gray-500">
          Unknown role. Please contact an administrator.
        </div>
      );
  }
}
