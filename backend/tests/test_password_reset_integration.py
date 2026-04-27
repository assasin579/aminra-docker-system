"""Integration tests for the password-reset router.

Wires real router functions against a FakeConn to exercise the full flow:
token generation → email send → token verify → password reset → audit log
side-effects, all without a running database or SMTP server.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from services.mailer import CapturingSender, Mailer, MailerConfig
from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


# ── Shared fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def capturing_mailer(monkeypatch: pytest.MonkeyPatch) -> Mailer:
    """Replace the singleton mailer with a Capturing one for the duration of a test."""
    cfg = MailerConfig(
        enabled=False,
        from_email="noreply@aminra.vn",
        from_name="AMINRA",
        default_lang="vi",
        app_base_url="https://aminra.test",
    )
    sender = CapturingSender()
    mailer = Mailer(cfg, sender=sender)
    monkeypatch.setattr("auth.password_reset_router.get_mailer", lambda: mailer)
    return mailer


@pytest.fixture
def fake_request():
    class FakeClient:
        host = "203.0.113.1"

    class FakeReq:
        client = FakeClient()
        headers = {"user-agent": "pytest"}

    return FakeReq()


USER_ID = uuid4()


def _user_record(email="biz@example.vn", name="Halal Foods Co"):
    return FakeRecord(id=USER_ID, email=email, company_name=name)


def _token_record(token: str, expires_in_minutes: int = 60, used: bool = False):
    return FakeRecord(
        id=uuid4(),
        token_id=uuid4(),
        user_id=USER_ID,
        email="biz@example.vn",
        role="business",
        tenant_id=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        used=used,
    )


# ── /request-password-reset ─────────────────────────────────────────────────

class TestRequestPasswordReset:
    async def test_existing_email_creates_token_and_sends_mail(
        self, capturing_mailer: Mailer, fake_request,
    ):
        from auth.password_reset_router import request_password_reset, RequestResetIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM users WHERE LOWER(email)", _user_record()),
        ]
        result = await request_password_reset(
            body=RequestResetIn(email="biz@example.vn", lang="vi"),
            request=fake_request,
            db=db, _=None,
        )

        # Generic response (no leak)
        assert "Nếu email tồn tại" in result["message"]

        # Token INSERT happened
        inserts = [args for kind, (sql, args) in db.calls
                   if kind == "execute" and "INSERT INTO password_reset_tokens" in sql]
        assert len(inserts) == 1
        # Args: user_id, token, expires_at
        token = inserts[0][1]
        assert isinstance(token, str)
        assert len(token) >= 40  # 32 bytes URL-safe = ~43 chars

        # Email sent with the same token
        assert len(capturing_mailer.sender.outbox) == 1
        msg = capturing_mailer.sender.outbox[0]
        body = msg.get_body(preferencelist=("plain",)).get_content()
        assert f"https://aminra.test/reset-password?token={token}" in body
        assert msg["To"] == "biz@example.vn"

        # Audit log entry recorded
        audit_inserts = [args for kind, (sql, args) in db.calls
                         if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit_inserts) == 1
        assert audit_inserts[0][4] == "password_reset.request"

    async def test_invalidates_existing_unused_tokens(
        self, capturing_mailer: Mailer, fake_request,
    ):
        from auth.password_reset_router import request_password_reset, RequestResetIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM users WHERE LOWER(email)", _user_record()),
        ]
        await request_password_reset(
            body=RequestResetIn(email="biz@example.vn"),
            request=fake_request,
            db=db, _=None,
        )

        invalidate_calls = [args for kind, (sql, args) in db.calls
                            if kind == "execute"
                            and "UPDATE password_reset_tokens SET used = true WHERE user_id" in sql
                            and "AND used = false" in sql]
        assert len(invalidate_calls) == 1

    async def test_unknown_email_returns_same_message_no_email_sent(
        self, capturing_mailer: Mailer, fake_request,
    ):
        from auth.password_reset_router import request_password_reset, RequestResetIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM users WHERE LOWER(email)", None),
        ]
        result = await request_password_reset(
            body=RequestResetIn(email="ghost@nowhere.io"),
            request=fake_request,
            db=db, _=None,
        )
        assert "Nếu email tồn tại" in result["message"]
        # No mail
        assert capturing_mailer.sender.outbox == []
        # No reset token created
        token_inserts = [c for kind, (sql, _) in db.calls
                         if kind == "execute" and "INSERT INTO password_reset_tokens" in sql
                         for c in [True]]
        assert token_inserts == []
        # Audit log: request_unknown_email
        audit_inserts = [args for kind, (sql, args) in db.calls
                         if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit_inserts) == 1
        assert audit_inserts[0][4] == "password_reset.request_unknown_email"

    async def test_email_lookup_is_case_insensitive_and_trimmed(
        self, capturing_mailer: Mailer, fake_request,
    ):
        from auth.password_reset_router import request_password_reset, RequestResetIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM users WHERE LOWER(email)", _user_record()),
        ]
        await request_password_reset(
            body=RequestResetIn(email="  Biz@Example.VN  "),
            request=fake_request,
            db=db, _=None,
        )
        # The query was called with normalized email (lowercased, trimmed).
        first_fetchrow = next(args for kind, (sql, args) in db.calls
                              if kind == "fetchrow" and "FROM users" in sql)
        assert first_fetchrow[0] == "biz@example.vn"


# ── /verify-reset-token ─────────────────────────────────────────────────────

class TestVerifyResetToken:
    async def test_valid_token_returns_email(self):
        from auth.password_reset_router import verify_reset_token, VerifyTokenIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record("xx" * 11)),
        ]
        result = await verify_reset_token(
            body=VerifyTokenIn(token="x" * 30),
            db=db, _=None,
        )
        assert result == {"valid": True, "email": "biz@example.vn"}

    async def test_used_token_rejected(self):
        from fastapi import HTTPException
        from auth.password_reset_router import verify_reset_token, VerifyTokenIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record("x", used=True)),
        ]
        with pytest.raises(HTTPException) as exc:
            await verify_reset_token(body=VerifyTokenIn(token="x" * 30), db=db, _=None)
        assert exc.value.status_code == 400

    async def test_expired_token_rejected(self):
        from fastapi import HTTPException
        from auth.password_reset_router import verify_reset_token, VerifyTokenIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record("x", expires_in_minutes=-1)),
        ]
        with pytest.raises(HTTPException) as exc:
            await verify_reset_token(body=VerifyTokenIn(token="x" * 30), db=db, _=None)
        assert exc.value.status_code == 400

    async def test_unknown_token_rejected(self):
        from fastapi import HTTPException
        from auth.password_reset_router import verify_reset_token, VerifyTokenIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", None),
        ]
        with pytest.raises(HTTPException) as exc:
            await verify_reset_token(body=VerifyTokenIn(token="x" * 30), db=db, _=None)
        assert exc.value.status_code == 400


# ── /reset-password ─────────────────────────────────────────────────────────

class TestResetPassword:
    async def test_valid_token_and_strong_password_updates_hash(self, fake_request):
        from auth.password_reset_router import reset_password, ResetPasswordIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record("x")),
        ]
        result = await reset_password(
            body=ResetPasswordIn(token="x" * 30, new_password="Strong1Password"),
            request=fake_request, db=db, _=None,
        )
        assert "thành công" in result["message"]

        # Password UPDATE happened
        pw_updates = [args for kind, (sql, args) in db.calls
                      if kind == "execute" and "UPDATE users SET password_hash" in sql]
        assert len(pw_updates) == 1
        # Hash is bcrypt format
        new_hash = pw_updates[0][0]
        assert new_hash.startswith("$2b$")

        # All sibling tokens invalidated
        token_invalidates = [args for kind, (sql, args) in db.calls
                             if kind == "execute"
                             and "UPDATE password_reset_tokens SET used = true WHERE user_id" in sql
                             and "AND used = false" not in sql]
        assert len(token_invalidates) == 1

        # Audit log: success
        audit_inserts = [args for kind, (sql, args) in db.calls
                         if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit_inserts) == 1
        assert audit_inserts[0][4] == "password_reset.success"

    async def test_weak_password_returns_400_no_db_write(self, fake_request):
        from fastapi import HTTPException
        from auth.password_reset_router import reset_password, ResetPasswordIn

        db = FakeConn()
        with pytest.raises(HTTPException) as exc:
            await reset_password(
                body=ResetPasswordIn(token="x" * 30, new_password="weak"),
                request=fake_request, db=db, _=None,
            )
        assert exc.value.status_code == 400
        # Token never even fetched
        assert all(kind != "fetchrow" for kind, _ in db.calls)

    async def test_invalid_token_returns_400_and_logs_attempt(self, fake_request):
        from fastapi import HTTPException
        from auth.password_reset_router import reset_password, ResetPasswordIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", None),
        ]
        with pytest.raises(HTTPException) as exc:
            await reset_password(
                body=ResetPasswordIn(token="x" * 30, new_password="Strong1Password"),
                request=fake_request, db=db, _=None,
            )
        assert exc.value.status_code == 400

        # Audit log: consume_invalid_token
        audit_inserts = [args for kind, (sql, args) in db.calls
                         if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit_inserts) == 1
        assert audit_inserts[0][4] == "password_reset.consume_invalid_token"

    async def test_used_token_rejected(self, fake_request):
        from fastapi import HTTPException
        from auth.password_reset_router import reset_password, ResetPasswordIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record("x", used=True)),
        ]
        with pytest.raises(HTTPException) as exc:
            await reset_password(
                body=ResetPasswordIn(token="x" * 30, new_password="Strong1Password"),
                request=fake_request, db=db, _=None,
            )
        assert exc.value.status_code == 400
        # Password NOT updated
        assert all("UPDATE users SET password_hash" not in sql
                   for kind, (sql, _) in db.calls if kind == "execute")

    async def test_expired_token_rejected(self, fake_request):
        from fastapi import HTTPException
        from auth.password_reset_router import reset_password, ResetPasswordIn

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record("x", expires_in_minutes=-1)),
        ]
        with pytest.raises(HTTPException) as exc:
            await reset_password(
                body=ResetPasswordIn(token="x" * 30, new_password="Strong1Password"),
                request=fake_request, db=db, _=None,
            )
        assert exc.value.status_code == 400


# ── End-to-end flow: request → verify → reset ───────────────────────────────

class TestEndToEndFlow:
    async def test_full_happy_path_request_verify_reset(
        self, capturing_mailer: Mailer, fake_request,
    ):
        from auth.password_reset_router import (
            request_password_reset,
            verify_reset_token,
            reset_password,
            RequestResetIn,
            VerifyTokenIn,
            ResetPasswordIn,
        )
        # Step 1 — request
        db1 = FakeConn()
        db1.fetchrow_responses = [
            ("FROM users WHERE LOWER(email)", _user_record()),
        ]
        await request_password_reset(
            body=RequestResetIn(email="biz@example.vn"),
            request=fake_request, db=db1, _=None,
        )
        # Pull the token out of the captured email's link
        body = capturing_mailer.sender.outbox[0].get_body(preferencelist=("plain",)).get_content()
        token = body.split("token=")[1].split()[0].strip()
        assert len(token) >= 40

        # Step 2 — verify
        db2 = FakeConn()
        db2.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record(token)),
        ]
        v = await verify_reset_token(body=VerifyTokenIn(token=token), db=db2, _=None)
        assert v["valid"] is True

        # Step 3 — reset
        db3 = FakeConn()
        db3.fetchrow_responses = [
            ("FROM password_reset_tokens t", _token_record(token)),
        ]
        r = await reset_password(
            body=ResetPasswordIn(token=token, new_password="Strong1Password"),
            request=fake_request, db=db3, _=None,
        )
        assert "thành công" in r["message"]
