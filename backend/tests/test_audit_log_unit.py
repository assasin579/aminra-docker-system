"""Unit tests for backend/services/audit_log.py."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from services.audit_log import (
    build_filter_query,
    compute_diff,
    log_audit,
)


# ── compute_diff ────────────────────────────────────────────────────────────

class TestComputeDiff:
    def test_returns_only_changed_keys(self):
        diff = compute_diff(
            before={"name": "Old", "status": "draft", "company": "X"},
            after={"name": "Old", "status": "approved", "company": "X"},
        )
        assert diff == {"status": ["draft", "approved"]}

    def test_handles_added_and_removed_keys(self):
        diff = compute_diff(
            before={"a": 1, "b": 2},
            after={"a": 1, "c": 3},
        )
        assert diff == {"b": [2, None], "c": [None, 3]}

    def test_ignore_list_skips_keys(self):
        diff = compute_diff(
            before={"name": "A", "updated_at": "T1"},
            after={"name": "B", "updated_at": "T2"},
            ignore={"updated_at"},
        )
        assert diff == {"name": ["A", "B"]}

    def test_no_change_returns_empty_dict(self):
        assert compute_diff({"x": 1}, {"x": 1}) == {}


# ── log_audit — append-only behavior ────────────────────────────────────────

class TestLogAudit:
    async def test_inserts_with_full_user_context(self, mocker):
        db = mocker.AsyncMock()
        db.fetchrow.return_value = {"id": "11111111-1111-1111-1111-111111111111"}
        user = {
            "sub": "11111111-1111-1111-1111-111111111111",
            "email": "biz@example.vn",
            "role": "business",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
        }
        await log_audit(
            db,
            user=user,
            action="submission.submit",
            entity_type="submission",
            entity_id="33333333-3333-3333-3333-333333333333",
            changes={"status": ["draft", "submitted"]},
        )
        db.execute.assert_awaited_once()
        sql, args = db.execute.call_args[0][0], db.execute.call_args[0][1:]
        assert "INSERT INTO audit_logs" in sql
        assert args[0] == user["sub"]            # user_id
        assert args[1] == "biz@example.vn"       # user_email
        assert args[2] == "business"             # user_role
        assert args[3] == user["tenant_id"]
        assert args[4] == "submission.submit"
        assert args[5] == "submission"
        assert args[6] == "33333333-3333-3333-3333-333333333333"
        # changes serialized as JSON
        assert json.loads(args[7]) == {"status": ["draft", "submitted"]}

    async def test_anonymous_user_logged_with_nulls(self, mocker):
        db = mocker.AsyncMock()
        await log_audit(
            db,
            user=None,
            action="login.failed",
            entity_type="user",
        )
        args = db.execute.call_args[0][1:]
        assert args[0] is None  # user_id
        assert args[1] is None  # email
        assert args[2] is None  # role

    async def test_request_metadata_extracted(self, mocker):
        db = mocker.AsyncMock()

        # Fake FastAPI Request
        class FakeClient:
            host = "203.0.113.42"

        class FakeReq:
            client = FakeClient()
            headers = {"user-agent": "Mozilla/5.0 test"}

        await log_audit(
            db,
            action="login.success",
            entity_type="user",
            user={"sub": str(uuid4()), "email": "x@y.z"},
            request=FakeReq(),
        )
        args = db.execute.call_args[0][1:]
        meta = json.loads(args[8])
        assert meta["ip"] == "203.0.113.42"
        assert meta["user_agent"] == "Mozilla/5.0 test"

    async def test_explicit_metadata_takes_precedence_over_request(self, mocker):
        db = mocker.AsyncMock()

        class FakeReq:
            client = type("C", (), {"host": "auto-detected"})()
            headers = {"user-agent": "auto"}

        await log_audit(
            db,
            action="x",
            entity_type="y",
            metadata={"ip": "explicit"},
            request=FakeReq(),
        )
        args = db.execute.call_args[0][1:]
        meta = json.loads(args[8])
        assert meta["ip"] == "explicit"           # caller's IP wins
        assert meta["user_agent"] == "auto"       # request still fills missing

    async def test_db_failure_is_swallowed_not_raised(self, mocker, caplog):
        db = mocker.AsyncMock()
        db.execute.side_effect = RuntimeError("connection lost")

        with caplog.at_level(logging.ERROR, logger="aminra.audit_log"):
            await log_audit(
                db,
                action="x", entity_type="y",
                user={"sub": "u"},
            )
        # No exception propagated; error logged.
        assert any("audit_log" in r.name and "insert failed" in r.message for r in caplog.records)

    async def test_refuses_when_action_or_entity_missing(self, mocker, caplog):
        db = mocker.AsyncMock()
        with caplog.at_level(logging.WARNING, logger="aminra.audit_log"):
            await log_audit(db, action="", entity_type="user")
            await log_audit(db, action="x", entity_type="")
        db.execute.assert_not_called()


# ── build_filter_query ──────────────────────────────────────────────────────

class TestBuildFilterQuery:
    def test_no_filters_returns_basic_select(self):
        sql, params = build_filter_query({})
        assert "SELECT * FROM audit_logs" in sql
        assert "WHERE" not in sql
        assert "ORDER BY created_at DESC" in sql
        assert "LIMIT 50 OFFSET 0" in sql
        assert params == []

    def test_single_filter_user_id(self):
        uid = str(uuid4())
        sql, params = build_filter_query({"user_id": uid})
        assert "WHERE user_id = $1" in sql
        assert params == [uid]

    def test_multiple_filters_chained_with_and(self):
        sql, params = build_filter_query({
            "user_id": "u1",
            "action": "login.success",
            "entity_type": "user",
        })
        # Order may vary but all three filters should appear
        assert sql.count(" AND ") == 2
        assert "user_id = $" in sql
        assert "action = $" in sql
        assert "entity_type = $" in sql
        assert set(params) == {"u1", "login.success", "user"}

    def test_date_range_filter(self):
        sql, params = build_filter_query({
            "from_date": "2026-01-01T00:00:00",
            "to_date": "2026-02-01T00:00:00",
        })
        assert "created_at >= $1" in sql
        assert "created_at < $2" in sql
        assert params == ["2026-01-01T00:00:00", "2026-02-01T00:00:00"]

    def test_pagination(self):
        sql, _ = build_filter_query({}, page=3, limit=20)
        assert "LIMIT 20 OFFSET 40" in sql

    def test_unknown_filter_field_raises(self):
        with pytest.raises(ValueError, match="Unknown filter field"):
            build_filter_query({"DROP_TABLE": "users"})

    def test_invalid_sort_field_raises(self):
        with pytest.raises(ValueError, match="Invalid sort field"):
            build_filter_query({}, sort="user_id; DROP TABLE")

    def test_invalid_order_raises(self):
        with pytest.raises(ValueError, match="Invalid order"):
            build_filter_query({}, order="SHUFFLE")

    def test_limit_out_of_range_raises(self):
        with pytest.raises(ValueError, match="limit"):
            build_filter_query({}, limit=10000)
        with pytest.raises(ValueError, match="limit"):
            build_filter_query({}, limit=0)

    def test_page_zero_raises(self):
        with pytest.raises(ValueError, match="page"):
            build_filter_query({}, page=0)

    def test_empty_string_filter_skipped(self):
        sql, params = build_filter_query({"user_id": "", "action": "login"})
        assert "user_id" not in sql
        assert params == ["login"]

    def test_sql_injection_attempt_in_value_passed_as_param_not_concatenated(self):
        # Values are bound as $N params — never interpolated into SQL.
        sql, params = build_filter_query({"action": "'; DROP TABLE users; --"})
        assert "DROP TABLE" not in sql
        assert params == ["'; DROP TABLE users; --"]
