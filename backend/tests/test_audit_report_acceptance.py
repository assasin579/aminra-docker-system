"""Regression tests for CB report acceptance and audit-completion metrics.

These tests use a recording fake connection; they never connect to the application
or any configured database. Migration execution is validated separately against a
disposable PostgreSQL database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException



class Record(dict):
    """Small asyncpg.Record substitute."""


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingDB:
    def __init__(self):
        self.calls = []
        self.canonical_user_row: Record | None = None
        self.visit_status = "report_submitted"
        self.visit_row = Record(status="report_submitted")
        self.accept_update_result = Record(
            status="report_accepted",
            report_accepted_at=datetime(2026, 10, 25, 12, tzinfo=timezone.utc),
        )
        self.fetchval_responses = []
        self.fetchrow_responses = []
        self.fetch_responses = []
        self.execute_result = "UPDATE 1"

    def transaction(self):
        return _Transaction()

    def _response(self, sql, responses):
        for needle, value in responses:
            if needle in sql:
                return value
        raise AssertionError(f"No fake response for SQL: {sql[:160]!r}")

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        normalized = " ".join(sql.split())
        if "SELECT id, role, status, is_owner, tenant_id FROM users" in normalized:
            return self.canonical_user_row
        if "SELECT status FROM audit_visits" in normalized:
            return Record(status=self.visit_status)
        if "SELECT * FROM audit_visits" in normalized:
            return self.visit_row
        if "UPDATE audit_visits SET status='report_accepted'" in normalized:
            return self.accept_update_result
        if self.fetchrow_responses:
            return self._response(sql, self.fetchrow_responses)
        raise AssertionError(f"Unexpected fetchrow: {sql[:160]!r}")

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return self._response(sql, self.fetchval_responses)

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self._response(sql, self.fetch_responses)

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return self.execute_result


def _route_endpoint(router, path):
    return next(
        (getattr(route, "endpoint", None) for route in router.routes if getattr(route, "path", None) == path),
        None,
    )


async def test_only_cb_owner_can_accept_and_no_db_work_happens_for_non_owner():
    from auth import audit_router

    db = RecordingDB()
    user = {"role": "provider", "is_owner": False, "sub": str(uuid4())}
    endpoint = _route_endpoint(audit_router.router, "/{vid}/accept-report")
    assert endpoint is not None, "missing CB-owner report-acceptance route"

    with pytest.raises(HTTPException) as exc:
        await endpoint(str(uuid4()), user, db)

    assert exc.value.status_code == 403
    assert db.calls == []


async def test_cb_owner_accepts_only_submitted_report_and_records_actor(monkeypatch):
    from auth import audit_router

    provider_id, owner_id, visit_id = uuid4(), uuid4(), uuid4()
    db = RecordingDB()
    user = {"role": "provider", "is_owner": True, "sub": str(owner_id)}

    async def tenant_id(_user, _db):
        return provider_id

    async def actor_id(_user, _db):
        return owner_id

    monkeypatch.setattr(audit_router, "resolve_canonical_tenant_id", tenant_id)
    monkeypatch.setattr(audit_router, "resolve_canonical_user_id", actor_id)
    endpoint = _route_endpoint(audit_router.router, "/{vid}/accept-report")
    assert endpoint is not None, "missing CB-owner report-acceptance route"

    result = await endpoint(str(visit_id), user, db)

    assert result["status"] == "report_accepted"
    assert result["report_accepted_by"] == str(owner_id)
    select = next(sql for kind, sql, _ in db.calls if kind == "fetchrow" and "SELECT status FROM audit_visits" in sql)
    update = next(
        " ".join(sql.split())
        for kind, sql, _ in db.calls
        if kind == "fetchrow" and "UPDATE audit_visits SET status='report_accepted'" in " ".join(sql.split())
    )
    assert "provider_id=$2" in select and "FOR UPDATE" in select
    assert "status='report_submitted'" in update
    assert "report_accepted_at=now()" in update
    assert "report_accepted_by=$3" in update


async def test_cb_owner_cannot_accept_report_in_wrong_state(monkeypatch):
    from auth import audit_router

    db = RecordingDB()
    db.visit_status = "completed"
    endpoint = _route_endpoint(audit_router.router, "/{vid}/accept-report")
    assert endpoint is not None, "missing CB-owner report-acceptance route"

    async def tenant_id(_user, _db):
        return uuid4()

    async def actor_id(_user, _db):
        return uuid4()

    monkeypatch.setattr(audit_router, "resolve_canonical_tenant_id", tenant_id)
    monkeypatch.setattr(audit_router, "resolve_canonical_user_id", actor_id)
    with pytest.raises(HTTPException) as exc:
        await endpoint(str(uuid4()), {"role": "provider", "is_owner": True}, db)

    assert exc.value.status_code == 409
    assert not any("UPDATE audit_visits SET status='report_accepted'" in sql for _, sql, _ in db.calls)


async def test_assigned_auditor_submits_but_owner_cannot_bypass_acceptance(monkeypatch):
    from auth import audit_router

    visit_id, auditor_id = uuid4(), uuid4()
    db = RecordingDB()
    endpoint = audit_router.update_visit_status

    async def audit_filter(_user, _db):
        return "auditor_id = $1", auditor_id

    monkeypatch.setattr(audit_router, "_audit_filter", audit_filter)
    owner = {"role": "provider", "is_owner": True, "sub": str(uuid4())}
    with pytest.raises(HTTPException) as exc:
        await endpoint(str(visit_id), {"status": "report_submitted"}, owner, db)
    assert exc.value.status_code == 403
    assert db.calls == []

    auditor = {"role": "provider", "is_owner": False, "sub": str(auditor_id)}
    result = await endpoint(str(visit_id), {"status": "report_submitted"}, auditor, db)
    assert "report_submitted" in result["message"]
    update_sql, update_args = next(
        (sql, args) for kind, sql, args in db.calls if kind == "execute" and "UPDATE audit_visits SET status" in sql
    )
    update_sql = " ".join(update_sql.split())
    assert "status = 'completed'" in update_sql
    assert "auditor_id = $3" in update_sql
    assert update_args[0] == "report_submitted"


async def test_report_generation_is_assigned_auditor_only(monkeypatch):
    from auth import audit_router

    db = RecordingDB()
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("authorization must reject before loading or mutating the visit")

    monkeypatch.setattr(audit_router, "assert_audit_visit_mutation_scope", should_not_run)
    with pytest.raises(HTTPException) as exc:
        await audit_router.generate_report(
            str(uuid4()),
            {"role": "provider", "is_owner": True, "sub": str(uuid4())},
            db,
        )

    assert exc.value.status_code == 403
    assert db.calls == []


async def test_report_generation_requires_completed_visit(monkeypatch):
    from auth import audit_router

    db = RecordingDB()
    db.visit_row = Record(status="report_submitted")

    async def allowed_scope(*_args, **_kwargs):
        return object()

    monkeypatch.setattr(audit_router, "assert_audit_visit_mutation_scope", allowed_scope)
    with pytest.raises(HTTPException) as exc:
        await audit_router.generate_report(
            str(uuid4()),
            {"role": "provider", "is_owner": False, "sub": str(uuid4())},
            db,
        )

    assert exc.value.status_code == 409
    assert len(db.calls) == 1
    assert "SELECT * FROM audit_visits" in db.calls[0][1]


async def test_accepted_visit_cannot_be_reopened_via_generic_status_endpoint(monkeypatch):
    from auth import audit_router

    db = RecordingDB()
    db.visit_status = "report_accepted"
    db.execute_result = "UPDATE 0"

    async def audit_filter(_user, _db):
        return "provider_id = $1", uuid4()

    monkeypatch.setattr(audit_router, "_audit_filter", audit_filter)
    with pytest.raises(HTTPException) as exc:
        await audit_router.update_visit_status(
            str(uuid4()),
            {"status": "completed"},
            {"role": "provider", "is_owner": True},
            db,
        )

    assert exc.value.status_code == 409
    update_sql = next(sql for kind, sql, _ in db.calls if kind == "execute" and "UPDATE audit_visits SET status" in sql)
    assert "status <> 'report_accepted'" in update_sql


async def test_cb_dashboard_completed_metric_counts_only_cb_accepted_reports():
    from auth import submission_router

    provider_id, owner_id = uuid4(), uuid4()
    db = RecordingDB()
    db.canonical_user_row = Record(
        id=owner_id, role="provider", status="active", is_owner=True, tenant_id=provider_id
    )
    db.fetchval_responses = [("COUNT(DISTINCT business_tenant)", 3)]
    db.fetchrow_responses = [
        ("FROM halal_certificates WHERE issued_by=$1", Record(total=2, active=2, expiring_soon=0, inactive=0)),
        ("FROM audit_visits WHERE provider_id=$1", Record(total=4, completed=1, avg_compliance=90)),
        ("FROM submissions WHERE provider_id=$1", Record(pending=0, reviewing=0, approved=2, total=2, avg_hours=8.0)),
    ]
    db.fetch_responses = [
        ("FROM users a", []),
        ("FROM halal_certificates", []),
    ]

    result = await submission_router.cb_stats({
        "role": "provider", "realm_roles": ["cb_admin"],
        "app_user_id": str(owner_id), "is_owner": False, "tenant_id": str(uuid4()),
    }, db)

    assert result["audits"]["completed"] == 1
    assert db.calls[0][2] == (owner_id,)
    audits_sql = next(sql for kind, sql, _ in db.calls if kind == "fetchrow" and "FROM audit_visits" in sql)
    audits_sql = " ".join(audits_sql.split())
    assert "status='report_accepted'" in audits_sql
    assert "status IN ('completed','report_submitted')" not in audits_sql
    assert "AVG(compliance_score) FILTER (WHERE status='report_accepted' AND compliance_score IS NOT NULL)" in audits_sql


async def test_cb_metrics_remain_owner_only():
    from auth import submission_router

    endpoint = _route_endpoint(submission_router.router, "/cb-stats")
    assert endpoint is not None
    for user in (
        {"role": "provider", "is_owner": False},
        {"role": "provider", "is_owner": True, "realm_roles": ["platform_admin"]},
    ):
        db = RecordingDB()
        with pytest.raises(HTTPException) as exc:
            await endpoint(user, db)
        assert exc.value.status_code == 403
        assert db.calls == []


def test_migration_adds_acceptance_state_and_guards_downgrade():
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "053_audit_report_acceptance.py"
    assert migration.exists(), "missing additive CB report acceptance migration"
    text = migration.read_text()
    assert 'down_revision = "052_mobile_replay_idem"' in text
    assert "report_accepted_at TIMESTAMPTZ" in text
    assert "report_accepted_by UUID REFERENCES users(id)" in text
    assert "report_accepted" in text
    assert "Cannot downgrade while accepted audit reports exist" in text
