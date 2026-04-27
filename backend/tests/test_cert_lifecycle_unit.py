"""Unit tests cho services/cert_lifecycle.py.

Sử dụng FakeConn pattern (no real DB) cho fast feedback.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


CERT_ID = uuid4()
TENANT_ID = uuid4()
USER_ID = uuid4()


# ── revoke_cert ────────────────────────────────────────────────────────────

class TestRevokeCert:
    async def test_happy_path_revokes_with_reason(self):
        from services.cert_lifecycle import revoke_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates WHERE id = $1", FakeRecord(
                id=CERT_ID, cert_number="HALAL-2026-0042",
                business_tenant=TENANT_ID, status="active", revoked_at=None,
            )),
            ("UPDATE halal_certificates", FakeRecord(
                revoked_at=datetime.now(timezone.utc),
            )),
        ]

        result = await revoke_cert(
            db,
            cert_id=str(CERT_ID),
            reason="Vi phạm tiêu chuẩn JAKIM",
            revoked_by_user_id=str(USER_ID),
        )
        assert result.cert_number == "HALAL-2026-0042"
        assert result.reason == "Vi phạm tiêu chuẩn JAKIM"

    async def test_rejects_empty_reason(self):
        from services.cert_lifecycle import InvalidRevocation, revoke_cert

        db = FakeConn()
        with pytest.raises(InvalidRevocation, match="reason is required"):
            await revoke_cert(
                db,
                cert_id=str(CERT_ID),
                reason="   ",
                revoked_by_user_id=str(USER_ID),
            )

    async def test_unknown_cert_raises(self):
        from services.cert_lifecycle import CertNotFound, revoke_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates WHERE id = $1", None),
        ]
        with pytest.raises(CertNotFound):
            await revoke_cert(
                db,
                cert_id=str(uuid4()),
                reason="x",
                revoked_by_user_id=str(USER_ID),
            )

    async def test_already_revoked_raises(self):
        from services.cert_lifecycle import AlreadyRevoked, revoke_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates WHERE id = $1", FakeRecord(
                id=CERT_ID, cert_number="HALAL-2026-0042",
                business_tenant=TENANT_ID, status="revoked",
                revoked_at=datetime.now(timezone.utc),
            )),
        ]
        with pytest.raises(AlreadyRevoked):
            await revoke_cert(
                db,
                cert_id=str(CERT_ID),
                reason="late",
                revoked_by_user_id=str(USER_ID),
            )

    async def test_reason_is_trimmed(self):
        from services.cert_lifecycle import revoke_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates WHERE id = $1", FakeRecord(
                id=CERT_ID, cert_number="X", business_tenant=TENANT_ID,
                status="active", revoked_at=None,
            )),
            ("UPDATE halal_certificates", FakeRecord(
                revoked_at=datetime.now(timezone.utc),
            )),
        ]
        result = await revoke_cert(
            db, cert_id=str(CERT_ID),
            reason="   leading and trailing whitespace   ",
            revoked_by_user_id=str(USER_ID),
        )
        assert result.reason == "leading and trailing whitespace"


# ── find_expiring_certs ────────────────────────────────────────────────────

class TestFindExpiringCerts:
    async def test_returns_certs_at_each_threshold_unsent(self):
        from services.cert_lifecycle import find_expiring_certs, EXPIRY_ALERT_THRESHOLDS

        today = date(2026, 4, 25)
        db = FakeConn()
        # Mock 3 certs at different thresholds
        db.fetch_responses = [
            ("FROM halal_certificates", [
                FakeRecord(  # 90d threshold
                    id=uuid4(), cert_number="C1", business_tenant=uuid4(),
                    expiry_date=today + timedelta(days=85),  # within 90, not 60
                    expiry_alerts_sent=json.dumps([]),
                    company_name="Co A",
                ),
                FakeRecord(  # 30d threshold
                    id=uuid4(), cert_number="C2", business_tenant=uuid4(),
                    expiry_date=today + timedelta(days=20),
                    expiry_alerts_sent=json.dumps([]),
                    company_name="Co B",
                ),
                FakeRecord(  # already alerted at 90, eligible for 30
                    id=uuid4(), cert_number="C3", business_tenant=uuid4(),
                    expiry_date=today + timedelta(days=25),
                    expiry_alerts_sent=json.dumps([90, 60]),  # already sent both
                    company_name="Co C",
                ),
            ]),
        ]

        result = await find_expiring_certs(db, today=today)
        assert len(result) == 3
        thresholds = sorted([r.threshold for r in result])
        assert thresholds == [30, 30, 90]
        # C2 should match threshold 30, days_until_expiry 20
        c2 = next(r for r in result if r.cert_number == "C2")
        assert c2.threshold == 30
        assert c2.days_until_expiry == 20

    async def test_skips_already_alerted_thresholds(self):
        from services.cert_lifecycle import find_expiring_certs

        today = date(2026, 4, 25)
        db = FakeConn()
        db.fetch_responses = [
            ("FROM halal_certificates", [
                FakeRecord(
                    id=uuid4(), cert_number="C1", business_tenant=uuid4(),
                    expiry_date=today + timedelta(days=85),
                    expiry_alerts_sent=json.dumps([90]),  # already sent 90
                    company_name=None,
                ),
            ]),
        ]
        result = await find_expiring_certs(db, today=today)
        # 85 days until expiry, threshold 90 already sent → not pending
        # threshold 60 = days_until <= 60 → 85 > 60 → not yet eligible
        assert result == []

    async def test_expired_cert_uses_zero_threshold(self):
        from services.cert_lifecycle import find_expiring_certs

        today = date(2026, 4, 25)
        db = FakeConn()
        db.fetch_responses = [
            ("FROM halal_certificates", [
                FakeRecord(
                    id=uuid4(), cert_number="EXPIRED", business_tenant=uuid4(),
                    expiry_date=today - timedelta(days=2),  # already expired
                    expiry_alerts_sent=json.dumps([90, 60, 30]),
                    company_name="Late Co",
                ),
            ]),
        ]
        result = await find_expiring_certs(db, today=today)
        assert len(result) == 1
        assert result[0].threshold == 0  # expired-day alert
        assert result[0].days_until_expiry == -2

    async def test_empty_when_no_certs_close_to_expiry(self):
        from services.cert_lifecycle import find_expiring_certs

        today = date(2026, 4, 25)
        db = FakeConn()
        db.fetch_responses = [
            ("FROM halal_certificates", []),
        ]
        result = await find_expiring_certs(db, today=today)
        assert result == []


# ── mark_alert_sent ────────────────────────────────────────────────────────

class TestMarkAlertSent:
    async def test_persists_threshold_to_jsonb(self):
        from services.cert_lifecycle import mark_alert_sent

        db = FakeConn()
        await mark_alert_sent(db, str(CERT_ID), 30)
        executes = [
            (sql, args) for kind, (sql, args) in db.calls
            if kind == "execute" and "expiry_alerts_sent" in sql
        ]
        assert len(executes) == 1
        # First arg is threshold int, second is cert_id
        assert executes[0][1][0] == 30
        assert executes[0][1][1] == str(CERT_ID)
