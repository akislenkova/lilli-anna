import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { Layout } from "./components/common/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IntakePage } from "./pages/IntakePage";
import { AppointmentDetailPage } from "./pages/AppointmentDetailPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route
            path="intake"
            element={
              <ProtectedRoute requiredRole="patient">
                <IntakePage />
              </ProtectedRoute>
            }
          />
          <Route path="appointments/:id" element={<AppointmentDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
