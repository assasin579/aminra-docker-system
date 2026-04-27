"""Unit tests for services/submission_revisions.py.

Strategy: real Postgres connection (DB has migration 010 applied) but injected
test data. Each test creates a fresh submission in a transaction and rolls
back so we don't pollute prod data.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg
import pytest


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
async def conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
async def fresh_submission(conn):
    """Create an isolated submission + cleanup after test. Returns (sub_id, tenant_id, provider_id)."""
    # Find any existing user to use as both business + provider (test needs FK valid)
    biz_user = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE role='business' AND is_owner=true LIMIT 1"
    )
    prov_user = await conn.fetchrow(
        "SELECT id FROM users WHERE role='provider' AND is_owner=true LIMIT 1"
    )
    if not biz_user or not prov_user:
        pytest.skip("Need at least 1 business + 1 provider user in DB")

    sub_id = uuid4()
    await conn.execute(
        """
        INSERT INTO submissions (id, business_tenant, provider_id, document_ids, status, notes, company_name)
        VALUES ($1, $2, $3, '{}'::uuid[], 'reviewing', 'test', 'Test Co')
        """,
        sub_id, biz_user["tenant_id"], prov_user["id"],
    )
    yield str(sub_id), str(biz_user["tenant_id"]), str(prov_user["id"])
    # Cleanup
    await conn.execute("DELETE FROM submission_revision_requests WHERE submission_id = $1", sub_id)
    await conn.execute("DELETE FROM submissions WHERE id = $1", sub_id)


# ── request_revision ───────────────────────────────────────────────────────

class TestRequestRevision:
    async def test_happy_path_creates_request_and_flips_status(self, conn, fresh_submission):
        from services.submission_revisions import (
            DocumentFeedback, request_revision,
        )

        sub_id, _, prov_id = fresh_submission
        result = await request_revision(
            conn,
            submission_id=sub_id,
            requester_id=prov_id,
            requester_name="Test CB",
            feedback="Cần bổ sung chứng nhận JAKIM",
            document_feedback=[
                DocumentFeedback(
                    document_id=str(uuid4()),
                    issue="Thiếu seal",
                    severity="major",
                    suggestion="Tải lại bản có seal",
                ),
            ],
        )

        assert result["round"] == 1
        assert "request_id" in result

        # Submission status updated
        sub = await conn.fetchrow("SELECT status, revision_round FROM submissions WHERE id = $1", sub_id)
        assert sub["status"] == "revision_required"
        assert sub["revision_round"] == 1

        # Revision request row created
        rr = await conn.fetchrow(
            "SELECT round, feedback, document_feedback FROM submission_revision_requests WHERE submission_id = $1",
            sub_id,
        )
        assert rr["round"] == 1
        assert rr["feedback"] == "Cần bổ sung chứng nhận JAKIM"
        df = json.loads(rr["document_feedback"]) if isinstance(rr["document_feedback"], str) else rr["document_feedback"]
        assert len(df) == 1
        assert df[0]["severity"] == "major"

    async def test_rejects_empty_feedback(self, conn, fresh_submission):
        from services.submission_revisions import request_revision

        sub_id, _, prov_id = fresh_submission
        with pytest.raises(ValueError, match="empty"):
            await request_revision(
                conn,
                submission_id=sub_id,
                requester_id=prov_id,
                requester_name="X",
                feedback="   ",
            )

    async def test_invalid_state_transition_from_approved(self, conn, fresh_submission):
        from services.submission_revisions import (
            InvalidStateTransition, request_revision,
        )

        sub_id, _, prov_id = fresh_submission
        # Move to 'approved' state
        await conn.execute("UPDATE submissions SET status='approved' WHERE id=$1", sub_id)

        with pytest.raises(InvalidStateTransition):
            await request_revision(
                conn,
                submission_id=sub_id,
                requester_id=prov_id,
                requester_name="X",
                feedback="too late",
            )

    async def test_unknown_submission_raises(self, conn):
        from services.submission_revisions import (
            SubmissionNotFound, request_revision,
        )

        with pytest.raises(SubmissionNotFound):
            await request_revision(
                conn,
                submission_id=str(uuid4()),
                requester_id=str(uuid4()),
                requester_name="X",
                feedback="abc",
            )

    async def test_round_increments_on_repeat_after_resubmit(self, conn, fresh_submission):
        """Round 1 → resubmit → Round 2. Tests append-only history."""
        from services.submission_revisions import request_revision, resubmit

        sub_id, _, prov_id = fresh_submission

        # Round 1
        r1 = await request_revision(
            conn, submission_id=sub_id, requester_id=prov_id,
            requester_name="X", feedback="round 1",
        )
        assert r1["round"] == 1

        # Business resubmits
        await resubmit(conn, submission_id=sub_id)

        # Round 2
        r2 = await request_revision(
            conn, submission_id=sub_id, requester_id=prov_id,
            requester_name="X", feedback="round 2 issues",
        )
        assert r2["round"] == 2

        # Both rounds preserved
        all_rounds = await conn.fetch(
            "SELECT round FROM submission_revision_requests WHERE submission_id = $1 ORDER BY round",
            sub_id,
        )
        assert [r["round"] for r in all_rounds] == [1, 2]


# ── resubmit ───────────────────────────────────────────────────────────────

class TestResubmit:
    async def test_happy_path_flips_status_to_reviewing(self, conn, fresh_submission):
        from services.submission_revisions import request_revision, resubmit

        sub_id, _, prov_id = fresh_submission
        await request_revision(
            conn, submission_id=sub_id, requester_id=prov_id,
            requester_name="X", feedback="fix this",
        )

        result = await resubmit(conn, submission_id=sub_id, business_notes="Done")

        assert result["round_resolved"] == 1
        sub = await conn.fetchrow(
            "SELECT status, notes, revision_resubmitted_at FROM submissions WHERE id = $1", sub_id,
        )
        assert sub["status"] == "reviewing"
        assert sub["notes"] == "Done"
        assert sub["revision_resubmitted_at"] is not None

        # Pending request marked resolved
        rr = await conn.fetchrow(
            "SELECT resolved_at FROM submission_revision_requests WHERE submission_id = $1",
            sub_id,
        )
        assert rr["resolved_at"] is not None

    async def test_resubmit_with_new_documents(self, conn, fresh_submission):
        from services.submission_revisions import request_revision, resubmit

        sub_id, tenant_id, prov_id = fresh_submission

        # Insert real documents owned by tenant
        new_doc_id = uuid4()
        # Find or create a user_id for tenant
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE tenant_id = $1 AND is_owner = true LIMIT 1", tenant_id,
        )
        await conn.execute(
            """
            INSERT INTO documents (id, filename, original_filename, user_id, tenant_id, doc_type, status)
            VALUES ($1, 'fixed.pdf', 'fixed.pdf', $2, $3, 'application', 'uploaded')
            """,
            new_doc_id, user_id, tenant_id,
        )

        try:
            await request_revision(
                conn, submission_id=sub_id, requester_id=prov_id,
                requester_name="X", feedback="upload fixed version",
            )
            await resubmit(
                conn, submission_id=sub_id,
                new_document_ids=[str(new_doc_id)],
            )

            sub = await conn.fetchrow(
                "SELECT document_ids FROM submissions WHERE id = $1", sub_id,
            )
            assert len(sub["document_ids"]) == 1
            assert str(sub["document_ids"][0]) == str(new_doc_id)
        finally:
            await conn.execute("DELETE FROM documents WHERE id = $1", new_doc_id)

    async def test_no_pending_revision_raises(self, conn, fresh_submission):
        from services.submission_revisions import (
            InvalidStateTransition, NoRevisionPending, resubmit,
        )

        sub_id, _, _ = fresh_submission
        # Submission is in 'reviewing' state — no revision_required
        with pytest.raises(InvalidStateTransition):
            await resubmit(conn, submission_id=sub_id)

    async def test_resubmit_double_call_second_fails(self, conn, fresh_submission):
        from services.submission_revisions import (
            InvalidStateTransition, request_revision, resubmit,
        )

        sub_id, _, prov_id = fresh_submission
        await request_revision(
            conn, submission_id=sub_id, requester_id=prov_id,
            requester_name="X", feedback="issue",
        )
        await resubmit(conn, submission_id=sub_id)
        # Second call: status is now 'reviewing', not 'revision_required'
        with pytest.raises(InvalidStateTransition):
            await resubmit(conn, submission_id=sub_id)


# ── list_revision_history ─────────────────────────────────────────────────

class TestListHistory:
    async def test_returns_rounds_newest_first(self, conn, fresh_submission):
        from services.submission_revisions import (
            DocumentFeedback, list_revision_history,
            request_revision, resubmit,
        )

        sub_id, _, prov_id = fresh_submission

        # 2 rounds
        await request_revision(
            conn, submission_id=sub_id, requester_id=prov_id,
            requester_name="X", feedback="round 1",
            document_feedback=[DocumentFeedback(
                document_id=str(uuid4()), issue="A", severity="minor",
            )],
        )
        await resubmit(conn, submission_id=sub_id)
        await request_revision(
            conn, submission_id=sub_id, requester_id=prov_id,
            requester_name="X", feedback="round 2",
        )

        history = await list_revision_history(conn, sub_id)

        assert len(history) == 2
        assert history[0]["round"] == 2  # newest first
        assert history[0]["resolved_at"] is None  # current round still open
        assert history[1]["round"] == 1
        assert history[1]["resolved_at"] is not None  # round 1 resolved

    async def test_empty_history_for_no_revisions(self, conn, fresh_submission):
        from services.submission_revisions import list_revision_history

        sub_id, _, _ = fresh_submission
        history = await list_revision_history(conn, sub_id)
        assert history == []
