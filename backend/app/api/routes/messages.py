"""Internal staff messaging — scheduler ↔ nurse ↔ physician."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import Role, get_current_user
from app.models.message import StaffMessage
from app.models.user import User

router = APIRouter(prefix="/messages", tags=["messages"])

# ── Staff directory ───────────────────────────────────────────────────────────

class StaffMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    role: str

# Roles that may use internal messaging (patients and admins excluded)
_STAFF_ROLES = {Role.SCHEDULER, Role.NURSE, Role.PHYSICIAN}


def _require_staff(current_user: dict) -> dict:
    role_str = current_user.get("role", "")
    try:
        role = Role(role_str)
    except ValueError:
        role = None
    if role not in _STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    return current_user


# ── Schemas ──────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    recipient_id: uuid.UUID
    content: str
    appointment_id: Optional[uuid.UUID] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    appointment_id: Optional[uuid.UUID]
    content: str
    is_read: bool
    created_at: str
    sender_name: str
    sender_role: str

    @classmethod
    def from_orm_with_names(cls, msg: StaffMessage) -> "MessageResponse":
        return cls(
            id=msg.id,
            sender_id=msg.sender_id,
            recipient_id=msg.recipient_id,
            appointment_id=msg.appointment_id,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at.isoformat(),
            sender_name=msg.sender.full_name,
            sender_role=msg.sender.role.value if hasattr(msg.sender.role, "value") else str(msg.sender.role),
        )


class InboxResponse(BaseModel):
    unread_count: int
    messages: list[MessageResponse]


# ── Send ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    body: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to a nurse or physician.  Scheduler, nurse, and physician only."""
    _require_staff(current_user)

    # Verify recipient exists and is staff
    result = await db.execute(select(User).where(User.id == body.recipient_id))
    recipient = result.scalar_one_or_none()
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")

    try:
        recipient_role = Role(recipient.role.value if hasattr(recipient.role, "value") else recipient.role)
    except ValueError:
        recipient_role = None

    if recipient_role not in _STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Can only message scheduler, nurse, or physician staff")

    msg = StaffMessage(
        sender_id=current_user["user_id"],
        recipient_id=body.recipient_id,
        appointment_id=body.appointment_id,
        content=body.content,
        is_read=False,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg, ["sender", "recipient"])
    await db.commit()

    return MessageResponse.from_orm_with_names(msg)


# ── Inbox ─────────────────────────────────────────────────────────────────────

@router.get("/inbox", response_model=InboxResponse)
async def get_inbox(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return messages received by the current user, newest first."""
    _require_staff(current_user)

    result = await db.execute(
        select(StaffMessage)
        .where(StaffMessage.recipient_id == current_user["user_id"])
        .options(selectinload(StaffMessage.sender))
        .order_by(StaffMessage.created_at.desc())
        .limit(50)
    )
    messages = result.scalars().all()
    unread = sum(1 for m in messages if not m.is_read)

    return InboxResponse(
        unread_count=unread,
        messages=[MessageResponse.from_orm_with_names(m) for m in messages],
    )


# ── Unread count (lightweight poll) ──────────────────────────────────────────

@router.get("/unread-count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return just the unread message count for badge display."""
    _require_staff(current_user)

    result = await db.execute(
        select(StaffMessage).where(
            StaffMessage.recipient_id == current_user["user_id"],
            StaffMessage.is_read == False,  # noqa: E712
        )
    )
    count = len(result.scalars().all())
    return {"unread_count": count}


# ── Mark read ─────────────────────────────────────────────────────────────────

@router.put("/{message_id}/read", response_model=MessageResponse)
async def mark_read(
    message_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a message as read.  Only the recipient may do this."""
    _require_staff(current_user)

    result = await db.execute(
        select(StaffMessage)
        .where(StaffMessage.id == message_id)
        .options(selectinload(StaffMessage.sender))
    )
    msg = result.scalar_one_or_none()
    if msg is None or str(msg.recipient_id) != str(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Message not found")

    msg.is_read = True
    await db.commit()
    await db.refresh(msg, ["sender"])
    return MessageResponse.from_orm_with_names(msg)


# ── Appointment thread ────────────────────────────────────────────────────────

@router.get("/appointment/{appointment_id}", response_model=list[MessageResponse])
async def get_appointment_messages(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all messages attached to a specific appointment.

    Only visible to the sender or recipient of each message, so a
    scheduler sees every thread they started; a physician/nurse sees
    threads addressed to them.
    """
    _require_staff(current_user)
    uid = current_user["user_id"]

    result = await db.execute(
        select(StaffMessage)
        .where(
            StaffMessage.appointment_id == appointment_id,
            or_(
                StaffMessage.sender_id == uid,
                StaffMessage.recipient_id == uid,
            ),
        )
        .options(selectinload(StaffMessage.sender))
        .order_by(StaffMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return [MessageResponse.from_orm_with_names(m) for m in messages]


@router.get("/staff-directory", response_model=list[StaffMemberResponse])
async def get_staff_directory(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return messageable staff members (nurse + physician + scheduler),
    excluding the caller."""
    _require_staff(current_user)

    result = await db.execute(
        select(User).where(
            User.role.in_([Role.NURSE, Role.PHYSICIAN, Role.SCHEDULER]),
            User.is_active == True,  # noqa: E712
            User.id != current_user["user_id"],
        ).order_by(User.role, User.full_name)
    )
    users = result.scalars().all()
    return [
        StaffMemberResponse(
            id=u.id,
            full_name=u.full_name,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
        )
        for u in users
    ]
