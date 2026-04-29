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
        "SELECT id, status, revision_round, business_tenant FROM submissions WHERE id = $1",
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
        await db.execute(
            """
            UPDATE submissions
               SET status = 'revision_required',
                   revision_round = $1,
                   revision_requested_at = NOW(),
                   updated_at = NOW()
             WHERE id = $2
            """,
            new_round,
            submission_id,
        )
        request_row = await db.fetchrow(
            """
            INSERT INTO submission_revision_requests
                (submission_id, round, requester_id, requester_name, feedback, document_feedback)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id, requested_at
            """,
            submission_id,
            new_round,
            requester_id,
            requester_name,
            feedback,
            doc_feedback_json,
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
        SELECT id, status, revision_round, business_tenant, provider_id, document_ids
        FROM submissions WHERE id = $1
        """,
        submission_id,
    )
    if sub is None:
        raise SubmissionNotFound(submission_id)
    if sub["status"] not in ALLOWED_FROM_STATUSES_FOR_RESUBMIT:
        raise InvalidStateTransition(
            f"can't resubmit from status={sub['status']!r} (allowed: {ALLOWED_FROM_STATUSES_FOR_RESUBMIT})"
        )

    pending = await db.fetchrow(
        """
        SELECT id FROM submission_revision_requests
         WHERE submission_id = $1 AND resolved_at IS NULL
         ORDER BY round DESC LIMIT 1
        """,
        submission_id,
    )
    if pending is None:
        raise NoRevisionPending(submission_id)

    new_docs_param = [str(d) for d in new_document_ids] if new_document_ids is not None else None

    async with db.transaction():
        if new_docs_param is not None:
            await db.execute(
                """
                UPDATE submissions
                   SET status = 'reviewing',
                       document_ids = $1::uuid[],
                       notes = COALESCE(NULLIF($2, ''), notes),
                       revision_resubmitted_at = NOW(),
                       updated_at = NOW()
                 WHERE id = $3
                """,
                new_docs_param,
                business_notes,
                submission_id,
            )
        else:
            await db.execute(
                """
                UPDATE submissions
                   SET status = 'reviewing',
                       notes = COALESCE(NULLIF($1, ''), notes),
                       revision_resubmitted_at = NOW(),
                       updated_at = NOW()
                 WHERE id = $2
                """,
                business_notes,
                submission_id,
            )
        await db.execute(
            "UPDATE submission_revision_requests SET resolved_at = NOW() WHERE id = $1",
            pending["id"],
        )

    log.info("[revisions] resubmit submission=%s round=%d", submission_id, sub["revision_round"])
    return {
        "submission_id": submission_id,
        "round_resolved": sub["revision_round"],
        "resubmitted_at": datetime.now(timezone.utc).isoformat(),
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
               document_feedback, requested_at, resolved_at
        FROM submission_revision_requests
        WHERE submission_id = $1
        ORDER BY round DESC
        """,
        submission_id,
    )
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
            }
        )
    return out
