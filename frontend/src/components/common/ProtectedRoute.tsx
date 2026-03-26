import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import type { Role } from "../../types";

interface Props {
  children: React.ReactNode;
  /** If provided, only users with one of these roles may access the route. */
  allowedRoles?: Role[];
}

export default function ProtectedRoute({ children, allowedRoles }: Props) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 text-center">
        <div className="text-6xl font-bold text-primary-300">403</div>
        <h1 className="text-2xl font-semibold text-gray-800">
          Access Denied
        </h1>
        <p className="max-w-md text-gray-600">
          You do not have permission to view this page. Please contact your
          administrator if you believe this is an error.
        </p>
        <a
          href="/"
          className="mt-4 rounded-lg bg-primary-600 px-6 py-2 text-white hover:bg-primary-700"
        >
          Go to Dashboard
        </a>
      </div>
    );
  }

  return <>{children}</>;
}
