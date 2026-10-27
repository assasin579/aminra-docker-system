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
        self.requirements_version_id = uuid4()
        self.document_ids = [uuid4()]
        self.business_tenant = uuid4()
        self.dossier_id = uuid4()
        self.new_docs = []
        self.slots = []
        self.calls: list[tuple[str, tuple]] = []

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetchrow(self, sql: str, *args):
        self.calls.append(("fetchrow", (sql, args)))
        if sql.lstrip().startswith("UPDATE submissions"):
            from datetime import datetime, timezone
            if "status = 'revision_required'" in sql:
                self.status = "revision_required"
                self.revision_round = args[0]
                return FakeRecord(id=args[1])
            self.status = "reviewing"
            if "document_ids = $1::uuid[]" in sql:
                self.document_ids = args[0]
                submission_id = args[2]
            else:
                submission_id = args[1]
            return FakeRecord(id=submission_id, revision_resubmitted_at=datetime.now(timezone.utc))
        if "UPDATE submission_revision_requests" in sql:
            return FakeRecord(id=args[0])
        if "FROM submissions WHERE id = $1" in sql:
            return FakeRecord(
                id=args[0],
                status=self.status,
                revision_round=self.revision_round,
                business_tenant=self.business_tenant,
                provider_id=uuid4(),
                document_ids=self.document_ids,
                requirements_version_id=self.requirements_version_id,
                requirements_binding_status="bound",
            )
        if "FROM submission_revision_requests" in sql:
            return FakeRecord(id=uuid4()) if self.pending else None
        if "FROM dossiers WHERE id=$1 AND tenant_id=$2" in sql:
            return FakeRecord(
                id=self.dossier_id,
                requirements_version_id=self.requirements_version_id,
                requirements_binding_status="bound",
            )
        if "INSERT INTO submission_revision_requests" in sql:
            return FakeRecord(id=uuid4(), requested_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        raise AssertionError(sql)

    async def fetch(self, sql: str, *args):
        self.calls.append(("fetch", (sql, args)))
        if "SELECT DISTINCT dossier_id FROM documents" in sql:
            return [FakeRecord(dossier_id=self.dossier_id)] if self.document_ids else []
        if "SELECT id, dossier_id, tenant_id, doc_type, version_number FROM documents" in sql:
            return self.new_docs
        if "FROM standard_requirement_version_slots" in sql:
            return self.slots
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

    async def test_request_revision_persists_exact_version_and_submitted_document_ids(self):
        from services.submission_revisions import request_revision

        db = RevisionFakeConn(status="reviewing", revision_round=1)
        await request_revision(
            db,
            submission_id=str(uuid4()),
            requester_id=str(uuid4()),
            requester_name="Provider",
            feedback="replace outdated evidence",
        )

        select_call = next(call for call in db.calls if "FROM submissions WHERE id = $1" in call[1][0])
        select_sql = select_call[1][0]
        assert "requirements_version_id" in select_sql
        assert "requirements_binding_status" in select_sql
        assert "document_ids" in select_sql
        insert_call = next(call for call in db.calls if "INSERT INTO submission_revision_requests" in call[1][0])
        sql, args = insert_call[1]
        assert "requirements_version_id" in sql
        assert "submitted_document_ids" in sql
        assert "submitted_round" in sql
        assert args[6] == db.requirements_version_id
        assert args[7] == db.document_ids
        assert args[8] == 2

    async def test_historical_revision_history_returns_immutable_round_snapshot(self):
        from datetime import datetime, timezone
        from services.submission_revisions import list_revision_history

        requirement_version_id, historical_doc_id = uuid4(), uuid4()

        class HistoryDB:
            def __init__(self):
                self.calls = []

            async def fetch(self, sql, *args):
                self.calls.append((sql, args))
                return [FakeRecord(
                    id=uuid4(), round=1, requester_id=uuid4(), requester_name="Reviewer",
                    feedback="fix evidence", document_feedback=[], requested_at=datetime.now(timezone.utc),
                    resolved_at=None, business_response=None,
                    requirements_version_id=requirement_version_id,
                    submitted_document_ids=[historical_doc_id], submitted_round=1,
                )]

        db = HistoryDB()
        history = await list_revision_history(db, str(uuid4()))

        query = db.calls[0][0]
        assert "submitted_document_ids" in query
        assert "requirements_version_id" in query
        assert "submitted_round" in query
        assert "FROM submissions" not in query
        assert history[0]["submitted_document_ids"] == [str(historical_doc_id)]
        assert history[0]["requirements_version_id"] == str(requirement_version_id)
        assert history[0]["submitted_round"] == 1

    async def test_resubmit_requires_revision_required_and_pending_request(self):
        from services.submission_revisions import InvalidStateTransition, resubmit

        db = RevisionFakeConn(status="reviewing", revision_round=0, pending=False)
        with pytest.raises(InvalidStateTransition):
            await resubmit(db, submission_id=str(uuid4()), business_notes="done")

        assert not any("UPDATE submissions" in call[1][0] for call in db.calls)

    async def test_version_bound_resubmit_validates_same_business_dossier_and_slot(self):
        from services.submission_revisions import resubmit

        db = RevisionFakeConn(status="revision_required", revision_round=1)
        replacement_id = uuid4()
        db.new_docs = [FakeRecord(
            id=replacement_id,
            dossier_id=db.dossier_id,
            tenant_id=db.business_tenant,
            doc_type="safety_policy",
            version_number=2,
        )]
        db.slots = [FakeRecord(doc_type="safety_policy")]

        result = await resubmit(db, submission_id=str(uuid4()), new_document_ids=[str(replacement_id)])

        assert result["round_resolved"] == 1
        evidence_query = next(call for call in db.calls if "SELECT id, dossier_id, tenant_id, doc_type, version_number FROM documents" in call[1][0])
        assert "tenant_id = $2 AND dossier_id = $3" in evidence_query[1][0]
        assert evidence_query[1][1][1:] == (db.business_tenant, db.dossier_id)
        update = next(call for call in db.calls if call[0] == "fetchrow" and "UPDATE submissions" in call[1][0])
        assert update[1][1][0] == [str(replacement_id)]

    async def test_version_bound_resubmit_rejects_unmapped_document_type_without_mutation(self):
        from services.submission_revisions import InvalidStateTransition, resubmit

        db = RevisionFakeConn(status="revision_required", revision_round=1)
        replacement_id = uuid4()
        db.new_docs = [FakeRecord(
            id=replacement_id,
            dossier_id=db.dossier_id,
            tenant_id=db.business_tenant,
            doc_type="unmapped_type",
            version_number=2,
        )]
        db.slots = [FakeRecord(doc_type="safety_policy")]

        with pytest.raises(InvalidStateTransition, match="not mapped"):
            await resubmit(db, submission_id=str(uuid4()), new_document_ids=[str(replacement_id)])

        assert not any(call[0] == "execute" for call in db.calls)

    async def test_revision_required_resubmit_returns_to_reviewing_and_resolves_pending_round(self):
        from services.submission_revisions import resubmit

        db = RevisionFakeConn(status="revision_required", revision_round=2, pending=True)
        result = await resubmit(db, submission_id=str(uuid4()), business_notes="fixed")

        assert result["round_resolved"] == 2
        sql_text = "\n".join(call[1][0] for call in db.calls if call[0] in {"execute", "fetchrow"})
        assert "SET status = 'reviewing'" in sql_text
        assert "resolved_at = NOW()" in sql_text
