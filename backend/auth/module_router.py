from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.db import get_db
from auth.jwt_utils import get_current_user, require_admin
from auth.module_service import get_current_tenant_modules, set_tenant_module_status

router = APIRouter()
admin_router = APIRouter()


class TenantModuleStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(enabled|trial|disabled|locked)$")
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/modules")
async def get_my_modules(user=Depends(get_current_user), db=Depends(get_db)):
    return await get_current_tenant_modules(db, user)


@admin_router.get("/tenants/{tenant_id}/modules")
async def list_tenant_modules_for_admin(
    tenant_id: str,
    _admin: dict = Depends(require_admin),
    db=Depends(get_db),
):
    return await get_current_tenant_modules(db, {"tenant_id": tenant_id})


@admin_router.patch("/tenants/{tenant_id}/modules/{module_code}")
async def update_tenant_module_for_admin(
    tenant_id: str,
    module_code: str,
    payload: TenantModuleStatusUpdate,
    _admin: dict = Depends(require_admin),
    db=Depends(get_db),
):
    return await set_tenant_module_status(
        db,
        tenant_id,
        module_code,
        payload.status,
        config=payload.config,
    )
