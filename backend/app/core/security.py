from __future__ import annotations

import base64
import enum
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------
class Role(str, enum.Enum):
    PATIENT = "patient"
    SCHEDULER = "scheduler"
    NURSE = "nurse"
    PHYSICIAN = "physician"
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------
def _get_db():
    """Placeholder – replaced by the real DB session dependency at app startup."""
    raise NotImplementedError("DB dependency not wired")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
):
    """Validate JWT and return user dict from token payload.

    In production this would look up the user in the database.  For now it
    returns the decoded token payload which must contain ``sub`` (user id)
    and ``role``.
    """
    payload = verify_access_token(token)
    user_id: Optional[str] = payload.get("sub")
    role: Optional[str] = payload.get("role")
    if user_id is None or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": user_id, "role": role, **payload}


def require_role(*roles: Role):
    """Dependency factory that restricts access to one or more roles."""

    def _check(current_user: Annotated[dict, Depends(get_current_user)]):
        if current_user["role"] not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check


# ---------------------------------------------------------------------------
# AES-256-GCM encryption / decryption for PHI fields
# ---------------------------------------------------------------------------
def _get_aesgcm() -> AESGCM:
    key_bytes = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY)
    if len(key_bytes) != 32:
        raise ValueError("ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256")
    return AESGCM(key_bytes)


def encrypt_phi(plaintext: str) -> str:
    """Encrypt a plaintext string and return a base64-encoded ciphertext.

    Format stored: base64(nonce || ciphertext)
    """
    aesgcm = _get_aesgcm()
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_phi(encrypted: str) -> str:
    """Decrypt a base64-encoded ciphertext produced by ``encrypt_phi``."""
    aesgcm = _get_aesgcm()
    raw = base64.urlsafe_b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
