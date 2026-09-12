"""P0 submission state-machine tests.

These tests make the compliance workflow explicit: revision requests can only
come from reviewable states, resubmits can only resolve an open revision, and
approved/final states cannot be driven backward by legacy endpoints.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeRecord

pytestmark = pytest.mark.asyncio


class RevisionFakeConn:
    def __init__(self, *, status: str, revision_round: int = 0, pending=True):
        self.status = status
        self.revision_round = revision_round
        self.pending = pending
        self.calls: list[tuple[str, tuple]] = []

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetchrow(self, sql: str, *args):
        self.calls.append(("fetchrow", (sql, args)))
        if "FROM submissions WHERE id = $1" in sql:
            return FakeRecord(
                id=args[0],
                status=self.status,
                revision_round=self.revision_round,
                business_tenant=uuid4(),
                provider_id=uuid4(),
                document_ids=[],
            )
        if "FROM submission_revision_requests" in sql:
            return FakeRecord(id=uuid4()) if self.pending else None
        if "INSERT INTO submission_revision_requests" in sql:
            return FakeRecord(id=uuid4(), requested_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        raise AssertionError(sql)

    async def execute(self, sql: str, *args):
        self.calls.append(("execute", (sql, args)))
        return None


class TestSubmissionStateMachine:
    async def test_request_revision_rejects_already_approved_submission(self):
        from services.submission_revisions import InvalidStateTransition, request_revision

        db = RevisionFakeConn(status="approved")
        with pytest.raises(InvalidStateTransition):
            await request_revision(
                db,
                submission_id=str(uuid4()),
                requester_id=str(uuid4()),
                requester_name="Provider",
                feedback="too late",
            )

        assert not any("UPDATE submissions" in call[1][0] for call in db.calls)

    async def test_resubmit_requires_revision_required_and_pending_request(self):
        from services.submission_revisions import InvalidStateTransition, resubmit

        db = RevisionFakeConn(status="reviewing", revision_round=0, pending=False)
        with pytest.raises(InvalidStateTransition):
            await resubmit(db, submission_id=str(uuid4()), business_notes="done")

        assert not any("UPDATE submissions" in call[1][0] for call in db.calls)

    async def test_revision_required_resubmit_returns_to_reviewing_and_resolves_pending_round(self):
        from services.submission_revisions import resubmit

        db = RevisionFakeConn(status="revision_required", revision_round=2, pending=True)
        result = await resubmit(db, submission_id=str(uuid4()), business_notes="fixed")

        assert result["round_resolved"] == 2
        sql_text = "\n".join(call[1][0] for call in db.calls if call[0] == "execute")
        assert "SET status = 'reviewing'" in sql_text
        assert "resolved_at = NOW()" in sql_text
