import logging
from fastapi import APIRouter, Depends, HTTPException, status
from asyncpg import Connection
from pydantic import BaseModel
from typing import Optional

from .db import get_db
from .jwt_utils import require_admin
from .models import PendingProvidersResponse, PendingProviderItem

log = logging.getLogger("aminra.auth.admin")
router = APIRouter()


class RejectRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/admin/pending-providers", response_model=PendingProvidersResponse)
async def pending_providers(admin: dict = Depends(require_admin), db: Connection = Depends(get_db)):
    rows = await db.fetch(
        "SELECT id, email, company_name, company_code, created_at FROM users "
        "WHERE role = 'provider' AND status = 'pending' ORDER BY created_at",
    )
    return PendingProvidersResponse(
        providers=[PendingProviderItem(
            id=str(r["id"]), email=r["email"],
            company_name=r["company_name"], company_code=r["company_code"],
            created_at=r["created_at"],
        ) for r in rows],
        count=len(rows),
    )


@router.post("/admin/providers/{provider_id}/approve")
async def approve_provider(
    provider_id: str,
    admin: dict = Depends(require_admin),
    db: Connection = Depends(get_db),
):
    row = await db.fetchrow(
        """
        UPDATE users SET status = 'active', approved_by = $2, approved_at = NOW()
        WHERE id = $1 AND role = 'provider' AND status = 'pending'
        RETURNING id, email, status
        """,
        provider_id, admin["sub"],
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found or not pending")
    log.info(f"[auth] Provider approved: {row['email']}")
    return {"id": str(row["id"]), "email": row["email"], "status": row["status"]}


@router.post("/admin/providers/{provider_id}/reject")
async def reject_provider(
    provider_id: str,
    req: RejectRequest,
    admin: dict = Depends(require_admin),
    db: Connection = Depends(get_db),
):
    row = await db.fetchrow(
        """
        UPDATE users SET status = 'suspended', rejection_reason = $2
        WHERE id = $1 AND role = 'provider' AND status = 'pending'
        RETURNING id, email, status
        """,
        provider_id, req.reason,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found or not pending")
    log.info(f"[auth] Provider rejected: {row['email']}")
    return {"id": str(row["id"]), "email": row["email"], "status": row["status"]}
