"""Tests for /auth/admin/analytics — verifies endpoint composes correctly
and returns stable shape (FE charts depend on these keys)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


ADMIN_USER = {"sub": str(uuid4()), "email": "admin@aminra.com", "role": "admin"}


def _build_db():
    db = FakeConn()
    db.fetchrow_responses = [
        # cert_buckets
        ("FROM halal_certificates", FakeRecord(
            healthy=12, expiring_90d=4, expiring_60d=3, expiring_30d=2,
            expired=1, suspended=0, revoked=2, total=24,
        )),
    ]
    db.fetch_responses = [
        # Heatmap MUST come first — `FROM audit_logs` substring would also
        # match it and steal the response.
        ("EXTRACT(DOW FROM created_at)", [
            FakeRecord(dow=1, hour=9, n=15),
            FakeRecord(dow=3, hour=14, n=8),
        ]),
        # submission_funnel
        ("FROM submissions GROUP BY status", [
            FakeRecord(status="approved", n=10),
            FakeRecord(status="reviewing", n=4),
        ]),
        # monthly_trend
        ("issue_date >= NOW() - INTERVAL '12 months'", [
            FakeRecord(month="2026-03", issued=3),
            FakeRecord(month="2026-04", issued=5),
        ]),
        # top_actions
        ("FROM audit_logs", [
            FakeRecord(action="login.success", n=42),
            FakeRecord(action="submission.submit", n=12),
        ]),
    ]
    return db


class TestAdminAnalytics:
    async def test_returns_all_five_sections(self):
        from auth.admin_analytics_router import admin_analytics
        db = _build_db()
        result = await admin_analytics(admin=ADMIN_USER, db=db)
        assert set(result.keys()) == {
            "cert_buckets", "funnel", "monthly_trend",
            "top_actions", "heatmap", "generated_at",
        }

    async def test_cert_buckets_preserve_all_keys(self):
        from auth.admin_analytics_router import admin_analytics
        result = await admin_analytics(admin=ADMIN_USER, db=_build_db())
        b = result["cert_buckets"]
        assert b["healthy"] == 12
        assert b["expiring_30d"] == 2
        assert b["expired"] == 1
        assert b["total"] == 24

    async def test_funnel_fills_zeros_for_missing_statuses(self):
        from auth.admin_analytics_router import admin_analytics
        result = await admin_analytics(admin=ADMIN_USER, db=_build_db())
        funnel = result["funnel"]
        # Returned data only had approved + reviewing — others should default to 0
        assert funnel["approved"] == 10
        assert funnel["reviewing"] == 4
        assert funnel["pending"] == 0
        assert funnel["rejected"] == 0
        assert funnel["assigned"] == 0
        assert funnel["returned"] == 0

    async def test_monthly_trend_shape(self):
        from auth.admin_analytics_router import admin_analytics
        result = await admin_analytics(admin=ADMIN_USER, db=_build_db())
        assert result["monthly_trend"] == [
            {"month": "2026-03", "issued": 3},
            {"month": "2026-04", "issued": 5},
        ]

    async def test_top_actions_sorted_desc(self):
        from auth.admin_analytics_router import admin_analytics
        result = await admin_analytics(admin=ADMIN_USER, db=_build_db())
        actions = result["top_actions"]
        assert actions[0] == {"action": "login.success", "count": 42}
        assert actions[1] == {"action": "submission.submit", "count": 12}

    async def test_heatmap_includes_dow_and_hour(self):
        from auth.admin_analytics_router import admin_analytics
        result = await admin_analytics(admin=ADMIN_USER, db=_build_db())
        cells = result["heatmap"]
        assert {"dow": 1, "hour": 9, "count": 15} in cells
        assert {"dow": 3, "hour": 14, "count": 8} in cells

    async def test_generated_at_is_iso_timestamp(self):
        from auth.admin_analytics_router import admin_analytics
        from datetime import datetime
        result = await admin_analytics(admin=ADMIN_USER, db=_build_db())
        # Should parse without raising
        datetime.fromisoformat(result["generated_at"])
