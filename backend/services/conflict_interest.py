"""Conflict-of-interest service for CB trust controls."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from services.audit_log import log_audit

PERSON_ROLES = {"auditor", "reviewer", "decision_maker", "cb_admin"}
CONFLICT_TYPES = {"prior_employment", "consultancy", "financial_interest", "family_relationship", "ownership", "other"}
STATUSES = {"declared", "under_review", "cleared", "blocked", "overridden"}
UNRESOLVED_STATUSES = {"declared", "under_review", "blocked"}


def _validate_uuid(value: str, field: str) -> str:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(400, f"Invalid {field}")
    return str(value)


def _require_non_empty(value: str | None, field: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(400, f"{field} is required")
    return cleaned


def _row_to_dict(row) -> dict[str, Any]:
    result = dict(row)
    for key, value in list(result.items()):
        if isinstance(value, (UUID, date)):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    return result


def _require_role(value: str) -> str:
    if value not in PERSON_ROLES:
        raise HTTPException(400, "Invalid person_role")
    return value


def _require_conflict_type(value: str) -> str:
    if value not in CONFLICT_TYPES:
        raise HTTPException(400, "Invalid conflict_type")
    return value


def _require_status(value: str) -> str:
    if value not in STATUSES:
        raise HTTPException(400, "Invalid conflict status")
    return value


async def declare_conflict(
    db,
    *,
    provider_id: str,
    business_tenant: str,
    person_user_id: str,
    person_role: str,
    conflict_type: str,
    description: str,
    declared_by: str,
    valid_from: date | None = None,
    valid_until: date | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    provider_id = _validate_uuid(provider_id, "provider_id")
    business_tenant = _validate_uuid(business_tenant, "business_tenant")
    person_user_id = _validate_uuid(person_user_id, "person_user_id")
    declared_by = _validate_uuid(declared_by, "declared_by")
    person_role = _require_role(person_role)
    conflict_type = _require_conflict_type(conflict_type)
    description = _require_non_empty(description, "description")

    row = await db.fetchrow(
        """
        INSERT INTO conflict_declarations
            (provider_id, business_tenant, person_user_id, person_role, conflict_type, description,
             status, declared_by, valid_from, valid_until)
        VALUES ($1, $2, $3, $4, $5, $6, 'declared', $7, $8, $9)
        RETURNING *
        """,
        provider_id,
        business_tenant,
        person_user_id,
        person_role,
        conflict_type,
        description,
        declared_by,
        valid_from,
        valid_until,
    )
    await log_audit(
        db,
        user=user or {"sub": declared_by},
        action="conflict.declare",
        entity_type="conflict_declaration",
        entity_id=str(row["id"]),
        metadata={"provider_id": provider_id, "business_tenant": business_tenant, "person_user_id": person_user_id},
    )
    return _row_to_dict(row)


async def list_conflicts(
    db,
    *,
    provider_id: str,
    business_tenant: str | None = None,
    person_user_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    provider_id = _validate_uuid(provider_id, "provider_id")
    clauses = ["provider_id=$1"]
    args: list[Any] = [provider_id]
    if business_tenant:
        args.append(_validate_uuid(business_tenant, "business_tenant"))
        clauses.append(f"business_tenant=${len(args)}")
    if person_user_id:
        args.append(_validate_uuid(person_user_id, "person_user_id"))
        clauses.append(f"person_user_id=${len(args)}")
    if status:
        args.append(_require_status(status))
        clauses.append(f"status=${len(args)}")
    rows = await db.fetch(
        f"""
        SELECT * FROM conflict_declarations
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at DESC, id DESC
        """,
        *args,
    )
    return [_row_to_dict(row) for row in rows]


async def get_conflict(db, *, conflict_id: str, provider_id: str) -> dict[str, Any]:
    conflict_id = _validate_uuid(conflict_id, "conflict_id")
    provider_id = _validate_uuid(provider_id, "provider_id")
    row = await db.fetchrow("SELECT * FROM conflict_declarations WHERE id=$1 AND provider_id=$2", conflict_id, provider_id)
    if not row:
        raise HTTPException(404, "Conflict declaration not found")
    return _row_to_dict(row)


async def review_conflict(
    db,
    *,
    conflict_id: str,
    provider_id: str,
    reviewed_by: str,
    status: str,
    review_reason: str,
    user: dict | None = None,
) -> dict[str, Any]:
    conflict_id = _validate_uuid(conflict_id, "conflict_id")
    provider_id = _validate_uuid(provider_id, "provider_id")
    reviewed_by = _validate_uuid(reviewed_by, "reviewed_by")
    status = _require_status(status)
    if status not in {"under_review", "cleared", "blocked"}:
        raise HTTPException(400, "Review status must be under_review, cleared, or blocked")
    review_reason = _require_non_empty(review_reason, "review_reason")
    row = await db.fetchrow(
        """
        UPDATE conflict_declarations
        SET status=$3, reviewed_by=$4, review_reason=$5, updated_at=now()
        WHERE id=$1 AND provider_id=$2
        RETURNING *
        """,
        conflict_id,
        provider_id,
        status,
        reviewed_by,
        review_reason,
    )
    if not row:
        raise HTTPException(404, "Conflict declaration not found")
    await log_audit(db, user=user or {"sub": reviewed_by}, action="conflict.review", entity_type="conflict_declaration", entity_id=conflict_id, metadata={"status": status, "reason": review_reason})
    return _row_to_dict(row)


def _caller_can_override(caller: dict | None, overridden_by: str) -> bool:
    caller = caller or {}
    role = caller.get("role")
    return bool(caller.get("is_owner") or role in {"cb_admin", "admin", "platform_admin"} or str(caller.get("id") or caller.get("sub")) == str(overridden_by) and caller.get("can_override_conflicts"))


async def override_conflict(
    db,
    *,
    conflict_id: str,
    provider_id: str,
    overridden_by: str,
    override_reason: str,
    caller: dict | None = None,
) -> dict[str, Any]:
    conflict_id = _validate_uuid(conflict_id, "conflict_id")
    provider_id = _validate_uuid(provider_id, "provider_id")
    overridden_by = _validate_uuid(overridden_by, "overridden_by")
    override_reason = _require_non_empty(override_reason, "override_reason")
    if not _caller_can_override(caller, overridden_by):
        raise HTTPException(403, "Only provider owners or CB admins may override conflicts")

    current = await db.fetchrow("SELECT * FROM conflict_declarations WHERE id=$1 AND provider_id=$2", conflict_id, provider_id)
    if not current:
        raise HTTPException(404, "Conflict declaration not found")
    if current.get("status") == "cleared":
        raise HTTPException(409, "Cleared conflict does not require override")

    override = await db.fetchrow(
        """
        INSERT INTO conflict_overrides (declaration_id, overridden_by, override_reason)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        conflict_id,
        overridden_by,
        override_reason,
    )
    row = await db.fetchrow(
        """
        UPDATE conflict_declarations
        SET status='overridden', reviewed_by=$3, review_reason=$4, updated_at=now()
        WHERE id=$1 AND provider_id=$2
        RETURNING *
        """,
        conflict_id,
        provider_id,
        overridden_by,
        override_reason,
    )
    await log_audit(
        db,
        user=caller or {"sub": overridden_by},
        action="conflict.override",
        entity_type="conflict_declaration",
        entity_id=conflict_id,
        metadata={"override_id": str(override["id"]) if override else None, "reason": override_reason},
    )
    return _row_to_dict(row)


async def assert_no_unresolved_conflict(
    db,
    *,
    provider_id: str,
    business_tenant: str,
    person_user_id: str,
    action: str,
) -> None:
    provider_id = _validate_uuid(provider_id, "provider_id")
    business_tenant = _validate_uuid(business_tenant, "business_tenant")
    person_user_id = _validate_uuid(person_user_id, "person_user_id")
    row = await db.fetchrow(
        """
        SELECT id, status, provider_id
        FROM conflict_declarations
        WHERE provider_id=$1
          AND business_tenant=$2
          AND person_user_id=$3
          AND status IN ('declared','under_review','blocked')
          AND (valid_until IS NULL OR valid_until >= CURRENT_DATE)
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        provider_id,
        business_tenant,
        person_user_id,
    )
    if row:
        raise HTTPException(409, f"Unresolved conflict of interest blocks {action}")
