"""Complaints and appeals service for CB trust controls."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from services.audit_log import log_audit
from services.conflict_interest import assert_no_unresolved_conflict

CASE_TYPES = {"complaint_service", "complaint_certified_client", "appeal_decision"}
SOURCES = {"business", "provider", "public", "internal"}
STATUSES = {"received", "acknowledged", "under_investigation", "decision_made", "closed", "rejected"}
TERMINAL_STATUSES = {"closed", "rejected"}
VALID_TRANSITIONS = {
    "received": {"acknowledged", "rejected"},
    "acknowledged": {"under_investigation", "rejected"},
    "under_investigation": {"decision_made", "rejected"},
    "decision_made": {"closed"},
    "closed": set(),
    "rejected": set(),
}


def _validate_uuid(value: str | UUID | None, field: str, *, required: bool = True) -> str | None:
    if value in (None, "") and not required:
        return None
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
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    return result


def _require_case_type(value: str) -> str:
    if value not in CASE_TYPES:
        raise HTTPException(400, "Invalid case_type")
    return value


def _require_source(value: str) -> str:
    if value not in SOURCES:
        raise HTTPException(400, "Invalid source")
    return value


def _require_status(value: str) -> str:
    if value not in STATUSES:
        raise HTTPException(400, "Invalid complaint status")
    return value


async def assert_provider_staff_user(db, *, owner_id: str, provider_id: str) -> None:
    owner_id = _validate_uuid(owner_id, "owner_id") or ""
    provider_id = _validate_uuid(provider_id, "provider_id") or ""
    row = await db.fetchrow(
        """
        SELECT id
        FROM users
        WHERE id=$1
          AND role='provider'
          AND (tenant_id=$2 OR id=$2)
          AND COALESCE(status::text, 'active') = 'active'
        LIMIT 1
        """,
        owner_id,
        provider_id,
    )
    if not row:
        raise HTTPException(404, "Provider staff user not found")


async def create_case(
    db,
    *,
    provider_id: str,
    case_type: str,
    source: str,
    title: str,
    description: str,
    submitted_by_user_id: str | None = None,
    business_tenant: str | None = None,
    certificate_id: str | None = None,
    submission_id: str | None = None,
    original_decision_id: str | None = None,
    due_at: datetime | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    provider_id = _validate_uuid(provider_id, "provider_id") or ""
    case_type = _require_case_type(case_type)
    source = _require_source(source)
    title = _require_non_empty(title, "title")
    description = _require_non_empty(description, "description")
    submitted_by_user_id = _validate_uuid(submitted_by_user_id, "submitted_by_user_id", required=False)
    business_tenant = _validate_uuid(business_tenant, "business_tenant", required=False)
    certificate_id = _validate_uuid(certificate_id, "certificate_id", required=False)
    submission_id = _validate_uuid(submission_id, "submission_id", required=False)
    original_decision_id = _validate_uuid(original_decision_id, "original_decision_id", required=False)

    if case_type == "appeal_decision" and not original_decision_id:
        raise HTTPException(400, "original_decision_id is required for appeal_decision")

    if original_decision_id:
        decision = await db.fetchrow(
            """
            SELECT id, provider_id, business_tenant, submission_id
            FROM certification_decisions
            WHERE id=$1 AND provider_id=$2
            """,
            original_decision_id,
            provider_id,
        )
        if not decision:
            raise HTTPException(404, "Original certification decision not found")
        decision_business_tenant = str(decision.get("business_tenant")) if decision.get("business_tenant") else None
        decision_submission_id = str(decision.get("submission_id")) if decision.get("submission_id") else None
        if business_tenant and decision_business_tenant and str(business_tenant) != decision_business_tenant:
            raise HTTPException(403, "Appeal business_tenant does not match original decision")
        if submission_id and decision_submission_id and str(submission_id) != decision_submission_id:
            raise HTTPException(400, "Appeal submission_id does not match original decision")
        business_tenant = business_tenant or decision_business_tenant
        submission_id = submission_id or decision_submission_id

    if submission_id:
        submission = await db.fetchrow(
            """
            SELECT id, provider_id, business_tenant
            FROM submissions
            WHERE id=$1 AND provider_id=$2
            """,
            submission_id,
            provider_id,
        )
        if not submission:
            raise HTTPException(404, "Submission not found")
        if business_tenant and str(submission.get("business_tenant")) != str(business_tenant):
            raise HTTPException(400, "Submission business_tenant mismatch")
        if not business_tenant and submission.get("business_tenant"):
            business_tenant = str(submission["business_tenant"])

    if certificate_id:
        certificate = await db.fetchrow(
            """
            SELECT id, issued_by, business_tenant, submission_id
            FROM halal_certificates
            WHERE id=$1 AND issued_by=$2
            """,
            certificate_id,
            provider_id,
        )
        if not certificate:
            raise HTTPException(404, "Certificate not found")
        if business_tenant and str(certificate.get("business_tenant")) != str(business_tenant):
            raise HTTPException(400, "Certificate business_tenant mismatch")
        if not business_tenant and certificate.get("business_tenant"):
            business_tenant = str(certificate["business_tenant"])
        if certificate.get("submission_id") and submission_id and str(certificate.get("submission_id")) != str(submission_id):
            raise HTTPException(400, "Certificate submission_id mismatch")

    row = await db.fetchrow(
        """
        INSERT INTO complaint_cases
            (provider_id, business_tenant, certificate_id, submission_id, case_type, source, status,
             title, description, submitted_by_user_id, original_decision_id, due_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'received', $7, $8, $9, $10, $11)
        RETURNING *
        """,
        provider_id,
        business_tenant,
        certificate_id,
        submission_id,
        case_type,
        source,
        title,
        description,
        submitted_by_user_id,
        original_decision_id,
        due_at,
    )
    await add_case_event(
        db,
        case_id=str(row["id"]),
        actor_user_id=submitted_by_user_id,
        event_type="case.created",
        notes="Case received",
        metadata={"case_type": case_type, "source": source},
        user=user or {"sub": submitted_by_user_id},
    )
    await log_audit(
        db,
        user=user or {"sub": submitted_by_user_id},
        action="complaint.create" if case_type != "appeal_decision" else "appeal.create",
        entity_type="complaint_case",
        entity_id=str(row["id"]),
        metadata={"provider_id": provider_id, "case_type": case_type},
    )
    return _row_to_dict(row)


async def list_cases(
    db,
    *,
    provider_id: str | None = None,
    business_tenant: str | None = None,
    assigned_owner_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if provider_id:
        args.append(_validate_uuid(provider_id, "provider_id"))
        clauses.append(f"provider_id=${len(args)}")
    if business_tenant:
        args.append(_validate_uuid(business_tenant, "business_tenant"))
        clauses.append(f"business_tenant=${len(args)}")
    if assigned_owner_id:
        args.append(_validate_uuid(assigned_owner_id, "assigned_owner_id"))
        clauses.append(f"assigned_owner_id=${len(args)}")
    if status:
        args.append(_require_status(status))
        clauses.append(f"status=${len(args)}")
    where = " AND ".join(clauses) if clauses else "1=0"
    rows = await db.fetch(
        f"""
        SELECT * FROM complaint_cases
        WHERE {where}
        ORDER BY created_at DESC, id DESC
        """,
        *args,
    )
    return [_row_to_dict(row) for row in rows]


async def get_case(db, *, case_id: str, provider_id: str | None = None, business_tenant: str | None = None) -> dict[str, Any]:
    case_id = _validate_uuid(case_id, "case_id") or ""
    clauses = ["id=$1"]
    args: list[Any] = [case_id]
    if provider_id:
        args.append(_validate_uuid(provider_id, "provider_id"))
        clauses.append(f"provider_id=${len(args)}")
    if business_tenant:
        args.append(_validate_uuid(business_tenant, "business_tenant"))
        clauses.append(f"business_tenant=${len(args)}")
    row = await db.fetchrow(f"SELECT * FROM complaint_cases WHERE {' AND '.join(clauses)}", *args)
    if not row:
        raise HTTPException(404, "Complaint case not found")
    return _row_to_dict(row)


async def assert_case_handler_independent(db, *, case_id: str, provider_id: str, owner_id: str) -> None:
    case_id = _validate_uuid(case_id, "case_id") or ""
    provider_id = _validate_uuid(provider_id, "provider_id") or ""
    owner_id = _validate_uuid(owner_id, "owner_id") or ""
    row = await db.fetchrow(
        """
        SELECT cc.*, cd.decision_maker_id AS original_decision_maker_id,
               cd.audit_visit_id AS original_audit_visit_id,
               av.auditor_id AS audit_visit_auditor_id
        FROM complaint_cases cc
        LEFT JOIN certification_decisions cd ON cd.id = cc.original_decision_id
        LEFT JOIN audit_visits av ON av.id = cd.audit_visit_id
        WHERE cc.id=$1 AND cc.provider_id=$2
        """,
        case_id,
        provider_id,
    )
    if not row:
        raise HTTPException(404, "Complaint case not found")
    if row.get("case_type") == "appeal_decision":
        if not row.get("original_decision_id"):
            raise HTTPException(400, "Appeal case requires original_decision_id")
        if row.get("original_decision_maker_id") and str(row["original_decision_maker_id"]) == str(owner_id):
            raise HTTPException(403, "Appeal owner cannot be original decision maker")
        if row.get("audit_visit_auditor_id") and str(row["audit_visit_auditor_id"]) == str(owner_id):
            raise HTTPException(403, "Appeal owner cannot be linked audit auditor")
    if row.get("business_tenant"):
        await assert_no_unresolved_conflict(
            db,
            provider_id=provider_id,
            business_tenant=str(row["business_tenant"]),
            person_user_id=owner_id,
            action="complaint.assign",
        )


async def assign_case_owner(
    db,
    *,
    case_id: str,
    provider_id: str,
    owner_id: str,
    actor_user_id: str,
    notes: str | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    case_id = _validate_uuid(case_id, "case_id") or ""
    provider_id = _validate_uuid(provider_id, "provider_id") or ""
    owner_id = _validate_uuid(owner_id, "owner_id") or ""
    actor_user_id = _validate_uuid(actor_user_id, "actor_user_id") or ""
    await assert_provider_staff_user(db, owner_id=owner_id, provider_id=provider_id)
    await assert_case_handler_independent(db, case_id=case_id, provider_id=provider_id, owner_id=owner_id)
    row = await db.fetchrow(
        """
        UPDATE complaint_cases
        SET assigned_owner_id=$3, updated_at=now()
        WHERE id=$1 AND provider_id=$2 AND status NOT IN ('closed','rejected')
        RETURNING *
        """,
        case_id,
        provider_id,
        owner_id,
    )
    if not row:
        raise HTTPException(404, "Complaint case not found or terminal")
    await add_case_event(db, case_id=case_id, actor_user_id=actor_user_id, event_type="case.assigned", notes=notes, metadata={"owner_id": owner_id}, user=user)
    await log_audit(db, user=user or {"sub": actor_user_id}, action="complaint.assign", entity_type="complaint_case", entity_id=case_id, metadata={"owner_id": owner_id})
    return _row_to_dict(row)


async def transition_case(
    db,
    *,
    case_id: str,
    provider_id: str,
    actor_user_id: str,
    to_status: str,
    decision_summary: str | None = None,
    closure_reason: str | None = None,
    notes: str | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    case_id = _validate_uuid(case_id, "case_id") or ""
    provider_id = _validate_uuid(provider_id, "provider_id") or ""
    actor_user_id = _validate_uuid(actor_user_id, "actor_user_id") or ""
    to_status = _require_status(to_status)
    current = await db.fetchrow("SELECT * FROM complaint_cases WHERE id=$1 AND provider_id=$2", case_id, provider_id)
    if not current:
        raise HTTPException(404, "Complaint case not found")
    from_status = current["status"]
    if from_status in TERMINAL_STATUSES:
        raise HTTPException(409, "Complaint case is terminal")
    if to_status not in VALID_TRANSITIONS.get(from_status, set()):
        raise HTTPException(409, f"Invalid status transition {from_status}->{to_status}")
    if to_status == "decision_made":
        decision_summary = _require_non_empty(decision_summary, "decision_summary")
    if to_status == "closed":
        closure_reason = _require_non_empty(closure_reason, "closure_reason")

    row = await db.fetchrow(
        """
        UPDATE complaint_cases
        SET status=$3,
            decision_summary=COALESCE($4, decision_summary),
            closure_reason=COALESCE($5, closure_reason),
            closed_at=CASE WHEN $3='closed' THEN now() ELSE closed_at END,
            updated_at=now()
        WHERE id=$1 AND provider_id=$2
        RETURNING *
        """,
        case_id,
        provider_id,
        to_status,
        decision_summary,
        closure_reason,
    )
    if not row:
        raise HTTPException(404, "Complaint case not found")
    await add_case_event(db, case_id=case_id, actor_user_id=actor_user_id, event_type="case.transition", from_status=from_status, to_status=to_status, notes=notes, metadata={}, user=user)
    await log_audit(db, user=user or {"sub": actor_user_id}, action="complaint.transition", entity_type="complaint_case", entity_id=case_id, metadata={"from_status": from_status, "to_status": to_status})
    return _row_to_dict(row)


async def add_case_event(
    db,
    *,
    case_id: str,
    actor_user_id: str | None,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    case_id = _validate_uuid(case_id, "case_id") or ""
    actor_user_id = _validate_uuid(actor_user_id, "actor_user_id", required=False)
    event_type = _require_non_empty(event_type, "event_type")
    if from_status:
        from_status = _require_status(from_status)
    if to_status:
        to_status = _require_status(to_status)
    row = await db.fetchrow(
        """
        INSERT INTO complaint_case_events
            (case_id, actor_user_id, event_type, from_status, to_status, notes, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        RETURNING *
        """,
        case_id,
        actor_user_id,
        event_type,
        from_status,
        to_status,
        notes,
        json.dumps(metadata or {}),
    )
    return _row_to_dict(row)
