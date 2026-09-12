"""P0 submission document-lock tests.

Once a submission is approved/rejected/finalized, its reviewed document set is
part of the compliance record and must not be mutated by replace-document.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_certificate_pdf_integration import FakeRecord

pytestmark = pytest.mark.asyncio


class ReplaceDocFakeConn:
    def __init__(self, *, status: str, archived_at=None):
        self.status = status
        self.archived_at = archived_at
        self.old_doc_id = uuid4()
        self.new_doc_id = uuid4()
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql: str, *args):
        self.calls.append(("fetchrow", (sql, args)))
        if "FROM submissions WHERE id=$1 AND business_tenant=$2" in sql:
            return FakeRecord(
                id=args[0],
                document_ids=[self.old_doc_id],
                status=self.status,
                archived_at=self.archived_at,
            )
        if "FROM documents WHERE id=$1 AND tenant_id=$2" in sql:
            return FakeRecord(id=args[0])
        if "SELECT provider_id, auditor_id, company_name FROM submissions" in sql:
            return FakeRecord(provider_id=uuid4(), auditor_id=None, company_name="Business Co")
        raise AssertionError(sql)

    async def execute(self, sql: str, *args):
        self.calls.append(("execute", (sql, args)))
        return None


async def _replace(db: ReplaceDocFakeConn):
    from auth.submission_router import replace_submission_document

    return await replace_submission_document(
        submission_id=str(uuid4()),
        request={"old_doc_id": str(db.old_doc_id), "new_doc_id": str(db.new_doc_id)},
        user={"role": "business", "tenant_id": str(uuid4()), "sub": str(uuid4())},
        db=db,
    )


class TestSubmissionDocumentLock:
    @pytest.mark.parametrize("status", ["approved", "rejected"])
    async def test_terminal_status_blocks_document_replacement_before_any_update(self, status: str):
        db = ReplaceDocFakeConn(status=status)

        with pytest.raises(HTTPException) as exc:
            await _replace(db)

        assert exc.value.status_code == 400
        assert not any(call[0] == "execute" for call in db.calls)

    async def test_finalized_submission_blocks_document_replacement_even_if_status_is_non_terminal(self):
        db = ReplaceDocFakeConn(status="reviewing", archived_at=object())

        with pytest.raises(HTTPException) as exc:
            await _replace(db)

        assert exc.value.status_code == 400
        assert "hoàn tất" in str(exc.value.detail).lower() or "trạng thái cuối" in str(exc.value.detail).lower()
        assert not any(call[0] == "execute" for call in db.calls)

    async def test_revision_required_allows_replacement_and_resolves_revision(self):
        db = ReplaceDocFakeConn(status="revision_required")

        result = await _replace(db)

        assert "Đã cập nhật" in result["message"]
        sql_text = "\n".join(call[1][0] for call in db.calls if call[0] == "execute")
        assert "status = 'reviewing'" in sql_text
        assert "submission_revision_requests" in sql_text
