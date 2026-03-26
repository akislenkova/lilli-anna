import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Role, User } from "../types";
import * as authService from "../services/auth";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isPatient: () => boolean;
  isScheduler: () => boolean;
  isNurse: () => boolean;
  isPhysician: () => boolean;
  isAdmin: () => boolean;
  hasRole: (role: Role) => boolean;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check if we already have a valid session cookie
  useEffect(() => {
    let cancelled = false;
    authService.getCurrentUser().then((u) => {
      if (!cancelled) {
        setUser(u);
        setIsLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { user: loggedIn } = await authService.login(email, password);
    setUser(loggedIn);
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (role: Role) => user?.role === role,
    [user],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
      isPatient: () => hasRole("patient"),
      isScheduler: () => hasRole("scheduler"),
      isNurse: () => hasRole("nurse"),
      isPhysician: () => hasRole("physician"),
      isAdmin: () => hasRole("admin"),
      hasRole,
    }),
    [user, isLoading, login, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
