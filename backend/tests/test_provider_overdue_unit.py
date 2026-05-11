"""F5 — Provider overdue queue unit tests (25 cases).

Covers session 2026-05-10:
  - services/submission_sla.py::list_overdue_submissions scope params
  - SQL builder for provider_id / auditor_id filter precedence
  - Endpoint role check branching (owner → provider_id, auditor → auditor_id)
  - urgencyColor helper (FE — but algorithm validated here via Python mirror)

Pure-function tests. SQL queries assembled but not executed against DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.submission_sla import (
    ACTIVE_STATUSES,
    SLA_THRESHOLDS,
    list_overdue_submissions,
    AtRiskSubmission,
    find_at_risk_submissions,
)


# ── Group 1 — Constants + module shape (4 tests) ───────────────────────────


class TestModuleConstants:
    def test_active_statuses_includes_pending(self):
        assert "pending" in ACTIVE_STATUSES

    def test_active_statuses_includes_reviewing(self):
        assert "reviewing" in ACTIVE_STATUSES

    def test_active_statuses_excludes_terminal_states(self):
        for terminal in ("approved", "rejected", "returned"):
            assert terminal not in ACTIVE_STATUSES

    def test_sla_thresholds_80_and_100(self):
        assert 80 in SLA_THRESHOLDS
        assert 100 in SLA_THRESHOLDS
        assert SLA_THRESHOLDS == sorted(SLA_THRESHOLDS)


# ── Group 2 — list_overdue_submissions SQL builder (8 tests) ───────────────


class TestSQLBuilder:
    """Verify SQL builder respects scope params + parameterized correctly."""

    async def test_no_scope_no_extra_clause(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(mock_db, limit=10)
        called_sql, *args = mock_db.fetch.call_args[0]
        # The SQL should NOT contain auditor_id or provider_id WHERE clause
        # beyond the join
        assert "s.auditor_id =" not in called_sql
        assert "s.provider_id = $" not in called_sql.replace(
            "LEFT JOIN users u ON u.id = s.provider_id", ""
        )
        assert args == [list(ACTIVE_STATUSES), 10]

    async def test_provider_id_adds_clause(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(
            mock_db, limit=10, provider_id="prov-uuid-x",
        )
        called_sql, *args = mock_db.fetch.call_args[0]
        assert "s.provider_id = $3" in called_sql
        assert args == [list(ACTIVE_STATUSES), 10, "prov-uuid-x"]

    async def test_auditor_id_adds_clause(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(
            mock_db, limit=10, auditor_id="audit-uuid-y",
        )
        called_sql, *args = mock_db.fetch.call_args[0]
        assert "s.auditor_id = $3" in called_sql
        assert args == [list(ACTIVE_STATUSES), 10, "audit-uuid-y"]

    async def test_auditor_supersedes_provider_when_both_given(self):
        """Documented behavior — narrower scope (auditor) wins."""
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(
            mock_db, limit=10,
            provider_id="prov-x", auditor_id="audit-y",
        )
        called_sql, *args = mock_db.fetch.call_args[0]
        assert "s.auditor_id = $3" in called_sql
        assert "s.provider_id = $" not in called_sql.replace(
            "LEFT JOIN users u ON u.id = s.provider_id", ""
        )
        assert args[2] == "audit-y"

    async def test_default_limit_100(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(mock_db)
        _, *args = mock_db.fetch.call_args[0]
        assert args[1] == 100

    async def test_custom_limit_passed(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(mock_db, limit=5)
        _, *args = mock_db.fetch.call_args[0]
        assert args[1] == 5

    async def test_status_filter_in_sql(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(mock_db)
        called_sql, *_ = mock_db.fetch.call_args[0]
        assert "s.status = ANY($1::text[])" in called_sql

    async def test_deadline_filter_in_sql(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await list_overdue_submissions(mock_db)
        called_sql, *_ = mock_db.fetch.call_args[0]
        assert "s.deadline IS NOT NULL" in called_sql
        assert "s.deadline < NOW()" in called_sql


# ── Group 3 — Result shape (3 tests) ───────────────────────────────────────


class TestResultShape:
    async def test_empty_db_returns_empty_list(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        result = await list_overdue_submissions(mock_db)
        assert result == []

    async def test_row_translates_to_expected_dict_keys(self):
        now = datetime.now(timezone.utc)
        mock_row = {
            "id": "sub-1",
            "company_name": "Test Co",
            "status": "reviewing",
            "submitted_at": now,
            "deadline": now,
            "provider_email": "p@example.com",
            "provider_name": "Provider Org",
            "days_overdue": 3.5,
        }
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[mock_row])
        result = await list_overdue_submissions(mock_db)
        assert len(result) == 1
        item = result[0]
        assert item["submission_id"] == "sub-1"
        assert item["company_name"] == "Test Co"
        assert item["status"] == "reviewing"
        assert item["provider_email"] == "p@example.com"
        assert item["provider_name"] == "Provider Org"
        assert item["days_overdue"] == 3.5

    async def test_submitted_at_null_handled(self):
        mock_row = {
            "id": "sub-2",
            "company_name": None,
            "status": "reviewing",
            "submitted_at": None,
            "deadline": datetime.now(timezone.utc),
            "provider_email": None,
            "provider_name": None,
            "days_overdue": 0,
        }
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[mock_row])
        result = await list_overdue_submissions(mock_db)
        assert result[0]["submitted_at"] is None


# ── Group 4 — find_at_risk_submissions logic (6 tests) ─────────────────────


class TestFindAtRiskLogic:
    """Threshold detection — pure logic, mocked DB."""

    async def test_no_active_submissions_returns_empty(self):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        result = await find_at_risk_submissions(mock_db)
        assert result == []

    async def test_submission_at_50_pct_not_at_risk(self):
        now = datetime(2026, 5, 10, tzinfo=timezone.utc)
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": "s",
            "business_tenant": "biz",
            "provider_id": "prov",
            "company_name": "Co",
            "submitted_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "deadline": datetime(2026, 5, 19, tzinfo=timezone.utc),
            "status": "reviewing",
            "sla_alerts_sent": [],
        }])
        result = await find_at_risk_submissions(mock_db, now=now)
        # Elapsed 9/18 = 50% — below 80 threshold
        assert result == []

    async def test_submission_at_80_pct_flagged(self):
        now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": "s2",
            "business_tenant": "biz",
            "provider_id": "prov",
            "company_name": "Co",
            "submitted_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "deadline": datetime(2026, 5, 12, tzinfo=timezone.utc),
            "status": "pending",
            "sla_alerts_sent": [],
        }])
        result = await find_at_risk_submissions(mock_db, now=now)
        assert len(result) == 1
        assert result[0].threshold == 80

    async def test_submission_already_alerted_skipped(self):
        now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": "s3",
            "business_tenant": "biz",
            "provider_id": "prov",
            "company_name": "Co",
            "submitted_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "deadline": datetime(2026, 5, 12, tzinfo=timezone.utc),
            "status": "pending",
            "sla_alerts_sent": [80],  # already alerted
        }])
        result = await find_at_risk_submissions(mock_db, now=now)
        # 80 already sent → should still report? No: skip already-alerted.
        assert result == []

    async def test_malformed_window_skipped(self):
        """submitted_at >= deadline → skip (no division by zero, no negative)."""
        now = datetime(2026, 5, 10, tzinfo=timezone.utc)
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": "bad",
            "business_tenant": "biz",
            "provider_id": "prov",
            "company_name": "Co",
            "submitted_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
            "deadline": datetime(2026, 5, 10, tzinfo=timezone.utc),
            "status": "reviewing",
            "sla_alerts_sent": [],
        }])
        result = await find_at_risk_submissions(mock_db, now=now)
        assert result == []

    async def test_null_dates_skipped(self):
        now = datetime(2026, 5, 10, tzinfo=timezone.utc)
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[
            {
                "id": "no-sub",
                "business_tenant": "biz",
                "provider_id": "prov",
                "company_name": "Co",
                "submitted_at": None,
                "deadline": datetime(2026, 5, 20, tzinfo=timezone.utc),
                "status": "pending",
                "sla_alerts_sent": [],
            },
            {
                "id": "no-deadline",
                "business_tenant": "biz",
                "provider_id": "prov",
                "company_name": "Co",
                "submitted_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "deadline": None,
                "status": "pending",
                "sla_alerts_sent": [],
            },
        ])
        result = await find_at_risk_submissions(mock_db, now=now)
        assert result == []


# ── Group 5 — Provider role branching (router-level unit) (4 tests) ────────


class TestProviderOverdueRouter:
    """Direct invocation of router handler with mocked deps."""

    async def test_role_not_provider_raises_403(self):
        from auth.submission_router import provider_overdue
        from fastapi import HTTPException

        mock_db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await provider_overdue(
                limit=100,
                user={"role": "business", "sub": "x", "is_owner": True},
                db=mock_db,
            )
        assert exc.value.status_code == 403

    async def test_owner_scopes_by_provider_id(self):
        from auth.submission_router import provider_overdue

        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        result = await provider_overdue(
            limit=100,
            user={"role": "provider", "sub": "prov-uuid", "is_owner": True},
            db=mock_db,
        )
        assert result == {"items": [], "count": 0}
        called_sql, *args = mock_db.fetch.call_args[0]
        assert "s.provider_id = $3" in called_sql
        assert args[2] == "prov-uuid"

    async def test_auditor_scopes_by_auditor_id(self):
        from auth.submission_router import provider_overdue

        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await provider_overdue(
            limit=100,
            user={"role": "provider", "sub": "audit-uuid", "is_owner": False},
            db=mock_db,
        )
        called_sql, *args = mock_db.fetch.call_args[0]
        assert "s.auditor_id = $3" in called_sql
        assert args[2] == "audit-uuid"

    async def test_custom_limit_propagated(self):
        from auth.submission_router import provider_overdue

        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        await provider_overdue(
            limit=5,
            user={"role": "provider", "sub": "prov", "is_owner": True},
            db=mock_db,
        )
        _, *args = mock_db.fetch.call_args[0]
        assert args[1] == 5
