"""Certification decision routes for CB independent approval."""
from __future__ import annotations

import inspect
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.db import get_db
from auth.identity import resolve_canonical_tenant_id, resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from auth.policy_service import PolicyContext, PolicyService
from services.certification_decisions import (
    approve_decision,
    create_decision_case,
    get_decision_for_submission,
    reject_decision,
)

router = APIRouter()


class DecisionCreateRequest(BaseModel):
    submission_id: str
    audit_visit_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    notes: str = ""


class DecisionFinalizeRequest(BaseModel):
    reason: str
    notes: str = ""


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _canonical_context(user: dict, db) -> tuple[PolicyContext, str, str]:
    canonical_user_id = await _maybe_await(resolve_canonical_user_id(user, db))
    canonical_tenant_id = await _maybe_await(resolve_canonical_tenant_id(user, db))
    ctx = PolicyContext(
        role=user.get("role", ""),
        is_owner=bool(user.get("is_owner")),
        canonical_user_id=canonical_user_id,
        canonical_tenant_id=canonical_tenant_id,
    )
    return ctx, str(canonical_user_id), str(canonical_tenant_id)


@router.post("")
async def create_decision(req: DecisionCreateRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, provider_id = await _canonical_context(user, db)
    decision = PolicyService().is_allowed(ctx, "certification_decision.create", {"provider_id": provider_id})
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    return await create_decision_case(
        db,
        submission_id=req.submission_id,
        audit_visit_id=req.audit_visit_id,
        reviewer_id=req.reviewer_id,
        notes=req.notes,
        created_by=actor_id,
        provider_id=provider_id,
        user=user,
    )


@router.get("/submission/{submission_id}")
async def get_decision(submission_id: str, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, _actor_id, provider_id = await _canonical_context(user, db)
    action = "submission.read"
    resource = {"provider_id": provider_id} if user.get("role") == "provider" else {"business_tenant": provider_id}
    decision = PolicyService().is_allowed(ctx, action, resource)
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    row = await get_decision_for_submission(
        db,
        submission_id=submission_id,
        provider_id=provider_id if user.get("role") == "provider" else None,
        business_tenant=provider_id if user.get("role") == "business" else None,
    )
    if not row:
        raise HTTPException(404, "Certification decision not found")
    return row


@router.post("/{decision_id}/approve")
async def approve_decision_route(decision_id: str, req: DecisionFinalizeRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, provider_id = await _canonical_context(user, db)
    decision = PolicyService().is_allowed(ctx, "certification_decision.approve", {"provider_id": provider_id})
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    return await approve_decision(db, decision_id=decision_id, decision_maker_id=actor_id, provider_id=provider_id, reason=req.reason, notes=req.notes, user=user)


@router.post("/{decision_id}/reject")
async def reject_decision_route(decision_id: str, req: DecisionFinalizeRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, provider_id = await _canonical_context(user, db)
    decision = PolicyService().is_allowed(ctx, "certification_decision.approve", {"provider_id": provider_id})
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    return await reject_decision(db, decision_id=decision_id, decision_maker_id=actor_id, provider_id=provider_id, reason=req.reason, notes=req.notes, user=user)
