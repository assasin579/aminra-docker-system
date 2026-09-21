from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.db import get_db
from auth.jwt_utils import get_current_user, require_admin
from auth.module_service import (
    create_module_activation_request,
    escalate_overdue_module_activation_requests,
    get_current_tenant_modules,
    list_module_activation_requests,
    review_module_activation_request,
    set_tenant_module_status,
)

router = APIRouter()
admin_router = APIRouter()


class TenantModuleStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(enabled|trial|disabled|locked)$")
    config: dict[str, Any] = Field(default_factory=dict)


class ModuleActivationRequestCreate(BaseModel):
    module_code: str = Field(..., min_length=1, max_length=80)
    route_path: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=1000)


class ModuleActivationRequestReview(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    admin_note: str | None = Field(default=None, max_length=1000)


class ModuleActivationEscalationRequest(BaseModel):
    tenant_id: str | None = Field(default=None, min_length=1, max_length=80)
    limit: int = Field(default=25, ge=1, le=100)


@router.get("/modules")
async def get_my_modules(user=Depends(get_current_user), db=Depends(get_db)):
    return await get_current_tenant_modules(db, user)


@router.post("/module-activation-requests")
async def create_my_module_activation_request(
    payload: ModuleActivationRequestCreate,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await create_module_activation_request(
        db,
        user,
        payload.module_code,
        route_path=payload.route_path,
        message=payload.message,
    )


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


@admin_router.get("/module-activation-requests")
async def list_activation_requests_for_admin(
    tenant_id: str | None = None,
    status: str = "pending",
    _admin: dict = Depends(require_admin),
    db=Depends(get_db),
):
    return await list_module_activation_requests(db, tenant_id=tenant_id, status=status)


@admin_router.post("/module-activation-requests/escalate-overdue")
async def escalate_overdue_activation_requests_for_admin(
    payload: ModuleActivationEscalationRequest,
    admin: dict = Depends(require_admin),
    db=Depends(get_db),
):
    return await escalate_overdue_module_activation_requests(
        db,
        admin=admin,
        tenant_id=payload.tenant_id,
        limit=payload.limit,
    )


@admin_router.patch("/module-activation-requests/{request_id}")
async def review_activation_request_for_admin(
    request_id: str,
    payload: ModuleActivationRequestReview,
    admin: dict = Depends(require_admin),
    db=Depends(get_db),
):
    return await review_module_activation_request(
        db,
        request_id,
        action=payload.action,
        admin=admin,
        admin_note=payload.admin_note,
    )
