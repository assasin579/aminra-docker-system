"""FastAPI dependency helpers for the lightweight RBAC policy service."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException

from auth.db import get_db
from auth.identity import resolve_canonical_tenant_id, resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from auth.policy_service import PolicyContext, PolicyService


def get_policy_service() -> PolicyService:
    return PolicyService()


def require_policy(action: str, resource_builder: Callable[[dict, Any], dict] | None = None):
    async def dependency(user: dict = Depends(get_current_user), db=Depends(get_db), policy: PolicyService = Depends(get_policy_service)):
        canonical_user_id = await resolve_canonical_user_id(user, db)
        canonical_tenant_id = await resolve_canonical_tenant_id(user, db)
        resource = resource_builder(user, db) if resource_builder else {}
        decision = policy.is_allowed(
            PolicyContext(
                role=user.get("role", ""),
                is_owner=bool(user.get("is_owner")),
                canonical_user_id=canonical_user_id,
                canonical_tenant_id=canonical_tenant_id,
            ),
            action,
            resource,
        )
        if not decision.allowed:
            raise HTTPException(403, decision.reason or "Forbidden")
        return True

    return dependency
