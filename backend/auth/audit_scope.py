"""Scoped authorization helpers for audit visit mutation endpoints.

This module intentionally has no router side effects. It centralizes the
provider-owner / assigned-auditor / business-tenant ownership checks that write
routes can call before mutating audit visit related state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, status

from auth.identity import resolve_canonical_tenant_id, resolve_canonical_user_id

AuditVisitMutationScopeName = Literal["provider_owner", "auditor", "business"]


@dataclass(frozen=True)
class AuditVisitMutationScope:
    """Authorized audit visit scope details useful to route handlers."""

    visit: Any
    scope: AuditVisitMutationScopeName
    canonical_tenant_id: Any | None = None
    canonical_user_id: Any | None = None


def _same_id(left: Any, right: Any) -> bool:
    """Compare UUID/string ids without widening authorization on falsey values."""
    return left is not None and right is not None and str(left) == str(right)


def _row_get(row: Any, key: str) -> Any:
    """Read from asyncpg.Record, dict-like fakes, or mapping rows without assuming .get()."""
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, TypeError):
        return getattr(row, key, None)


async def assert_audit_visit_mutation_scope(
    visit_id: Any,
    user: dict,
    db: Any,
    *,
    allow_business: bool = False,
    allow_auditor: bool = True,
    allow_provider_owner: bool = True,
) -> AuditVisitMutationScope:
    """Assert the current principal may mutate state scoped to an audit visit.

    Authorization rules are deliberately narrow and fail closed:
    - provider owners must resolve to the visit's provider_id;
    - assigned auditors must resolve to the visit's auditor_id;
    - business access is opt-in and must resolve to business_tenant.

    Returns an AuditVisitMutationScope containing the visit row and matched scope
    so route handlers can reuse the already-loaded row.
    """
    visit = await db.fetchrow(
        """
        SELECT id, provider_id, auditor_id, business_tenant
        FROM audit_visits
        WHERE id=$1
        """,
        visit_id,
    )
    if not visit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit visit not found")

    canonical_tenant_id = await resolve_canonical_tenant_id(user, db)
    canonical_user_id = await resolve_canonical_user_id(user, db) if allow_auditor else None

    if (
        allow_provider_owner
        and user.get("role") == "provider"
        and bool(user.get("is_owner"))
        and _same_id(canonical_tenant_id, _row_get(visit, "provider_id"))
    ):
        return AuditVisitMutationScope(
            visit=visit,
            scope="provider_owner",
            canonical_tenant_id=canonical_tenant_id,
            canonical_user_id=canonical_user_id,
        )

    if allow_auditor and _same_id(canonical_user_id, _row_get(visit, "auditor_id")):
        return AuditVisitMutationScope(
            visit=visit,
            scope="auditor",
            canonical_tenant_id=canonical_tenant_id,
            canonical_user_id=canonical_user_id,
        )

    if allow_business and _same_id(canonical_tenant_id, _row_get(visit, "business_tenant")):
        return AuditVisitMutationScope(
            visit=visit,
            scope="business",
            canonical_tenant_id=canonical_tenant_id,
            canonical_user_id=canonical_user_id,
        )

    raise HTTPException(status.HTTP_403_FORBIDDEN, "Audit visit scope denied")
