"""Unit tests for services/data_deletion.py."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


USER_ID = uuid4()


def _token_record(used: bool = False, expires_in_minutes: int = 60,
                  deleted: bool = False) -> FakeRecord:
    return FakeRecord(
        token_id=uuid4(),
        user_id=USER_ID,
        email="biz@example.vn",
        role="business",
        tenant_id=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        confirmed_at=datetime.now(timezone.utc) if used else None,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


# ── create_deletion_token ──────────────────────────────────────────────────

class TestCreateDeletionToken:
    async def test_inserts_token_and_invalidates_priors(self):
        from services.data_deletion import create_deletion_token

        db = FakeConn()
        token, expires_at = await create_deletion_token(db, str(USER_ID))

        assert isinstance(token, str)
        assert len(token) >= 40  # 32 bytes urlsafe ≈ 43 chars
        assert expires_at > datetime.now(timezone.utc)

        # Both UPDATE (invalidate priors) + INSERT executed
        executes = [(sql, args) for kind, (sql, args) in db.calls if kind == "execute"]
        assert any("UPDATE deletion_tokens" in s and "confirmed_at = NOW()" in s for s, _ in executes)
        assert any("INSERT INTO deletion_tokens" in s for s, _ in executes)


# ── confirm_and_anonymize ──────────────────────────────────────────────────

class TestConfirmAndAnonymize:
    async def test_anonymizes_user_pii_on_valid_token(self):
        from services.data_deletion import confirm_and_anonymize

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM deletion_tokens t", _token_record()),
        ]

        result = await confirm_and_anonymize(db, "good-token")

        assert result["user_id"] == str(USER_ID)
        assert result["anonymized_email"].startswith("deleted-")
        assert result["anonymized_email"].endswith("@aminra.deleted")
        assert len(result["original_email_hash"]) == 12  # short hex

        # User UPDATE includes nulled PII + deleted_at
        user_updates = [args for kind, (sql, args) in db.calls
                        if kind == "execute" and "UPDATE users" in sql and "deleted_at" in sql]
        assert len(user_updates) == 1
        new_email, uid = user_updates[0]
        assert new_email.startswith("deleted-")
        assert new_email.endswith("@aminra.deleted")
        assert str(uid) == str(USER_ID)

        # Audit logs PII redacted
        audit_anonymize = [args for kind, (sql, args) in db.calls
                           if kind == "execute" and "UPDATE audit_logs SET user_email" in sql]
        assert len(audit_anonymize) == 1
        assert str(audit_anonymize[0][0]) == str(USER_ID)

    async def test_rejects_unknown_token(self):
        from services.data_deletion import TokenInvalid, confirm_and_anonymize
        db = FakeConn()
        db.fetchrow_responses = [("FROM deletion_tokens t", None)]
        with pytest.raises(TokenInvalid, match="không tồn tại"):
            await confirm_and_anonymize(db, "x")

    async def test_rejects_used_token(self):
        from services.data_deletion import TokenInvalid, confirm_and_anonymize
        db = FakeConn()
        db.fetchrow_responses = [("FROM deletion_tokens t", _token_record(used=True))]
        with pytest.raises(TokenInvalid, match="đã được sử dụng"):
            await confirm_and_anonymize(db, "x")

    async def test_rejects_expired_token(self):
        from services.data_deletion import TokenInvalid, confirm_and_anonymize
        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM deletion_tokens t", _token_record(expires_in_minutes=-1)),
        ]
        with pytest.raises(TokenInvalid, match="hết hạn"):
            await confirm_and_anonymize(db, "x")

    async def test_rejects_already_deleted_account(self):
        from services.data_deletion import TokenInvalid, confirm_and_anonymize
        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM deletion_tokens t", _token_record(deleted=True)),
        ]
        with pytest.raises(TokenInvalid, match="đã bị xoá"):
            await confirm_and_anonymize(db, "x")

    async def test_does_not_touch_certificates_or_submissions(self):
        """Legal artifacts must remain intact (privacy policy promises this)."""
        from services.data_deletion import confirm_and_anonymize

        db = FakeConn()
        db.fetchrow_responses = [("FROM deletion_tokens t", _token_record())]
        await confirm_and_anonymize(db, "good-token")

        cert_updates = [s for kind, (s, _) in db.calls
                        if kind == "execute" and "halal_certificates" in s]
        sub_updates = [s for kind, (s, _) in db.calls
                       if kind == "execute" and "UPDATE submissions" in s]
        assert cert_updates == []
        assert sub_updates == []
