import api, { getAccessToken, setAccessToken } from "./api";
import type { User } from "../types";

interface TokenResponse {
  access_token: string;
}

interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

/**
 * Authenticate with the backend and store the JWT in memory.
 * Returns the user profile fetched after successful login.
 */
export async function login(
  email: string,
  password: string,
): Promise<{ user: User }> {
  const { data: tokenData } = await api.post<TokenResponse>("/auth/login", {
    email,
    password,
  });

  setAccessToken(tokenData.access_token);

  const user = await getCurrentUser();
  if (!user) {
    throw new Error("Failed to fetch user profile after login");
  }

  return { user };
}

/**
 * End the session. Clears the in-memory token.
 */
export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } finally {
    setAccessToken(null);
  }
}

/**
 * Fetch the currently authenticated user from the /auth/me endpoint.
 * Returns null when no valid token exists.
 */
export async function getCurrentUser(): Promise<User | null> {
  if (!getAccessToken()) return null;

  try {
    const { data } = await api.get<UserResponse>("/auth/me");
    return {
      id: data.id,
      email: data.email,
      first_name: data.full_name.split(" ")[0] ?? "",
      last_name: data.full_name.split(" ").slice(1).join(" "),
      role: data.role as User["role"],
      created_at: "",
      updated_at: "",
    };
  } catch {
    return null;
  }
}
