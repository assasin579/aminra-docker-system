"""Integration tests for /me/request-deletion + /me/confirm-deletion."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.mailer import CapturingSender, Mailer, MailerConfig
from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


USER_ID   = uuid4()
TENANT_ID = uuid4()


@pytest.fixture
def capturing_mailer(monkeypatch):
    cfg = MailerConfig(
        enabled=False,
        from_email="noreply@aminra.vn",
        from_name="AMINRA",
        default_lang="vi",
        app_base_url="https://aminra.test",
    )
    sender = CapturingSender()
    mailer = Mailer(cfg, sender=sender)
    monkeypatch.setattr("auth.gdpr_router.get_mailer", lambda: mailer)
    return mailer


class _FakeClient:
    host = "10.0.0.1"


class FakeRequest:
    client = _FakeClient()
    headers = {"user-agent": "pytest"}


def _user() -> dict:
    return {
        "sub":       str(USER_ID),
        "email":     "biz@example.vn",
        "role":      "business",
        "tenant_id": str(TENANT_ID),
    }


def _token_record(used: bool = False, expires_in_minutes: int = 60,
                  deleted: bool = False) -> FakeRecord:
    return FakeRecord(
        token_id=uuid4(),
        user_id=USER_ID,
        email="biz@example.vn",
        role="business",
        tenant_id=TENANT_ID,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        confirmed_at=datetime.now(timezone.utc) if used else None,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


# ── request-deletion ───────────────────────────────────────────────────────

class TestRequestDeletion:
    async def test_creates_token_emails_user_logs_audit(self, capturing_mailer: Mailer):
        from auth.gdpr_router import request_deletion, RequestDeletionIn

        db = FakeConn()
        # company_name lookup via fetchval
        db.fetchval_responses = [
            ("SELECT company_name FROM users", "Halal Foods Co"),
        ]

        await request_deletion(
            body=RequestDeletionIn(lang="vi"),
            request=FakeRequest(),
            user=_user(),
            db=db, _=None,
        )

        # Email landed
        assert len(capturing_mailer.sender.outbox) == 1
        msg = capturing_mailer.sender.outbox[0]
        assert msg["To"] == "biz@example.vn"
        assert "Xác nhận yêu cầu xoá tài khoản" in msg["Subject"]
        body = msg.get_body(preferencelist=("plain",)).get_content()
        assert "https://aminra.test/account/confirm-deletion?token=" in body

        # Token persisted
        inserts = [args for kind, (sql, args) in db.calls
                   if kind == "execute" and "INSERT INTO deletion_tokens" in sql]
        assert len(inserts) == 1

        # Audit log: data.delete.requested
        audit = [args for kind, (sql, args) in db.calls
                 if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit) == 1
        assert audit[0][4] == "data.delete.requested"


# ── confirm-deletion ───────────────────────────────────────────────────────

class TestConfirmDeletion:
    async def test_valid_token_anonymizes_and_logs(self):
        from auth.gdpr_router import confirm_deletion, ConfirmDeletionIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM deletion_tokens t", _token_record()),
        ]

        result = await confirm_deletion(
            body=ConfirmDeletionIn(token="x" * 40),
            request=FakeRequest(),
            db=db, _=None,
        )
        assert "đã bị xoá" in result["message"]

        # Audit log: data.delete.confirmed
        audit = [args for kind, (sql, args) in db.calls
                 if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit) == 1
        assert audit[0][4] == "data.delete.confirmed"
        meta = json.loads(audit[0][8])
        assert meta["anonymized_email"].endswith("@aminra.deleted")
        assert "original_email_hash" in meta

    async def test_invalid_token_returns_400_and_logs_attempt(self):
        from fastapi import HTTPException
        from auth.gdpr_router import confirm_deletion, ConfirmDeletionIn

        db = FakeConn()
        db.fetchrow_responses = [("FROM deletion_tokens t", None)]
        with pytest.raises(HTTPException) as exc:
            await confirm_deletion(
                body=ConfirmDeletionIn(token="x" * 40),
                request=FakeRequest(),
                db=db, _=None,
            )
        assert exc.value.status_code == 400

        audit = [args for kind, (sql, args) in db.calls
                 if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit) == 1
        assert audit[0][4] == "data.delete.confirm_invalid_token"

    async def test_used_token_rejected(self):
        from fastapi import HTTPException
        from auth.gdpr_router import confirm_deletion, ConfirmDeletionIn

        db = FakeConn()
        db.fetchrow_responses = [("FROM deletion_tokens t", _token_record(used=True))]
        with pytest.raises(HTTPException) as exc:
            await confirm_deletion(
                body=ConfirmDeletionIn(token="x" * 40),
                request=FakeRequest(),
                db=db, _=None,
            )
        assert exc.value.status_code == 400
