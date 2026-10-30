"""Complaints and appeals API routes."""
from __future__ import annotations

import inspect
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth.db import get_db
from auth.identity import resolve_canonical_tenant_id, resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from auth.policy_service import PolicyContext, PolicyService
from services.complaints_appeals import add_case_event, assign_case_owner, create_case, get_case, list_cases, transition_case

router = APIRouter()


class ComplaintCreateRequest(BaseModel):
    provider_id: Optional[str] = None
    business_tenant: Optional[str] = None
    certificate_id: Optional[str] = None
    submission_id: Optional[str] = None
    case_type: str
    source: str
    title: str
    description: str
    original_decision_id: Optional[str] = None
    due_at: Optional[datetime] = None


class ComplaintAssignRequest(BaseModel):
    owner_id: str
    notes: str = ""


class ComplaintTransitionRequest(BaseModel):
    to_status: str
    decision_summary: str = ""
    closure_reason: str = ""
    notes: str = ""


class ComplaintEventRequest(BaseModel):
    event_type: str
    notes: str = ""
    metadata: dict = Field(default_factory=dict)


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _canonical_context(user: dict, db) -> tuple[PolicyContext, str, str]:
    canonical_user_id = await _maybe_await(resolve_canonical_user_id(user, db))
    canonical_tenant_id = await _maybe_await(resolve_canonical_tenant_id(user, db))
    if not canonical_user_id or not canonical_tenant_id:
        raise HTTPException(404, "User not found")
    ctx = PolicyContext(
        role=user.get("role", ""),
        is_owner=bool(user.get("is_owner")),
        canonical_user_id=canonical_user_id,
        canonical_tenant_id=canonical_tenant_id,
    )
    return ctx, str(canonical_user_id), str(canonical_tenant_id)


def _action_for_case_type(case_type: str) -> str:
    return "appeal.manage" if case_type == "appeal_decision" else "complaint.manage"


@router.get("")
async def list_complaints_route(
    status: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    ctx, _actor_id, tenant_id = await _canonical_context(user, db)
    if user.get("role") == "provider":
        decision = PolicyService().is_allowed(ctx, "complaint.manage", {"provider_id": tenant_id})
        if not decision.allowed:
            raise HTTPException(403, decision.reason or "Forbidden")
        return {"cases": await list_cases(db, provider_id=tenant_id, status=status)}
    if user.get("role") == "business":
        decision = PolicyService().is_allowed(ctx, "complaint.manage", {"business_tenant": tenant_id})
        if not decision.allowed:
            raise HTTPException(403, decision.reason or "Forbidden")
        return {"cases": await list_cases(db, business_tenant=tenant_id, status=status)}
    raise HTTPException(403, "Provider owner or business access required")


@router.post("")
async def create_complaint_route(req: ComplaintCreateRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, tenant_id = await _canonical_context(user, db)
    provider_id = req.provider_id if user.get("role") == "business" else tenant_id
    business_tenant = req.business_tenant
    if user.get("role") == "business":
        business_tenant = tenant_id
        if req.business_tenant and str(req.business_tenant) != tenant_id:
            raise HTTPException(403, "Business may create complaints only for own tenant")
        if not provider_id:
            raise HTTPException(400, "provider_id is required for business complaints")
    if not provider_id:
        raise HTTPException(400, "provider_id is required")
    if user.get("role") == "provider" and not user.get("is_owner"):
        raise HTTPException(403, "Provider owner access required")
    action = _action_for_case_type(req.case_type)
    resource = {"business_tenant": tenant_id} if user.get("role") == "business" else {"provider_id": provider_id}
    decision = PolicyService().is_allowed(ctx, action, resource)
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    return await create_case(
        db,
        provider_id=provider_id,
        business_tenant=business_tenant,
        certificate_id=req.certificate_id,
        submission_id=req.submission_id,
        case_type=req.case_type,
        source=req.source,
        title=req.title,
        description=req.description,
        submitted_by_user_id=actor_id,
        original_decision_id=req.original_decision_id,
        due_at=req.due_at,
        user=user,
    )


@router.get("/{case_id}")
async def get_complaint_route(case_id: str, user: dict = Depends(get_current_user), db=Depends(get_db)):
    _ctx, _actor_id, tenant_id = await _canonical_context(user, db)
    if user.get("role") == "provider":
        if not user.get("is_owner"):
            raise HTTPException(403, "Provider owner access required")
        return await get_case(db, case_id=case_id, provider_id=tenant_id)
    if user.get("role") == "business":
        return await get_case(db, case_id=case_id, business_tenant=tenant_id)
    raise HTTPException(403, "Provider owner or business access required")


@router.post("/{case_id}/assign")
async def assign_complaint_route(case_id: str, req: ComplaintAssignRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, provider_id = await _canonical_context(user, db)
    decision = PolicyService().is_allowed(ctx, "complaint.manage", {"provider_id": provider_id})
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    return await assign_case_owner(db, case_id=case_id, provider_id=provider_id, owner_id=req.owner_id, actor_user_id=actor_id, notes=req.notes, user=user)


@router.post("/{case_id}/transition")
async def transition_complaint_route(case_id: str, req: ComplaintTransitionRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, provider_id = await _canonical_context(user, db)
    decision = PolicyService().is_allowed(ctx, "complaint.manage", {"provider_id": provider_id})
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    return await transition_case(
        db,
        case_id=case_id,
        provider_id=provider_id,
        actor_user_id=actor_id,
        to_status=req.to_status,
        decision_summary=req.decision_summary,
        closure_reason=req.closure_reason,
        notes=req.notes,
        user=user,
    )


@router.post("/{case_id}/events")
async def add_complaint_event_route(case_id: str, req: ComplaintEventRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    ctx, actor_id, provider_id = await _canonical_context(user, db)
    decision = PolicyService().is_allowed(ctx, "complaint.manage", {"provider_id": provider_id})
    if not decision.allowed:
        raise HTTPException(403, decision.reason or "Forbidden")
    await get_case(db, case_id=case_id, provider_id=provider_id)
    return await add_case_event(db, case_id=case_id, actor_user_id=actor_id, event_type=req.event_type, notes=req.notes, metadata=req.metadata, user=user)
