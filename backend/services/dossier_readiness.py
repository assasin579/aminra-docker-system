from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


_APPROVED_DOCUMENT_STATUSES = {"approved"}
_REJECTED_DOCUMENT_STATUSES = {"rejected"}
_OPEN_NCR_STATUSES = {"open", "in_review"}
_NON_BLOCKING_NCR_SEVERITIES = {"minor"}


def _requirements_blocked_result(
    dossier: dict[str, Any], *, state: str, action: str, reason: str,
    requirement_slots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return UNKNOWN rather than a fabricated zero when requirements are unresolved."""
    return {
        "dossier_id": str(dossier["id"]),
        "tenant_id": str(dossier["tenant_id"]),
        "status": _as_str(dossier.get("status")),
        "title": dossier.get("title"),
        "requirements_version_id": _as_str(dossier.get("requirements_version_id")),
        "requirements_binding_status": _as_str(dossier.get("requirements_binding_status")) or "unknown",
        "state": state,
        "readiness_percent": None,
        "certificate_issue_blocked": True,
        "safe_public_trace_available": False,
        "next_action": action,
        "next_actor_role": "platform_admin",
        "next_action_owner_role": "platform_admin",
        "due_date": None,
        "required_documents": [],
        "requirement_slots": requirement_slots or [],
        "missing_required_documents": [],
        "unreviewed_documents": [],
        "rejected_documents": [],
        "open_ncrs": [],
        "blocking_ncrs": [],
        "certification_decision": {"id": None, "status": None, "reason": None},
        "submission_round": None,
        "certificate": {"id": None, "cert_number": None, "status": None},
        "blocking_reasons": [{"code": reason}],
    }


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _document_is_approved(row: dict[str, Any]) -> bool:
    approval_status = _as_str(row.get("approval_status"))
    if approval_status is not None:
        return approval_status in _APPROVED_DOCUMENT_STATUSES
    return _as_str(row.get("status")) in _APPROVED_DOCUMENT_STATUSES


def _document_is_rejected(row: dict[str, Any]) -> bool:
    approval_status = _as_str(row.get("approval_status"))
    status_value = _as_str(row.get("status"))
    return approval_status in _REJECTED_DOCUMENT_STATUSES or status_value in _REJECTED_DOCUMENT_STATUSES


def _review_reason(row: dict[str, Any]) -> str | None:
    for key in ("review_reason", "rejection_reason", "reason"):
        if row.get(key):
            return str(row[key])
    evaluation = row.get("evaluation_result")
    if isinstance(evaluation, dict):
        for key in ("review_reason", "rejection_reason", "reason"):
            if evaluation.get(key):
                return str(evaluation[key])
    return None


def _doc_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": str(row["id"]),
        "doc_type": row.get("doc_type"),
        "status": _as_str(row.get("approval_status") or row.get("status")),
        "compliance_score": row.get("compliance_score"),
    }


def _ncr_public(row: dict[str, Any]) -> dict[str, Any]:
    deadline = row.get("deadline")
    return {
        "id": str(row["id"]),
        "status": _as_str(row.get("status")),
        "severity": _as_str(row.get("severity")),
        "description": row.get("description"),
        "corrective_action": row.get("corrective_action"),
        "deadline": deadline.isoformat() if deadline is not None and hasattr(deadline, "isoformat") else deadline,
    }


async def compute_dossier_readiness(db, *, dossier_id: str, tenant_id: str) -> dict[str, Any]:
    """Return source-of-truth readiness for one tenant-scoped certification dossier.

    This deliberately treats AI evaluation/compliance score as evidence only. A
    required document is ready only when an explicit reviewer/approval status is
    approved. The response is shaped for the future dossier command page.
    """

    dossier = await db.fetchrow(
        """
        SELECT id, tenant_id, standard_type_id, requirements_version_id,
               requirements_binding_status, status, title
          FROM dossiers
         WHERE id = $1 AND tenant_id = $2 AND status != 'cancelled'
        """,
        str(dossier_id),
        str(tenant_id),
    )
    if not dossier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier not found")

    binding_status = _as_str(dossier.get("requirements_binding_status")) or "unknown"
    if binding_status == "unconfigured":
        return _requirements_blocked_result(
            _dict(dossier), state="requirements_unconfigured", action="publish_requirements_version",
            reason="requirements_version_not_published",
        )
    if binding_status == "unknown" or not dossier.get("requirements_version_id"):
        return _requirements_blocked_result(
            _dict(dossier), state="requirements_unknown", action="resolve_requirements_binding",
            reason="requirements_version_unknown_no_backfill",
        )

    slot_rows = await db.fetch(
        "SELECT doc_type, required, display_order FROM standard_requirement_version_slots "
        "WHERE requirements_version_id = $1 ORDER BY display_order, doc_type",
        dossier["requirements_version_id"],
    )
    requirement_slots = [
        {"doc_type": str(row["doc_type"]), "required": bool(row["required"]), "display_order": int(row["display_order"])}
        for row in slot_rows
    ]
    required_doc_types = [slot["doc_type"] for slot in requirement_slots if slot["required"]]
    if not requirement_slots:
        return _requirements_blocked_result(
            _dict(dossier), state="requirements_empty", action="configure_requirement_slots",
            reason="published_requirements_have_no_slots",
        )
    if not required_doc_types:
        return _requirements_blocked_result(
            _dict(dossier), state="requirements_no_required_slots", action="configure_required_slots",
            reason="requirements_configured_without_required_slots", requirement_slots=requirement_slots,
        )

    submission = await db.fetchrow(
        """
        SELECT id, status, provider_id, requirements_version_id, document_ids, revision_round
          FROM submissions
         WHERE business_tenant = $1
           AND requirements_version_id = $3
           AND EXISTS (
               SELECT 1 FROM documents d
                WHERE d.id = ANY(submissions.document_ids)
                  AND d.tenant_id = $1
                  AND (d.dossier_id = $2 OR EXISTS (
                      SELECT 1 FROM dossier_document_attachments a
                       WHERE a.dossier_id=$2 AND a.document_id=d.id
                         AND a.requirements_version_id=$3 AND a.doc_type=d.doc_type
                  ))
           )
         ORDER BY updated_at DESC NULLS LAST, submitted_at DESC NULLS LAST, id DESC
         LIMIT 1
        """,
        str(tenant_id), str(dossier_id), dossier["requirements_version_id"],
    )
    submitted_document_ids = list(submission.get("document_ids") or []) if submission else None

    document_rows = await db.fetch(
        """
        SELECT d.id, d.doc_type, d.status, d.approval_status, d.compliance_score, d.evaluation_result,
               COALESCE(a.document_version_number, d.version_number) AS version_number
          FROM documents d
          LEFT JOIN dossier_document_attachments a
            ON a.dossier_id=$1 AND a.document_id=d.id
           AND a.requirements_version_id=(SELECT requirements_version_id FROM dossiers WHERE id=$1)
           AND a.doc_type=d.doc_type
         WHERE d.tenant_id = $2
           AND d.id = ANY(COALESCE(
               $3::uuid[],
               ARRAY(SELECT a.document_id FROM dossier_document_attachments a
                      WHERE a.dossier_id=$1
                        AND a.requirements_version_id=(SELECT requirements_version_id FROM dossiers WHERE id=$1))
           ))
           AND (d.dossier_id=$1 OR a.document_id IS NOT NULL)
         ORDER BY d.uploaded_at DESC, d.id ASC
        """,
        str(dossier_id),
        str(tenant_id),
        submitted_document_ids,
    )
    documents = [_dict(row) for row in document_rows]

    latest_by_type: dict[str, dict[str, Any]] = {}
    for row in documents:
        doc_type = row.get("doc_type")
        if doc_type and str(doc_type) not in latest_by_type:
            latest_by_type[str(doc_type)] = row

    active_round = int(submission.get("revision_round") or 0) + 1 if submission else None
    submission_id = str(submission["id"]) if submission else None
    bound_version_id = str(dossier["requirements_version_id"])
    for slot in requirement_slots:
        slot["requirements_version_id"] = bound_version_id
        slot["submission_id"] = submission_id
        slot["submitted_round"] = active_round
        row = latest_by_type.get(slot["doc_type"])
        slot["evidence_document_id"] = str(row["id"]) if row else None
        slot["evidence_version"] = row.get("version_number") if row else None
        if row is None:
            slot["state"] = "missing_required" if slot["required"] else "optional_not_submitted"
        elif _document_is_approved(row):
            slot["state"] = "approved"
        elif _document_is_rejected(row):
            slot["state"] = "revision_required"
        else:
            slot["state"] = "pending_review"

    missing_required_documents = [doc_type for doc_type in required_doc_types if doc_type not in latest_by_type]
    unreviewed_documents: list[dict[str, Any]] = []
    rejected_documents: list[dict[str, Any]] = []
    approved_required = 0
    blocking_reasons: list[dict[str, Any]] = []

    for doc_type in required_doc_types:
        row = latest_by_type.get(doc_type)
        if row is None:
            blocking_reasons.append({"code": "missing_required_document", "doc_type": doc_type})
            continue
        if _document_is_approved(row):
            approved_required += 1
            continue
        if _document_is_rejected(row):
            rejected = {
                "doc_type": doc_type,
                "document_id": str(row["id"]),
                "reason": _review_reason(row),
            }
            rejected_documents.append(rejected)
            blocking_reasons.append({"code": "rejected_document", **rejected})
            continue
        public_doc = _doc_public(row)
        unreviewed_documents.append(public_doc)
        blocking_reasons.append({"code": "document_not_approved", **public_doc})

    ncr_rows = await db.fetch(
        """
        SELECT n.id, n.status, n.severity, n.description, n.corrective_action, n.deadline
          FROM audit_ncr n
          JOIN audit_visits v ON v.id = n.visit_id
         WHERE v.business_tenant = $1 AND n.status IN ('open', 'in_review')
           AND EXISTS (
               SELECT 1
                 FROM submissions s
                 JOIN documents d ON d.id = ANY(s.document_ids)
                WHERE s.business_tenant = v.business_tenant
                  AND s.provider_id = v.provider_id
                  AND s.requirements_version_id = $3
                  AND s.id = $4
                  AND d.dossier_id = $2
                  AND d.tenant_id = $1
           )
         ORDER BY n.deadline NULLS LAST, n.created_at DESC
        """,
        str(tenant_id),
        str(dossier_id),
        dossier["requirements_version_id"],
        submission["id"] if submission else None,
    )
    open_ncrs = [_ncr_public(_dict(row)) for row in ncr_rows if _as_str(row.get("status")) in _OPEN_NCR_STATUSES]
    # Per the product plan, critical/major findings block a decision. Minor
    # findings remain visible; missing/unknown severity fails closed.
    blocking_ncrs = [
        ncr for ncr in open_ncrs
        if (ncr.get("severity") or "").lower() not in _NON_BLOCKING_NCR_SEVERITIES
    ]
    for ncr in blocking_ncrs:
        blocking_reasons.append({"code": "open_ncr", **ncr})

    decision = None
    if submission:
        decision = await db.fetchrow(
            """
            SELECT id, status, decision_reason
              FROM certification_decisions
             WHERE submission_id = $1
               AND business_tenant = $2
               AND provider_id = $3
               AND submitted_round = $4
               AND requirements_version_id IS NOT DISTINCT FROM $5
             ORDER BY decided_at DESC NULLS LAST, created_at DESC, id DESC
             LIMIT 1
            """,
            str(submission["id"]),
            str(tenant_id),
            str(submission["provider_id"]),
            int(submission.get("revision_round") or 0) + 1,
            submission.get("requirements_version_id"),
        )
    decision_status = _as_str(decision.get("status")) if decision else None
    document_or_ncr_blocked = bool(
        missing_required_documents
        or unreviewed_documents
        or rejected_documents
        or blocking_ncrs
    )
    if not document_or_ncr_blocked and decision_status != "approved":
        blocking_reasons.append({
            "code": "certification_decision_not_approved",
            "status": decision_status or "missing",
        })

    certificate = None
    if decision_status == "approved":
        certificate = await db.fetchrow(
            """
            SELECT id, cert_number, status, issue_date, expiry_date
              FROM halal_certificates
             WHERE submission_id = $1 AND business_tenant = $2
               AND status = 'active'
               AND issue_date <= CURRENT_DATE
               AND expiry_date >= CURRENT_DATE
             ORDER BY issue_date DESC
             LIMIT 1
            """,
            str(submission["id"]),
            str(tenant_id),
        )

    document_percent = int((approved_required / len(required_doc_types)) * 50) if required_doc_types else 0
    documents_complete = bool(required_doc_types) and approved_required == len(required_doc_types)
    audit_percent = 25 if documents_complete and not blocking_ncrs else 0
    decision_percent = 25 if not document_or_ncr_blocked and decision_status == "approved" and certificate else 0
    readiness_percent = min(100, document_percent + audit_percent + decision_percent)

    if missing_required_documents:
        state = "requirements_pending"
        next_action = "upload_required_documents"
        next_actor_role = "business"
    elif rejected_documents:
        state = "documents_rejected"
        next_action = "replace_rejected_documents"
        next_actor_role = "business"
    elif unreviewed_documents:
        state = "documents_in_review"
        next_action = "review_uploaded_documents"
        next_actor_role = "reviewer"
    elif any(ncr["status"] == "open" for ncr in blocking_ncrs):
        state = "ncr_open"
        next_action = "submit_capa_evidence"
        next_actor_role = "business"
    elif any(ncr["status"] == "in_review" for ncr in blocking_ncrs):
        state = "capa_in_review"
        next_action = "verify_capa_evidence"
        next_actor_role = "auditor"
    elif decision_status != "approved":
        state = "ready_for_decision"
        next_action = "finalize_certification_decision"
        next_actor_role = "decision_maker"
    elif not certificate:
        state = "certificate_pending"
        next_action = "issue_certificate_artifact"
        next_actor_role = "provider"
        blocking_reasons.append({"code": "active_certificate_missing"})
    else:
        state = "certified"
        next_action = "certification_ready"
        next_actor_role = "provider"

    due_dates = [ncr["deadline"] for ncr in blocking_ncrs if ncr.get("deadline") is not None]
    due_date = min(due_dates) if due_dates else None
    if due_date is not None and hasattr(due_date, "isoformat"):
        due_date = due_date.isoformat()

    certificate_issue_blocked = bool(blocking_reasons)
    safe_public_trace_available = bool(certificate and not certificate_issue_blocked)

    return {
        "dossier_id": str(dossier["id"]),
        "tenant_id": str(dossier["tenant_id"]),
        "status": _as_str(dossier.get("status")),
        "title": dossier.get("title"),
        "requirements_version_id": str(dossier["requirements_version_id"]),
        "requirements_binding_status": binding_status,
        "state": state,
        "readiness_percent": readiness_percent,
        "certificate_issue_blocked": certificate_issue_blocked,
        "safe_public_trace_available": safe_public_trace_available,
        "next_action": next_action,
        "next_actor_role": next_actor_role,
        "next_action_owner_role": next_actor_role,
        "due_date": due_date,
        "required_documents": required_doc_types,
        "requirement_slots": requirement_slots,
        "missing_required_documents": missing_required_documents,
        "unreviewed_documents": unreviewed_documents,
        "rejected_documents": rejected_documents,
        "open_ncrs": open_ncrs,
        "blocking_ncrs": blocking_ncrs,
        "certification_decision": {
            "id": str(decision["id"]) if decision else None,
            "status": decision_status,
            "reason": decision.get("decision_reason") if decision else None,
        },
        "submission_round": ({
            "id": str(submission["id"]),
            "status": _as_str(submission.get("status")),
            "requirements_version_id": str(submission["requirements_version_id"]),
            "submitted_round": int(submission.get("revision_round") or 0) + 1,
            "document_ids": [str(document_id) for document_id in (submission.get("document_ids") or [])],
        } if submission else None),
        "certificate": {
            "id": str(certificate["id"]) if certificate else None,
            "cert_number": certificate.get("cert_number") if certificate else None,
            "status": certificate.get("status") if certificate else None,
        },
        "blocking_reasons": blocking_reasons,
    }
