"""Unit tests cho services/submission_sla.py — fake DB, no network."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


def _now() -> datetime:
    return datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)


# ── find_at_risk_submissions ──────────────────────────────────────────────

class TestFindAtRiskSubmissions:
    async def test_returns_80_threshold_when_85pct_elapsed(self):
        from services.submission_sla import find_at_risk_submissions

        now = _now()
        submitted = now - timedelta(days=85)
        deadline = submitted + timedelta(days=100)  # 100-day window

        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions", [
                FakeRecord(
                    id=uuid4(),
                    business_tenant=uuid4(),
                    provider_id=uuid4(),
                    company_name="X",
                    submitted_at=submitted,
                    deadline=deadline,
                    status="reviewing",
                    sla_alerts_sent=json.dumps([]),
                ),
            ]),
        ]
        result = await find_at_risk_submissions(db, now=now)
        assert len(result) == 1
        assert result[0].threshold == 80
        assert result[0].elapsed_pct >= 80

    async def test_returns_100_threshold_when_overdue(self):
        from services.submission_sla import find_at_risk_submissions

        now = _now()
        submitted = now - timedelta(days=110)
        deadline = submitted + timedelta(days=100)  # already past

        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions", [
                FakeRecord(
                    id=uuid4(),
                    business_tenant=uuid4(),
                    provider_id=uuid4(),
                    company_name=None,
                    submitted_at=submitted,
                    deadline=deadline,
                    status="reviewing",
                    sla_alerts_sent=json.dumps([80]),  # 80 already sent → next is 100
                ),
            ]),
        ]
        result = await find_at_risk_submissions(db, now=now)
        assert len(result) == 1
        assert result[0].threshold == 100
        assert result[0].days_remaining < 0

    async def test_skips_already_alerted_thresholds(self):
        from services.submission_sla import find_at_risk_submissions

        now = _now()
        submitted = now - timedelta(days=85)
        deadline = submitted + timedelta(days=100)

        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions", [
                FakeRecord(
                    id=uuid4(), business_tenant=uuid4(), provider_id=uuid4(),
                    company_name=None, submitted_at=submitted, deadline=deadline,
                    status="reviewing",
                    sla_alerts_sent=json.dumps([80]),  # already alerted
                ),
            ]),
        ]
        result = await find_at_risk_submissions(db, now=now)
        # Only 100% threshold remains, but elapsed is 85% → not yet → no result
        assert result == []

    async def test_skips_terminal_states(self):
        from services.submission_sla import find_at_risk_submissions

        # SQL-level filter excludes 'approved' so query never returns it.
        # The query in fetch_responses is what matters. We pass empty list to simulate.
        db = FakeConn()
        db.fetch_responses = [("FROM submissions", [])]
        result = await find_at_risk_submissions(db, now=_now())
        assert result == []

    async def test_handles_zero_window_gracefully(self):
        from services.submission_sla import find_at_risk_submissions

        now = _now()
        # Malformed: submitted_at == deadline. Should skip, not crash.
        same = now - timedelta(days=10)
        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions", [
                FakeRecord(
                    id=uuid4(), business_tenant=uuid4(), provider_id=uuid4(),
                    company_name=None,
                    submitted_at=same, deadline=same,
                    status="reviewing",
                    sla_alerts_sent=json.dumps([]),
                ),
            ]),
        ]
        result = await find_at_risk_submissions(db, now=now)
        assert result == []


# ── mark_sla_alert_sent ────────────────────────────────────────────────────

class TestMarkAlertSent:
    async def test_persists_threshold(self):
        from services.submission_sla import mark_sla_alert_sent

        sub_id = str(uuid4())
        db = FakeConn()
        await mark_sla_alert_sent(db, sub_id, 80)
        executes = [
            (sql, args) for kind, (sql, args) in db.calls
            if kind == "execute" and "sla_alerts_sent" in sql
        ]
        assert len(executes) == 1
        sql, args = executes[0]
        assert "? $1::text" in sql
        assert "to_jsonb($2::int)" in sql
        assert args == ("80", 80, sub_id)


# ── list_overdue_submissions ──────────────────────────────────────────────

class TestListOverdue:
    async def test_returns_serialized_rows(self):
        from services.submission_sla import list_overdue_submissions

        now = _now()
        deadline = now - timedelta(days=3)
        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions s", [
                FakeRecord(
                    id=uuid4(), company_name="Late Co",
                    status="reviewing",
                    submitted_at=now - timedelta(days=30),
                    deadline=deadline,
                    provider_email="cb@x.vn",
                    provider_name="Halal CB",
                    days_overdue=3.2,
                ),
            ]),
        ]
        result = await list_overdue_submissions(db, limit=50)
        assert len(result) == 1
        item = result[0]
        assert item["company_name"] == "Late Co"
        assert item["provider_email"] == "cb@x.vn"
        assert item["days_overdue"] == 3.2
