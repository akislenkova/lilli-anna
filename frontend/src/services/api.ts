import axios from "axios";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Request interceptor: attach JWT Bearer token from in-memory storage.
 * Tokens are never persisted to localStorage/sessionStorage per HIPAA.
 */
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

/**
 * Response interceptor: handle authentication and authorization errors.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Only redirect to login if the failed request was an auth check,
      // not a regular data-fetching call that happened to fail.
      const url = error.config?.url ?? "";
      if (url.includes("/auth/me")) {
        accessToken = null;
        if (!window.location.pathname.startsWith("/login")) {
          window.location.href = "/login";
        }
      }
    }

    if (error.response?.status === 403) {
      console.error("Access denied: insufficient permissions");
    }

    return Promise.reject(error);
  },
);

export default api;
