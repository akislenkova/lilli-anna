import { useAuth } from "../../context/AuthContext";
import type { Role } from "../../types";

interface Props {
  /** Roles that are allowed to see the children. */
  allowed: Role[];
  /** Optional fallback rendered when the user's role is not in the allowed list. */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Conditionally renders children based on the current user's role.
 * Use this inside pages/components to show or hide sections.
 */
export default function RoleGate({ allowed, fallback = null, children }: Props) {
  const { user } = useAuth();

  if (!user || !allowed.includes(user.role)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
