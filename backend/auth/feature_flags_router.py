"""Feature-flag HTTP API.

Endpoints:
  GET  /api/feature-flags/me              — resolve all flags for current tenant
  GET  /auth/admin/feature-flags          — admin: list all flags + per-tenant overrides
  PUT  /auth/admin/feature-flags/{name}   — admin: upsert a flag (default + rollout)
  PUT  /auth/admin/feature-flags/{name}/overrides/{tenant_id} — set override
  DELETE /auth/admin/feature-flags/{name}/overrides/{tenant_id} — clear override
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.db import get_db
from auth.identity import resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from services import feature_flags

log = logging.getLogger("aminra.feature_flags.router")

# Tenant-facing router — mounted at /api/feature-flags
router = APIRouter()

# Admin router — mounted at /auth/admin
admin_router = APIRouter()


class FlagUpsertRequest(BaseModel):
    description: str | None = None
    default_enabled: bool = False
    rollout_percentage: int = Field(default=0, ge=0, le=100)


class OverrideSetRequest(BaseModel):
    enabled: bool
    reason: str | None = None


def _require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")


# ── Tenant-facing ───────────────────────────────────────────────────────────


@router.get("/me")
async def my_feature_flags(user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    """Returns {flag_name: enabled} for the authenticated tenant.

    Frontend hydrates `useFeature()` from this single response so each
    component lookup is O(1) without per-flag round-trips.
    """
    tenant_id = user.get("tenant_id")
    flags = await feature_flags.list_flags_for_tenant(db, tenant_id)
    return {"tenant_id": tenant_id, "flags": flags}


# ── Admin ───────────────────────────────────────────────────────────────────


@admin_router.get("/feature-flags")
async def admin_list_flags(user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    _require_admin(user)
    flags = await db.fetch(
        "SELECT name, description, default_enabled, rollout_percentage, created_at, updated_at "
        "FROM feature_flags ORDER BY name"
    )
    overrides = await db.fetch(
        "SELECT tenant_id, feature_name, enabled, override_reason, updated_at "
        "FROM tenant_feature_overrides ORDER BY feature_name, tenant_id"
    )
    return {
        "flags": [dict(f) for f in flags],
        "overrides": [dict(o) for o in overrides],
    }


@admin_router.put("/feature-flags/{name}")
async def admin_upsert_flag(
    name: str,
    body: FlagUpsertRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _require_admin(user)
    if not name or len(name) > 64:
        raise HTTPException(400, "Invalid flag name")
    await feature_flags.upsert_flag(
        db,
        name,
        description=body.description,
        default_enabled=body.default_enabled,
        rollout_percentage=body.rollout_percentage,
    )
    log.info(f"[feature-flags] Upsert {name} default={body.default_enabled} rollout={body.rollout_percentage}")
    return {"name": name, "message": "Flag updated"}


@admin_router.put("/feature-flags/{name}/overrides/{tenant_id}")
async def admin_set_override(
    name: str,
    tenant_id: str,
    body: OverrideSetRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _require_admin(user)
    flag = await db.fetchrow("SELECT name FROM feature_flags WHERE name = $1", name)
    if flag is None:
        raise HTTPException(404, f"Flag {name!r} not found")
    actor_id = await resolve_canonical_user_id(user, db)
    await feature_flags.set_tenant_override(
        db, tenant_id, name, body.enabled, reason=body.reason, created_by=str(actor_id) if actor_id else None
    )
    log.info(f"[feature-flags] Override tenant={tenant_id} flag={name} enabled={body.enabled}")
    return {"tenant_id": tenant_id, "feature_name": name, "enabled": body.enabled}


@admin_router.delete("/feature-flags/{name}/overrides/{tenant_id}")
async def admin_clear_override(
    name: str,
    tenant_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _require_admin(user)
    await feature_flags.clear_tenant_override(db, tenant_id, name)
    return {"tenant_id": tenant_id, "feature_name": name, "message": "Override cleared"}
