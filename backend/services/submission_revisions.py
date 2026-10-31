"""Submission revisions cycle service.

Handles the round-by-round revision flow:
    Provider review → request_revision(...) → status=revision_required
                                            → submission_revision_requests row
                                            → notify business
    Business → resubmit(...) → status=reviewing, revision_round += 1
                             → mark request resolved, link to new docs
                             → notify provider

Append-only revision history; full audit trail.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import asyncpg

log = logging.getLogger("aminra.submission_revisions")


# ── Errors ──────────────────────────────────────────────────────────────────


class SubmissionNotFound(Exception): ...


class InvalidStateTransition(Exception): ...


class NoRevisionPending(Exception): ...


# ── Data ────────────────────────────────────────────────────────────────────

ALLOWED_FROM_STATUSES_FOR_REVISION = {"reviewing", "returned"}
ALLOWED_FROM_STATUSES_FOR_RESUBMIT = {"revision_required"}


@dataclass
class DocumentFeedback:
    """One issue flagged on a specific document — surfaces in business UI."""

    document_id: str  # UUID of the document with issue
    issue: str  # short description ("Missing JAKIM seal")
    severity: str = "minor"  # minor | major | critical
    suggestion: str = ""  # optional fix suggestion

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "issue": self.issue,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


@dataclass
class RevisionRequest:
    submission_id: str
    round: int
    requester_id: str
    requester_name: str
    feedback: str
    document_feedback: list[DocumentFeedback]
    requested_at: datetime
    resolved_at: Optional[datetime] = None


# ── Provider: request a revision ────────────────────────────────────────────


async def request_revision(
    db: asyncpg.Connection,
    *,
    submission_id: str,
    requester_id: str,
    requester_name: str,
    feedback: str,
    document_feedback: list[DocumentFeedback] | None = None,
) -> dict:
    """Provider asks the business to fix issues. Submission status flips to
    `revision_required`; we record this round in submission_revision_requests.

    Idempotent in the sense that re-calling on a submission already in
    revision_required raises InvalidStateTransition (use update_revision_request
    if you want to amend the feedback in the same round).
    """
    if not feedback.strip():
        raise ValueError("feedback cannot be empty")

    sub = await db.fetchrow(
        "SELECT id, status, revision_round, business_tenant, requirements_version_id, requirements_binding_status, document_ids FROM submissions WHERE id = $1",
        submission_id,
    )
    if sub is None:
        raise SubmissionNotFound(submission_id)
    if sub["status"] not in ALLOWED_FROM_STATUSES_FOR_REVISION:
        raise InvalidStateTransition(
            f"can't request revision from status={sub['status']!r} (allowed: {ALLOWED_FROM_STATUSES_FOR_REVISION})"
        )

    new_round = (sub["revision_round"] or 0) + 1
    doc_feedback_json = json.dumps([df.to_dict() for df in (document_feedback or [])])

    async with db.transaction():
        updated = await db.fetchrow(
            """
            UPDATE submissions
               SET status = 'revision_required',
                   revision_round = $1,
                   revision_requested_at = NOW(),
                   updated_at = NOW()
             WHERE id = $2 AND status = $3 AND COALESCE(revision_round, 0) = $4
            RETURNING id
            """,
            new_round,
            submission_id,
            sub["status"],
            sub["revision_round"] or 0,
        )
        if updated is None:
            raise InvalidStateTransition("submission state changed before revision request")
        request_row = await db.fetchrow(
            """
            INSERT INTO submission_revision_requests
                (submission_id, round, requester_id, requester_name, feedback, document_feedback, requirements_version_id, submitted_document_ids, submitted_round)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::uuid[], $9)
            RETURNING id, requested_at
            """,
            submission_id,
            new_round,
            requester_id,
            requester_name,
            feedback,
            doc_feedback_json,
            sub.get("requirements_version_id"),
            list(sub.get("document_ids") or []),
            new_round,
        )

    log.info("[revisions] submission=%s round=%d by=%s", submission_id, new_round, requester_id)
    return {
        "request_id": str(request_row["id"]),
        "submission_id": submission_id,
        "round": new_round,
        "requested_at": request_row["requested_at"].isoformat(),
        "tenant_id": str(sub["business_tenant"]),
    }


# ── Business: resubmit ─────────────────────────────────────────────────────


async def resubmit(
    db: asyncpg.Connection,
    *,
    submission_id: str,
    new_document_ids: list[str] | None = None,
    business_notes: str = "",
) -> dict:
    """Business says 'I've fixed the issues, please review again'.

    - Status flips back to `reviewing`
    - revision_resubmitted_at stamped
    - Latest revision request marked resolved
    - Optionally swap document_ids (e.g., new versions of fixed docs)
    """
    sub = await db.fetchrow(
        """
        SELECT id, status, revision_round, revision_resubmitted_at, updated_at,
               business_tenant, provider_id, document_ids, dossier_id,
               requirements_version_id, requirements_binding_status
        FROM submissions WHERE id = $1
        """,
        submission_id,
    )
    if sub is None:
        raise SubmissionNotFound(submission_id)

    pending = await db.fetchrow(
        """
        SELECT id FROM submission_revision_requests
         WHERE submission_id = $1 AND resolved_at IS NULL
         ORDER BY round DESC LIMIT 1
        """,
        submission_id,
    )

    # Legacy retry path for clients without an Idempotency-Key: after an
    # explicit resubmit has committed, a repeated request must not create a
    # second round or repeat notification/audit side effects. Replacement
    # uploads do not resolve requests or enter this state.
    if sub["status"] == "reviewing" and pending is None and sub["revision_round"] > 0:
        log.info(
            "[revisions] resubmit no-op submission=%s — already explicitly resubmitted",
            submission_id,
        )
        return {
            "submission_id": submission_id,
            "round_resolved": sub["revision_round"],
            "resubmitted_at": (
                sub.get("revision_resubmitted_at") or sub.get("updated_at")
            ).isoformat() if (sub.get("revision_resubmitted_at") or sub.get("updated_at")) else None,
            "provider_id": str(sub["provider_id"]),
            "noop": True,
        }

    if sub["status"] not in ALLOWED_FROM_STATUSES_FOR_RESUBMIT:
        raise InvalidStateTransition(
            f"can't resubmit from status={sub['status']!r} (allowed: {ALLOWED_FROM_STATUSES_FOR_RESUBMIT})"
        )

    if pending is None:
        raise NoRevisionPending(submission_id)

    new_docs_param = [str(d) for d in new_document_ids] if new_document_ids is not None else None
    if new_docs_param is not None:
        if not new_docs_param or len(set(new_docs_param)) != len(new_docs_param):
            raise InvalidStateTransition("resubmission evidence must contain unique document versions")
        if sub.get("dossier_id"):
            dossier_id = sub["dossier_id"]
        else:
            current_dossiers = await db.fetch(
                "SELECT DISTINCT dossier_id FROM documents WHERE id = ANY($1::uuid[]) AND tenant_id = $2",
                list(sub.get("document_ids") or []),
                sub["business_tenant"],
            )
            dossier_ids = {row["dossier_id"] for row in current_dossiers if row["dossier_id"] is not None}
            if len(dossier_ids) != 1 or len(current_dossiers) != 1:
                raise InvalidStateTransition("cannot establish one canonical dossier for the submitted evidence")
            dossier_id = next(iter(dossier_ids))
        dossier = await db.fetchrow(
            "SELECT id, requirements_version_id, requirements_binding_status FROM dossiers WHERE id=$1 AND tenant_id=$2",
            dossier_id,
            sub["business_tenant"],
        )
        if not dossier:
            raise InvalidStateTransition("resubmission dossier is not owned by the canonical business")
        binding_status = sub.get("requirements_binding_status") or "unknown"
        if binding_status == "bound":
            if not sub.get("requirements_version_id") or dossier.get("requirements_binding_status") != "bound" or dossier.get("requirements_version_id") != sub.get("requirements_version_id"):
                raise InvalidStateTransition("submission requirements version does not match its bound dossier")
        if sub.get("dossier_id") and (sub.get("requirements_binding_status") or "unknown") == "bound":
            selected_docs = await db.fetch(
                """SELECT d.id, a.dossier_id, d.tenant_id, a.doc_type, a.document_version_number AS version_number
                     FROM dossier_document_attachments a
                     JOIN documents d ON d.id=a.document_id AND d.tenant_id=$2 AND d.doc_type=a.doc_type
                    WHERE a.dossier_id=$3 AND a.requirements_version_id=$4
                      AND a.document_id = ANY($1::uuid[])""",
                new_docs_param, sub["business_tenant"], dossier_id, sub["requirements_version_id"],
            )
        else:
            selected_docs = await db.fetch(
                "SELECT id, dossier_id, tenant_id, doc_type, version_number FROM documents WHERE id = ANY($1::uuid[]) AND tenant_id = $2 AND dossier_id = $3",
                new_docs_param, sub["business_tenant"], dossier_id,
            )
        if len(selected_docs) != len(new_docs_param):
            raise InvalidStateTransition("each replacement document version must belong to the same business and dossier")
        if binding_status == "bound":
            slots = await db.fetch(
                "SELECT doc_type FROM standard_requirement_version_slots WHERE requirements_version_id = $1",
                sub["requirements_version_id"],
            )
            allowed_doc_types = {str(slot["doc_type"]) for slot in slots}
            if not allowed_doc_types or any(doc.get("doc_type") not in allowed_doc_types for doc in selected_docs):
                raise InvalidStateTransition("replacement document type is not mapped by the bound requirements version")

    async with db.transaction():
        if new_docs_param is not None:
            updated = await db.fetchrow(
                """
                UPDATE submissions
                   SET status = 'reviewing',
                       document_ids = $1::uuid[],
                       notes = COALESCE(NULLIF($2, ''), notes),
                       revision_resubmitted_at = NOW(),
                       updated_at = NOW()
                 WHERE id = $3 AND status = $4 AND COALESCE(revision_round, 0) = $5
                RETURNING id, revision_resubmitted_at
                """,
                new_docs_param,
                business_notes,
                submission_id,
                sub["status"],
                sub["revision_round"] or 0,
            )
        else:
            updated = await db.fetchrow(
                """
                UPDATE submissions
                   SET status = 'reviewing',
                       notes = COALESCE(NULLIF($1, ''), notes),
                       revision_resubmitted_at = NOW(),
                       updated_at = NOW()
                 WHERE id = $2 AND status = $3 AND COALESCE(revision_round, 0) = $4
                RETURNING id, revision_resubmitted_at
                """,
                business_notes,
                submission_id,
                sub["status"],
                sub["revision_round"] or 0,
            )
        if updated is None:
            raise InvalidStateTransition("submission state changed before resubmission")
        resolved = await db.fetchrow(
            """
            UPDATE submission_revision_requests
               SET resolved_at = NOW(),
                   business_response = NULLIF($2, '')
             WHERE id = $1 AND resolved_at IS NULL
            RETURNING id
            """,
            pending["id"],
            business_notes,
        )
        if resolved is None:
            raise NoRevisionPending(submission_id)

    log.info("[revisions] resubmit submission=%s round=%d", submission_id, sub["revision_round"])
    return {
        "submission_id": submission_id,
        "round_resolved": sub["revision_round"],
        "resubmitted_at": updated["revision_resubmitted_at"].isoformat(),
        "provider_id": str(sub["provider_id"]),
    }


# ── Read API ───────────────────────────────────────────────────────────────


async def list_revision_history(
    db: asyncpg.Connection,
    submission_id: str,
) -> list[dict]:
    """Return all revision rounds for a submission (newest first), with
    document_feedback parsed."""
    rows = await db.fetch(
        """
        SELECT id, round, requester_id, requester_name, feedback,
               document_feedback, requested_at, resolved_at, business_response,
               requirements_version_id, submitted_document_ids, submitted_round
        FROM submission_revision_requests
        WHERE submission_id = $1
        ORDER BY round DESC
        """,
        submission_id,
    )
    tenant_id = await db.fetchval(
        "SELECT business_tenant FROM submissions WHERE id = $1", submission_id
    )
    snapshot_ids = list(dict.fromkeys(
        document_id for row in rows for document_id in (row["submitted_document_ids"] or [])
    ))
    snapshot_docs = {}
    if snapshot_ids and tenant_id is not None:
        docs = await db.fetch(
            """SELECT id, original_filename, doc_type
                 FROM documents
                WHERE id = ANY($1::uuid[]) AND tenant_id = $2""",
            snapshot_ids,
            tenant_id,
        )
        snapshot_docs = {str(doc["id"]): doc for doc in docs}
    out = []
    for r in rows:
        df = r["document_feedback"]
        if isinstance(df, str):
            df = json.loads(df) if df else []
        out.append(
            {
                "id": str(r["id"]),
                "round": r["round"],
                "requester_id": str(r["requester_id"]),
                "requester_name": r["requester_name"],
                "feedback": r["feedback"],
                "document_feedback": df or [],
                "requested_at": r["requested_at"].isoformat(),
                "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
                "business_response": r["business_response"],
                # Historical reads are sourced from this immutable round snapshot,
                # never from the submission's mutable current document_ids.
                "requirements_version_id": str(r["requirements_version_id"]) if r["requirements_version_id"] else None,
                "submitted_document_ids": [str(document_id) for document_id in (r["submitted_document_ids"] or [])],
                "submitted_documents": [
                    {
                        "id": str(document_id),
                        "filename": snapshot_docs[str(document_id)]["original_filename"],
                        "doc_type": snapshot_docs[str(document_id)]["doc_type"],
                    }
                    for document_id in (r["submitted_document_ids"] or [])
                    if str(document_id) in snapshot_docs
                ],
                "submitted_round": r["submitted_round"],
                "round_evidence_state": "bound" if r["submitted_round"] is not None and r["requirements_version_id"] else "unknown",
            }
        )
    return out
