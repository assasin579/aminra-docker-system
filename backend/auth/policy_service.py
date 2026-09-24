"""Lightweight RBAC policy engine for CB trust-core actions.

Week 1 intentionally keeps this small and explicit: default deny, no wildcard
roles, and only canonical AMINRA UUID ids may be used for access decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

SUPPORTED_ACTIONS = {
    "submission.read",
    "submission.review",
    "audit.assign",
    "audit.perform",
    "certification_decision.create",
    "certification_decision.approve",
    "certificate.issue",
    "complaint.manage",
    "appeal.manage",
}


@dataclass(frozen=True)
class PolicyContext:
    role: str
    canonical_user_id: UUID | str | None
    canonical_tenant_id: UUID | str | None
    is_owner: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyService:
    def is_allowed(self, ctx: PolicyContext, action: str, resource: dict[str, Any] | None = None) -> PolicyDecision:
        resource = resource or {}
        if action not in SUPPORTED_ACTIONS:
            return PolicyDecision(False, "unsupported action")
        if ctx.role not in {"provider", "business", "admin"}:
            return PolicyDecision(False, "unknown role")
        if not _is_uuid(ctx.canonical_user_id) or not _is_uuid(ctx.canonical_tenant_id):
            return PolicyDecision(False, "canonical ids required")

        if ctx.role == "admin":
            return PolicyDecision(True, "admin")
        if ctx.role == "business":
            return self._business_allowed(ctx, action, resource)
        if ctx.role == "provider":
            return self._provider_allowed(ctx, action, resource)
        return PolicyDecision(False, "default deny")

    def _business_allowed(self, ctx: PolicyContext, action: str, resource: dict[str, Any]) -> PolicyDecision:
        if action in {"submission.read", "complaint.manage", "appeal.manage"}:
            return _scope_decision(_same(resource.get("business_tenant"), ctx.canonical_tenant_id), "business tenant scope")
        return PolicyDecision(False, "business role cannot perform provider trust action")

    def _provider_allowed(self, ctx: PolicyContext, action: str, resource: dict[str, Any]) -> PolicyDecision:
        if action == "submission.read":
            if ctx.is_owner:
                return _scope_decision(_same(resource.get("provider_id"), ctx.canonical_tenant_id), "provider scope")
            return _scope_decision(_same(resource.get("auditor_id"), ctx.canonical_user_id), "assigned auditor scope")
        if action == "submission.review":
            if ctx.is_owner:
                return _scope_decision(_same(resource.get("provider_id"), ctx.canonical_tenant_id), "provider scope")
            return _scope_decision(_same(resource.get("auditor_id"), ctx.canonical_user_id), "assigned auditor scope")
        if action == "audit.assign":
            return _scope_decision(ctx.is_owner and _same(resource.get("provider_id"), ctx.canonical_tenant_id), "provider owner scope")
        if action == "audit.perform":
            if ctx.is_owner:
                return _scope_decision(_same(resource.get("provider_id"), ctx.canonical_tenant_id), "provider owner scope")
            return _scope_decision(_same(resource.get("auditor_id"), ctx.canonical_user_id), "assigned auditor scope")
        if action in {"certification_decision.create", "certification_decision.approve", "certificate.issue", "complaint.manage", "appeal.manage"}:
            return _scope_decision(ctx.is_owner and _same(resource.get("provider_id"), ctx.canonical_tenant_id), "provider owner scope")
        return PolicyDecision(False, "default deny")


def _scope_decision(ok: bool, reason: str) -> PolicyDecision:
    return PolicyDecision(bool(ok), "allowed" if ok else reason)


def _is_uuid(value: UUID | str | None) -> bool:
    if value is None:
        return False
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _same(left: Any, right: Any) -> bool:
    return left is not None and right is not None and str(left) == str(right)
