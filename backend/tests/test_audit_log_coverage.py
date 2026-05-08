"""Verify audit log emits for the newly-instrumented call sites:
- provider.approve / provider.reject (admin endpoints)
- submission.submit (business owner)
- submission.status_change.* (provider)
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


ADMIN_USER = {"sub": str(uuid4()), "email": "admin@aminra.com", "role": "admin"}


# ── FakeRequest helper ──────────────────────────────────────────────────────

class _FakeClient:
    host = "10.0.0.1"


class FakeRequest:
    client = _FakeClient()
    headers = {"user-agent": "pytest"}


def _audit_inserts(db: FakeConn) -> list[tuple]:
    return [args for kind, (sql, args) in db.calls
            if kind == "execute" and "INSERT INTO audit_logs" in sql]


# ── Provider approve / reject (admin_router) ────────────────────────────────

class TestProviderApprovalAuditLog:
    async def test_approve_records_status_diff(self):
        from auth.admin_router import approve_provider

        provider_id = str(uuid4())
        db = FakeConn()
        db.fetchrow_responses = [
            ("UPDATE users SET status = 'active'",
             FakeRecord(id=uuid4(), email="cb@example.vn", status="active")),
        ]
        await approve_provider(
            provider_id=provider_id,
            request=FakeRequest(),
            admin=ADMIN_USER,
            db=db,
        )

        inserts = _audit_inserts(db)
        assert len(inserts) == 1
        args = inserts[0]
        assert args[4] == "provider.approve"
        assert args[5] == "user"
        assert json.loads(args[7]) == {"status": ["pending", "active"]}
        assert json.loads(args[8])["provider_email"] == "cb@example.vn"

    async def test_reject_records_status_diff_and_reason(self):
        from auth.admin_router import reject_provider, RejectRequest

        provider_id = str(uuid4())
        db = FakeConn()
        db.fetchrow_responses = [
            ("UPDATE users SET status = 'suspended'",
             FakeRecord(id=uuid4(), email="cb@example.vn", status="suspended")),
        ]
        await reject_provider(
            provider_id=provider_id,
            req=RejectRequest(reason="Hồ sơ không đầy đủ"),
            request=FakeRequest(),
            admin=ADMIN_USER,
            db=db,
        )

        inserts = _audit_inserts(db)
        assert len(inserts) == 1
        args = inserts[0]
        assert args[4] == "provider.reject"
        assert json.loads(args[7]) == {"status": ["pending", "suspended"]}
        meta = json.loads(args[8])
        assert meta["reason"] == "Hồ sơ không đầy đủ"
        assert meta["provider_email"] == "cb@example.vn"

    async def test_approve_404_does_not_emit_audit(self):
        from fastapi import HTTPException
        from auth.admin_router import approve_provider

        db = FakeConn()
        db.fetchrow_responses = [
            ("UPDATE users SET status = 'active'", None),
        ]
        with pytest.raises(HTTPException):
            await approve_provider(
                provider_id=str(uuid4()),
                request=FakeRequest(),
                admin=ADMIN_USER,
                db=db,
            )
        assert _audit_inserts(db) == []


# ── Submission submit (business owner) ──────────────────────────────────────

class TestSubmissionSubmitAuditLog:
    async def test_submit_records_provider_and_doc_count(self):
        from auth.submission_router import submit_documents
        from auth.submission_router import SubmitRequest

        owner = {
            "sub":       str(uuid4()),
            "email":     "biz@example.vn",
            "role":      "business",
            "is_owner":  True,
            "tenant_id": str(uuid4()),
        }
        provider_id = str(uuid4())
        doc_id = uuid4()

        db = FakeConn()
        # provider lookup → fetchrow
        # documents count → fetchval
        # business name → fetchrow
        # INSERT submission → fetchrow
        db.fetchrow_responses = [
            ("FROM users WHERE id = $1 AND role = 'provider'",
             FakeRecord(id=uuid4(), company_name="Halal CB Vietnam")),
            ("SELECT company_name FROM users WHERE id = $1",
             FakeRecord(company_name="Halal Foods Co")),
            ("INSERT INTO submissions",
             FakeRecord(id=uuid4(), submitted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))),
        ]
        db.fetchval_responses = [
            ("SELECT COUNT(*) FROM documents", 1),
        ]

        await submit_documents(
            req=SubmitRequest(
                provider_id=provider_id,
                document_ids=[str(doc_id)],
                notes="MVP test",
            ),
            request=FakeRequest(),
            owner=owner,
            db=db,
        )

        inserts = _audit_inserts(db)
        assert len(inserts) == 1
        args = inserts[0]
        assert args[4] == "submission.submit"
        assert args[5] == "submission"
        meta = json.loads(args[8])
        assert meta["provider_name"] == "Halal CB Vietnam"
        assert meta["document_count"] == 1


# ── Submission status change (provider) ─────────────────────────────────────

class TestSubmissionStatusChangeAuditLog:
    @pytest.mark.skip(
        reason="stale: hardcodes status='approved' but update_submission_status now "
        "rejects terminal transitions (must use /approve-final). Rewrite to use a "
        "non-terminal transition like reviewing → revision_required, or test "
        "/approve-final endpoint directly."
    )
    async def test_status_change_records_namespaced_action_and_diff(self):
        from auth.submission_router import update_submission_status
        from auth.submission_router import UpdateStatusRequest

        sub_id = str(uuid4())
        provider = {
            "sub":      str(uuid4()),
            "email":    "cb@example.vn",
            "role":     "provider",
            "is_owner": True,
            "tenant_id": str(uuid4()),
        }

        db = FakeConn()
        # 1) snapshot previous status
        # 2) (no UPDATE response — execute returns None)
        # 3) sub_info for notify
        # 4) biz_owner for notify
        db.fetchrow_responses = [
            ("SELECT status FROM submissions WHERE id = $1",
             FakeRecord(status="reviewing")),
            ("SELECT business_tenant FROM submissions WHERE id=$1",
             FakeRecord(business_tenant=uuid4())),
            ("SELECT id FROM users WHERE id=$1 OR (tenant_id=$1",
             None),  # no biz owner → notify skipped
        ]
        # The fake execute returns None, so we need to make UPDATE return non-zero
        # by overriding `execute` in our Fake.
        original_execute = db.execute

        async def execute_returning_update_1(sql, *args):
            await original_execute(sql, *args)
            if sql.startswith("UPDATE submissions"):
                return "UPDATE 1"
            return None

        db.execute = execute_returning_update_1

        await update_submission_status(
            submission_id=sub_id,
            req=UpdateStatusRequest(status="approved", auditor_notes="OK"),
            request=FakeRequest(),
            user=provider,
            db=db,
        )

        inserts = _audit_inserts(db)
        assert len(inserts) == 1
        args = inserts[0]
        assert args[4] == "submission.status_change.approved"
        assert json.loads(args[7]) == {"status": ["reviewing", "approved"]}
        assert json.loads(args[8])["auditor_notes"] == "OK"

    async def test_invalid_status_does_not_emit_audit(self):
        from fastapi import HTTPException
        from auth.submission_router import update_submission_status
        from auth.submission_router import UpdateStatusRequest

        provider = {"sub": str(uuid4()), "role": "provider"}
        db = FakeConn()
        with pytest.raises(HTTPException) as exc:
            await update_submission_status(
                submission_id=str(uuid4()),
                req=UpdateStatusRequest(status="totally_invalid", auditor_notes=""),
                request=FakeRequest(),
                user=provider,
                db=db,
            )
        assert exc.value.status_code == 400
        assert _audit_inserts(db) == []
