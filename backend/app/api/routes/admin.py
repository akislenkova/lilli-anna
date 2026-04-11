"""Admin routes for coverage, proxy management, and audit logs."""

from __future__ import annotations

from typing import Optional

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_role
from app.models.audit import AuditAction, AuditLog
from app.models.coverage import PhysicianCoverage
from app.models.proxy import ProxyAuthorization, ProxyRelationship
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Coverage ──────────────────────────────────────────────────────────


@router.post("/coverage", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_coverage(
    covering_physician_id: UUID,
    absent_physician_id: UUID,
    start_date: date,
    end_date: date,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a time-limited physician coverage assignment."""
    if start_date > end_date:
        raise HTTPException(400, "start_date must be before end_date")

    # Verify both are physicians
    for pid in (covering_physician_id, absent_physician_id):
        result = await db.execute(select(User).where(User.id == pid, User.role == Role.PHYSICIAN))
        if not result.scalar_one_or_none():
            raise HTTPException(404, f"Physician {pid} not found")

    coverage = PhysicianCoverage(
        covering_physician_id=covering_physician_id,
        absent_physician_id=absent_physician_id,
        start_date=start_date,
        end_date=end_date,
        assigned_by=UUID(current_user["user_id"]),
        is_active=True,
    )
    db.add(coverage)
    await db.commit()
    await db.refresh(coverage)

    await AuditService(db).log_modification(
        user_id=UUID(current_user["user_id"]), resource_type="coverage", resource_id=coverage.id,
        changes={"action": "created", "covering": str(covering_physician_id), "absent": str(absent_physician_id)},
        ip_address="",
    )
    return {"id": coverage.id, "status": "created"}


@router.delete("/coverage/{coverage_id}", dependencies=[Depends(require_role(Role.ADMIN))])
async def revoke_coverage(
    coverage_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an active physician coverage."""
    result = await db.execute(select(PhysicianCoverage).where(PhysicianCoverage.id == coverage_id))
    coverage = result.scalar_one_or_none()
    if not coverage:
        raise HTTPException(404, "Coverage not found")

    coverage.is_active = False
    await db.commit()
    await AuditService(db).log_modification(
        user_id=UUID(current_user["user_id"]), resource_type="coverage", resource_id=coverage_id,
        changes={"action": "revoked"}, ip_address="",
    )
    return {"status": "revoked"}


@router.get("/coverage", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_coverages(db: AsyncSession = Depends(get_db)):
    """List all active physician coverages."""
    result = await db.execute(
        select(PhysicianCoverage).where(PhysicianCoverage.is_active == True)
    )
    coverages = result.scalars().all()
    return [
        {
            "id": c.id,
            "covering_physician_id": c.covering_physician_id,
            "absent_physician_id": c.absent_physician_id,
            "start_date": c.start_date,
            "end_date": c.end_date,
            "is_active": c.is_active,
        }
        for c in coverages
    ]


# ── Proxy Authorization ──────────────────────────────────────────────


@router.post("/proxy", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_proxy(
    patient_id: UUID,
    proxy_user_id: UUID,
    relationship: str,
    state_code: str,
    minor_age_of_consent: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a proxy authorization (parent/guardian, caregiver, legal proxy)."""
    proxy = ProxyAuthorization(
        patient_id=patient_id,
        proxy_user_id=proxy_user_id,
        relationship=ProxyRelationship(relationship),
        state_code=state_code,
        minor_age_of_consent=minor_age_of_consent,
        is_active=True,
        verified=False,
    )
    db.add(proxy)
    await db.commit()
    await db.refresh(proxy)

    await AuditService(db).log_modification(
        user_id=UUID(current_user["user_id"]), resource_type="proxy", resource_id=proxy.id,
        changes={"action": "created", "patient": str(patient_id), "proxy_user": str(proxy_user_id)},
        ip_address="",
    )
    return {"id": proxy.id, "status": "created"}


@router.get("/proxy/patient/{patient_id}", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_patient_proxies(patient_id: UUID, db: AsyncSession = Depends(get_db)):
    """List all proxy authorizations for a patient."""
    result = await db.execute(
        select(ProxyAuthorization).where(ProxyAuthorization.patient_id == patient_id)
    )
    proxies = result.scalars().all()
    return [
        {
            "id": p.id,
            "proxy_user_id": p.proxy_user_id,
            "relationship": p.relationship.value if p.relationship else None,
            "verified": p.verified,
            "is_active": p.is_active,
            "state_code": p.state_code,
        }
        for p in proxies
    ]


@router.put("/proxy/{proxy_id}/verify", dependencies=[Depends(require_role(Role.ADMIN))])
async def verify_proxy(
    proxy_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a proxy authorization as verified."""
    result = await db.execute(
        select(ProxyAuthorization).where(ProxyAuthorization.id == proxy_id)
    )
    proxy = result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(404, "Proxy authorization not found")

    proxy.verified = True
    proxy.verified_by = UUID(current_user["user_id"])
    await db.commit()

    await AuditService(db).log_modification(
        user_id=UUID(current_user["user_id"]), resource_type="proxy", resource_id=proxy_id,
        changes={"action": "verified"}, ip_address="",
    )
    return {"status": "verified"}


# ── Audit Logs ────────────────────────────────────────────────────────


@router.get("/audit-logs", dependencies=[Depends(require_role(Role.ADMIN))])
async def query_audit_logs(
    user_id: Optional[UUID] = None,
    patient_id: Optional[UUID] = None,
    action: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Query the immutable audit log."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if patient_id:
        query = query.where(AuditLog.patient_id_accessed == patient_id)
    if action:
        query = query.where(AuditLog.action == AuditAction(action))
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action.value if log.action else None,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "success": log.success,
                "details": log.details,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }


# ── Override Report ───────────────────────────────────────────────────


@router.get("/override-report", dependencies=[Depends(require_role(Role.ADMIN))])
async def scheduler_override_report(db: AsyncSession = Depends(get_db)):
    """
    Surface patterns where schedulers consistently override AI duration downward
    and post-visit feedback indicates rushed appointments (spec 6.3).
    """
    return await AuditService(db).get_override_patterns()
