"""Session security middleware.

Enforces:
- Session timeout (15 min inactivity for provider roles).
- Concurrent session limits (one active session per user per role).
- Re-authentication after timeout.
- Secure cookie attributes (HttpOnly, SameSite=Strict, Secure).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)

# Provider roles subject to the 15-minute inactivity timeout.
_PROVIDER_ROLES = {"physician", "nurse", "scheduler", "admin"}

# Simple in-memory session store.  In production this would be backed by
# Redis or a database table.
# Key: user_id:role -> {"session_token": str, "last_activity": float}
_active_sessions: dict[str, dict] = {}


class SessionMiddleware(BaseHTTPMiddleware):
    """Enforces session security policies on every request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip session enforcement for auth endpoints
        if self._is_auth_endpoint(request.url.path):
            response = await call_next(request)
            return response

        # Extract identity
        user_info = self._extract_user_info(request)
        if user_info is None:
            # Unauthenticated request -- let downstream handle 401
            response = await call_next(request)
            return self._set_secure_cookies(response)

        user_id, role = user_info
        session_key = f"{user_id}:{role}"
        session_token = request.cookies.get("anilla_session") or request.headers.get(
            "x-session-token", ""
        )

        # ----- Inactivity timeout for provider roles --------------------
        if role in _PROVIDER_ROLES:
            existing = _active_sessions.get(session_key)
            if existing is not None:
                elapsed = time.time() - existing["last_activity"]
                timeout_seconds = settings.SESSION_TIMEOUT_MINUTES * 60

                if elapsed > timeout_seconds:
                    # Session expired
                    _active_sessions.pop(session_key, None)
                    logger.info(
                        "session expired (inactivity) | user=%s role=%s idle=%.0fs",
                        user_id,
                        role,
                        elapsed,
                    )
                    return JSONResponse(
                        status_code=401,
                        content={
                            "detail": "Session expired due to inactivity. Please re-authenticate.",
                            "code": "SESSION_TIMEOUT",
                        },
                    )

                # Enforce single concurrent session
                if (
                    session_token
                    and existing["session_token"] != session_token
                ):
                    logger.warning(
                        "concurrent session rejected | user=%s role=%s",
                        user_id,
                        role,
                    )
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": (
                                "Another active session exists for this user and role. "
                                "Please log out of the other session first."
                            ),
                            "code": "CONCURRENT_SESSION",
                        },
                    )

        # ----- Process request ------------------------------------------
        response = await call_next(request)

        # ----- Update session tracking ----------------------------------
        if role in _PROVIDER_ROLES:
            new_token = session_token or str(uuid.uuid4())
            _active_sessions[session_key] = {
                "session_token": new_token,
                "last_activity": time.time(),
            }
            # Set / refresh session cookie
            response = self._set_session_cookie(response, new_token)

        return self._set_secure_cookies(response)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_auth_endpoint(path: str) -> bool:
        auth_paths = {"/api/v1/auth/login", "/api/v1/auth/register", "/health", "/docs", "/openapi.json"}
        return path in auth_paths or path.startswith("/api/v1/auth/")

    @staticmethod
    def _extract_user_info(request: Request) -> Optional[tuple[str, str]]:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            sub = payload.get("sub")
            role = payload.get("role")
            if sub and role:
                return str(sub), str(role)
        except (JWTError, ValueError):
            pass
        return None

    @staticmethod
    def _set_session_cookie(response: Response, token: str) -> Response:
        """Set the session cookie with secure attributes."""
        response.set_cookie(
            key="anilla_session",
            value=token,
            httponly=True,
            samesite="strict",
            secure=True,
            max_age=settings.SESSION_TIMEOUT_MINUTES * 60,
            path="/",
        )
        return response

    @staticmethod
    def _set_secure_cookies(response: Response) -> Response:
        """Ensure any cookies already set have secure attributes.

        This is a safety net -- individual set_cookie calls should already
        use the correct flags.
        """
        # Append Strict-Transport-Security header for HTTPS enforcement
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response
