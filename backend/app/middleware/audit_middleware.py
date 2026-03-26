"""FastAPI middleware that logs every HTTP request in the audit trail.

Captures method, path, authenticated user (from JWT), client IP, user agent,
and response status code.  Failed access attempts (403) are logged with a
denial reason.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.audit_service import AuditLog, AuditService

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs every inbound request and its outcome to the audit log table."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()

        # Extract caller identity from JWT (best-effort; unauthenticated
        # requests are logged with user_id=None).
        user_id = self._extract_user_id(request)
        ip_address = self._client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Let the actual endpoint run
        response: Response = await call_next(request)

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)

        # Determine success and denial reason
        success = response.status_code < 400
        denial_reason: Optional[str] = None
        if response.status_code == 403:
            denial_reason = "Forbidden – insufficient permissions"
        elif response.status_code == 401:
            denial_reason = "Unauthorized – invalid or missing credentials"

        # Persist audit entry in its own short-lived session so it is
        # committed independently of the request's transactional scope.
        try:
            async with async_session_factory() as db:
                audit = AuditService(db)
                await audit.log_access(
                    user_id=user_id or uuid.UUID(int=0),
                    patient_id=uuid.UUID(int=0),  # not known at middleware level
                    resource_type="http",
                    resource_id=uuid.UUID(int=0),
                    action=f"{request.method} {request.url.path}",
                    success=success,
                    details={
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    denial_reason=denial_reason,
                )
                await db.commit()
        except Exception:
            # Audit logging must never break the request.
            logger.exception("Failed to write audit log for %s %s", request.method, request.url.path)

        return response

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_user_id(request: Request) -> Optional[uuid.UUID]:
        """Best-effort extraction of user_id from the Authorization header."""
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
            if sub:
                return uuid.UUID(str(sub))
        except (JWTError, ValueError):
            pass
        return None

    @staticmethod
    def _client_ip(request: Request) -> str:
        """Return the client IP, respecting X-Forwarded-For if present."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
