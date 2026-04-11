import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/common/ProtectedRoute";
import Layout from "./components/common/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IntakePage } from "./pages/IntakePage";
import { AppointmentDetailPage } from "./pages/AppointmentDetailPage";
import { AppointmentsPage } from "./pages/AppointmentsPage";
import { ConflictsPage } from "./pages/ConflictsPage";
import { PriorityPage } from "./pages/PriorityPage";
import { MedicalRecordPage } from "./pages/MedicalRecordPage";
import { MessagesPage } from "./pages/MessagesPage";
import { EpicCallbackPage } from "./pages/EpicCallbackPage";

function LayoutWrapper() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/epic-callback" element={<EpicCallbackPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <LayoutWrapper />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route
            path="intake"
            element={
              <ProtectedRoute allowedRoles={["patient"]}>
                <IntakePage />
              </ProtectedRoute>
            }
          />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="appointments/:id" element={<AppointmentDetailPage />} />
          <Route path="conflicts" element={<ConflictsPage />} />
          <Route path="priority" element={<PriorityPage />} />
          <Route
            path="my-record"
            element={
              <ProtectedRoute allowedRoles={["patient"]}>
                <MedicalRecordPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="messages"
            element={
              <ProtectedRoute allowedRoles={["scheduler", "nurse", "physician"]}>
                <MessagesPage />
              </ProtectedRoute>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
