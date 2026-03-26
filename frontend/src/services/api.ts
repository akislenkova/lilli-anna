import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Request interceptor: attach CSRF token from the cookie set by the backend.
 * The backend issues HttpOnly auth cookies; we only need to forward the
 * CSRF double-submit token which is stored in a non-HttpOnly cookie.
 */
api.interceptors.request.use((config) => {
  const csrfToken = document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrf_token="))
    ?.split("=")[1];

  if (csrfToken) {
    config.headers["X-CSRF-Token"] = csrfToken;
  }

  return config;
});

/**
 * Response interceptor: handle authentication and authorization errors
 * globally so individual service calls don't need to duplicate this logic.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Session expired or not authenticated -- redirect to login
      // Avoid redirect loops if already on login page
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }

    if (error.response?.status === 403) {
      // Forbidden -- user lacks the required role
      console.error("Access denied: insufficient permissions");
    }

    return Promise.reject(error);
  },
);

export default api;
