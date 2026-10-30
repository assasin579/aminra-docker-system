"""Certification-decision service enforcing independence before cert issue."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException

from services.audit_log import log_audit
from services.conflict_interest import assert_no_unresolved_conflict

FINAL_STATUSES = {"approved", "rejected"}


def _validate_uuid(value: str, field: str = "id") -> str:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(400, f"Invalid {field}")
    return str(value)


def _require_reason(reason: str) -> str:
    cleaned = (reason or "").strip()
    if not cleaned:
        raise HTTPException(400, "Decision reason is required")
    return cleaned


async def assert_provider_staff_user(db, *, user_id: str, provider_id: str, field: str = "reviewer_id") -> None:
    _validate_uuid(user_id, field)
    _validate_uuid(provider_id, "provider_id")
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
        str(user_id),
        str(provider_id),
    )
    if not row:
        raise HTTPException(404, "Provider staff user not found")


async def create_decision_case(
    db,
    *,
    submission_id: str,
    created_by: str,
    provider_id: str,
    audit_visit_id: str | None = None,
    reviewer_id: str | None = None,
    notes: str | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    _validate_uuid(submission_id, "submission_id")
    _validate_uuid(created_by, "created_by")
    _validate_uuid(provider_id, "provider_id")
    if audit_visit_id:
        _validate_uuid(audit_visit_id, "audit_visit_id")
    if reviewer_id:
        _validate_uuid(reviewer_id, "reviewer_id")
        await assert_provider_staff_user(db, user_id=reviewer_id, provider_id=provider_id, field="reviewer_id")

    submission = await db.fetchrow(
        """
        SELECT id, business_tenant, provider_id, auditor_id
        FROM submissions
        WHERE id=$1 AND provider_id=$2
        """,
        submission_id,
        provider_id,
    )
    if not submission:
        raise HTTPException(404, "Submission not found")
    if reviewer_id:
        if submission.get("auditor_id") and str(submission["auditor_id"]) == str(reviewer_id):
            raise HTTPException(403, "Reviewer cannot be assigned auditor")
        await assert_no_unresolved_conflict(
            db,
            provider_id=provider_id,
            business_tenant=str(submission["business_tenant"]),
            person_user_id=reviewer_id,
            action="certification_decision.review",
        )

    existing = await db.fetchrow(
        """
        SELECT id
        FROM certification_decisions
        WHERE submission_id=$1 AND provider_id=$2 AND status IN ('pending_review','approved')
        LIMIT 1
        """,
        submission_id,
        provider_id,
    )
    if existing:
        raise HTTPException(409, "Active certification decision already exists for submission")

    if audit_visit_id:
        visit = await db.fetchrow(
            """
            SELECT id, auditor_id
            FROM audit_visits
            WHERE id=$1 AND provider_id=$2 AND business_tenant=$3
            """,
            audit_visit_id,
            provider_id,
            submission["business_tenant"],
        )
        if not visit:
            raise HTTPException(404, "Audit visit not found")
        if reviewer_id and visit.get("auditor_id") and str(visit["auditor_id"]) == str(reviewer_id):
            raise HTTPException(403, "Reviewer cannot be audit visit auditor")

    try:
        row = await db.fetchrow(
            """
            INSERT INTO certification_decisions
                (submission_id, business_tenant, provider_id, audit_visit_id, created_by, reviewer_id, decision_notes, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending_review')
            RETURNING id, submission_id, business_tenant, provider_id, audit_visit_id, status, reviewer_id, created_by
            """,
            submission_id,
            submission["business_tenant"],
            submission["provider_id"],
            audit_visit_id,
            created_by,
            reviewer_id,
            notes,
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(409, "Active certification decision already exists for submission") from exc
        raise
    await log_audit(
        db,
        user=user or {"sub": created_by},
        action="certification_decision.create",
        entity_type="certification_decision",
        entity_id=str(row["id"]),
        metadata={"submission_id": submission_id, "audit_visit_id": audit_visit_id},
    )
    return dict(row)


async def get_decision_for_submission(
    db,
    *,
    submission_id: str,
    provider_id: str | None = None,
    business_tenant: str | None = None,
) -> dict[str, Any] | None:
    _validate_uuid(submission_id, "submission_id")
    if provider_id and business_tenant:
        raise HTTPException(400, "Use either provider_id or business_tenant scope")
    if provider_id:
        _validate_uuid(provider_id, "provider_id")
        row = await db.fetchrow(
            """
            SELECT * FROM certification_decisions
            WHERE submission_id=$1 AND provider_id=$2 AND status <> 'cancelled'
            ORDER BY created_at DESC, decided_at DESC NULLS LAST, id DESC LIMIT 1
            """,
            submission_id,
            provider_id,
        )
    elif business_tenant:
        _validate_uuid(business_tenant, "business_tenant")
        row = await db.fetchrow(
            """
            SELECT * FROM certification_decisions
            WHERE submission_id=$1 AND business_tenant=$2 AND status <> 'cancelled'
            ORDER BY created_at DESC, decided_at DESC NULLS LAST, id DESC LIMIT 1
            """,
            submission_id,
            business_tenant,
        )
    else:
        row = await db.fetchrow(
            """
            SELECT * FROM certification_decisions
            WHERE submission_id=$1 AND status <> 'cancelled'
            ORDER BY created_at DESC, decided_at DESC NULLS LAST, id DESC LIMIT 1
            """,
            submission_id,
        )
    return dict(row) if row else None


async def approve_decision(
    db,
    *,
    decision_id: str,
    decision_maker_id: str,
    provider_id: str,
    reason: str,
    notes: str | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    return await _finalize_decision(db, decision_id=decision_id, decision_maker_id=decision_maker_id, provider_id=provider_id, reason=reason, status="approved", notes=notes, user=user)


async def reject_decision(
    db,
    *,
    decision_id: str,
    decision_maker_id: str,
    provider_id: str,
    reason: str,
    notes: str | None = None,
    user: dict | None = None,
) -> dict[str, Any]:
    return await _finalize_decision(db, decision_id=decision_id, decision_maker_id=decision_maker_id, provider_id=provider_id, reason=reason, status="rejected", notes=notes, user=user)


async def _finalize_decision(
    db,
    *,
    decision_id: str,
    decision_maker_id: str,
    provider_id: str,
    reason: str,
    status: str,
    notes: str | None,
    user: dict | None,
) -> dict[str, Any]:
    _validate_uuid(decision_id, "decision_id")
    _validate_uuid(decision_maker_id, "decision_maker_id")
    _validate_uuid(provider_id, "provider_id")
    reason = _require_reason(reason)

    current = await db.fetchrow(
        """
        SELECT cd.*, s.auditor_id AS assigned_auditor_id, av.auditor_id AS visit_auditor_id
        FROM certification_decisions cd
        LEFT JOIN submissions s ON s.id = cd.submission_id
        LEFT JOIN audit_visits av ON av.id = cd.audit_visit_id
        WHERE cd.id=$1 AND cd.provider_id=$2 AND cd.status <> 'cancelled'
        """,
        decision_id,
        provider_id,
    )
    if not current:
        raise HTTPException(404, "Certification decision not found")
    if current["status"] in FINAL_STATUSES:
        raise HTTPException(409, "Certification decision is already final")
    if current.get("assigned_auditor_id") and str(current["assigned_auditor_id"]) == str(decision_maker_id):
        raise HTTPException(403, "Assigned auditor cannot approve or reject the certification decision")
    if current.get("visit_auditor_id") and str(current["visit_auditor_id"]) == str(decision_maker_id):
        raise HTTPException(403, "Audit visit auditor cannot approve or reject the certification decision")

    await assert_no_unresolved_conflict(
        db,
        provider_id=provider_id,
        business_tenant=str(current["business_tenant"]),
        person_user_id=decision_maker_id,
        action="certification_decision.approve",
    )

    row = await db.fetchrow(
        """
        UPDATE certification_decisions
        SET status=$2,
            decision_maker_id=$3,
            decision_reason=$4,
            decision_notes=COALESCE($5, decision_notes),
            decided_at=now(),
            updated_at=now()
        WHERE id=$1 AND provider_id=$6 AND status='pending_review'
        RETURNING *
        """,
        decision_id,
        status,
        decision_maker_id,
        reason,
        notes,
        provider_id,
    )
    if not row:
        raise HTTPException(409, "Certification decision is already final or no longer pending review")
    audit_action = "certification_decision.approve" if status == "approved" else "certification_decision.reject"
    await log_audit(
        db,
        user=user or {"sub": decision_maker_id},
        action=audit_action,
        entity_type="certification_decision",
        entity_id=decision_id,
        metadata={"status": status, "reason": reason},
    )
    return dict(row)


async def assert_certificate_issue_allowed(db, *, submission_id: str, provider_id: str) -> None:
    decision = await get_decision_for_submission(db, submission_id=submission_id, provider_id=provider_id)
    if not decision:
        raise HTTPException(409, "Approved certification decision required before certificate issue")
    if str(decision.get("provider_id")) != str(provider_id):
        raise HTTPException(403, "Certification decision provider scope mismatch")
    status = decision.get("status")
    if status == "approved":
        return
    if status == "rejected":
        raise HTTPException(409, "Rejected certification decision blocks certificate issue")
    raise HTTPException(409, "Approved certification decision required before certificate issue")
