import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import ProtectedRoute from "./components/common/ProtectedRoute";
import Layout from "./components/common/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IntakePage } from "./pages/IntakePage";
import { AppointmentDetailPage } from "./pages/AppointmentDetailPage";

function LayoutWrapper() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
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
        <Route path="appointments/:id" element={<AppointmentDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
