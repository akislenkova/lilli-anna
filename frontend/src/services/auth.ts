import api from "./api";
import type { User } from "../types";

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  user: User;
  message: string;
}

/**
 * Authenticate with the backend. The server will set an HttpOnly cookie
 * for the session -- no tokens are stored client-side.
 */
export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/auth/login", {
    email,
    password,
  });
  return data;
}

/**
 * End the session. The backend clears the HttpOnly auth cookie.
 */
export async function logout(): Promise<void> {
  await api.post("/auth/logout");
}

/**
 * Fetch the currently authenticated user from the session cookie.
 * Returns null when the session is invalid or expired.
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const { data } = await api.get<{ user: User }>("/auth/me");
    return data.user;
  } catch {
    return null;
  }
}

/**
 * Quick check -- hits a lightweight endpoint to see if the cookie is valid.
 */
export async function isAuthenticated(): Promise<boolean> {
  try {
    await api.get("/auth/me");
    return true;
  } catch {
    return false;
  }
}
