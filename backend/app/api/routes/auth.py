"""Authentication routes: login, register, logout, current-user info."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    Role,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _audit_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str,
    success: bool,
) -> None:
    """Write an audit log entry.  Uses raw execute to avoid circular model imports."""
    await db.execute(
        # language=SQL
        __import__("sqlalchemy").text(
            "INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, success, created_at) "
            "VALUES (:id, :user_id, :action, :resource_type, :resource_id, :success, now())"
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "success": success,
        },
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user with email and password, returning a JWT bearer token."""

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        logger.warning("Failed login attempt for email=%s", body.email)
        await _audit_log(
            db,
            user_id=user.id if user else uuid.UUID(int=0),
            action="login_failed",
            resource_type="user",
            resource_id=user.id if user else uuid.UUID(int=0),
            success=False,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.full_name}
    )

    await _audit_log(
        db,
        user_id=user.id,
        action="login_success",
        resource_type="user",
        resource_id=user.id,
        success=True,
    )
    await db.commit()

    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict | None = None,
):
    """Create a new user account.

    Patients can self-register (no auth required).  Creating provider roles
    (physician, nurse, scheduler, admin) requires an authenticated admin.
    """

    requested_role = Role(body.role)

    # Provider roles require admin authorization
    if requested_role != Role.PATIENT:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin authentication required to create provider accounts",
            )
        if current_user["role"] != Role.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create provider accounts",
            )

    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    new_user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=requested_role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    registrant_id = current_user["user_id"] if current_user else str(new_user.id)
    await _audit_log(
        db,
        user_id=registrant_id,
        action="user_registered",
        resource_type="user",
        resource_id=new_user.id,
        success=True,
    )
    await db.commit()
    await db.refresh(new_user)

    logger.info("User registered: id=%s role=%s", new_user.id, new_user.role.value)
    return UserResponse.model_validate(new_user)


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invalidate the current session.

    In a stateless JWT setup, the client simply discards the token.
    This endpoint records the logout event in the audit log and could be
    extended to maintain a token denylist backed by Redis.
    """

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="logout",
        resource_type="user",
        resource_id=current_user["user_id"],
        success=True,
    )
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's profile information."""

    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_own_profile",
        resource_type="user",
        resource_id=current_user["user_id"],
        success=True,
    )
    await db.commit()

    return UserResponse.model_validate(user)
