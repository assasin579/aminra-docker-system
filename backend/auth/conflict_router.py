"""Conflict-of-interest API routes."""
from __future__ import annotations

import inspect
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth.db import get_db
from auth.identity import resolve_canonical_tenant_id, resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from services.conflict_interest import declare_conflict, get_conflict, list_conflicts, override_conflict, review_conflict

router = APIRouter()


class ConflictDeclareRequest(BaseModel):
    business_tenant: str
    person_user_id: str
    person_role: str
    conflict_type: str
    description: str
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None


class ConflictReviewRequest(BaseModel):
    status: str
    review_reason: str


class ConflictOverrideRequest(BaseModel):
    override_reason: str


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _canonical_ids(user: dict, db) -> tuple[str, str]:
    actor_id = await _maybe_await(resolve_canonical_user_id(user, db))
    tenant_id = await _maybe_await(resolve_canonical_tenant_id(user, db))
    if not actor_id or not tenant_id:
        raise HTTPException(404, "User not found")
    return str(actor_id), str(tenant_id)


def _require_provider_staff(user: dict) -> None:
    if user.get("role") != "provider" and user.get("role") != "cb_admin":
        raise HTTPException(403, "Provider access required")


def _require_owner_or_admin(user: dict) -> None:
    _require_provider_staff(user)
    if not user.get("is_owner") and user.get("role") != "cb_admin":
        raise HTTPException(403, "Provider owner or CB admin required")


@router.get("")
async def list_conflicts_route(
    business_tenant: str | None = Query(default=None),
    person_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    _require_provider_staff(user)
    _actor_id, provider_id = await _canonical_ids(user, db)
    return {"conflicts": await list_conflicts(db, provider_id=provider_id, business_tenant=business_tenant, person_user_id=person_user_id, status=status)}


@router.post("")
async def declare_conflict_route(req: ConflictDeclareRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    _require_provider_staff(user)
    actor_id, provider_id = await _canonical_ids(user, db)
    return await declare_conflict(
        db,
        provider_id=provider_id,
        business_tenant=req.business_tenant,
        person_user_id=req.person_user_id,
        person_role=req.person_role,
        conflict_type=req.conflict_type,
        description=req.description,
        declared_by=actor_id,
        valid_from=req.valid_from,
        valid_until=req.valid_until,
        user=user,
    )


@router.get("/{conflict_id}")
async def get_conflict_route(conflict_id: str, user: dict = Depends(get_current_user), db=Depends(get_db)):
    _require_provider_staff(user)
    _actor_id, provider_id = await _canonical_ids(user, db)
    return await get_conflict(db, conflict_id=conflict_id, provider_id=provider_id)


@router.post("/{conflict_id}/review")
async def review_conflict_route(conflict_id: str, req: ConflictReviewRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    _require_owner_or_admin(user)
    actor_id, provider_id = await _canonical_ids(user, db)
    return await review_conflict(
        db,
        conflict_id=conflict_id,
        provider_id=provider_id,
        reviewed_by=actor_id,
        status=req.status,
        review_reason=req.review_reason,
        user=user,
    )


@router.post("/{conflict_id}/override")
async def override_conflict_route(conflict_id: str, req: ConflictOverrideRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    _require_owner_or_admin(user)
    actor_id, provider_id = await _canonical_ids(user, db)
    return await override_conflict(
        db,
        conflict_id=conflict_id,
        provider_id=provider_id,
        overridden_by=actor_id,
        override_reason=req.override_reason,
        caller=user,
    )
