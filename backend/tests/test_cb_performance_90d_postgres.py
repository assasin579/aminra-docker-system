"""PostgreSQL-backed CB dashboard tests; writes only to a guarded disposable DB."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from urllib.parse import unquote, urlparse
from uuid import uuid4

import asyncpg
import pytest

from auth.submission_router import _resolve_cb_metrics_owner_scope, cb_performance_90d


def _disposable_dsn() -> str:
    dsn = os.environ.get("DASHBOARD_TEST_DATABASE_URL", "")
    parsed = urlparse(dsn)
    if (
        os.environ.get("DASHBOARD_TEST_DISPOSABLE") != "1"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or unquote(parsed.path.lstrip("/")) != "dashboard_test"
    ):
        pytest.fail("Require DASHBOARD_TEST_DISPOSABLE=1 and localhost/dashboard_test; refusing any other DB")
    return dsn


@pytest.mark.asyncio
async def test_canonical_owner_scope_is_read_only_and_fail_closed_in_postgres():
    conn = await asyncpg.connect(_disposable_dsn())
    try:
        async with conn.transaction():
            await conn.execute("""
                CREATE TEMP TABLE users (
                    id uuid PRIMARY KEY,
                    keycloak_sub uuid UNIQUE,
                    role text NOT NULL,
                    status text NOT NULL,
                    is_owner boolean,
                    tenant_id uuid
                ) ON COMMIT DROP
            """)
            owner_id, owner_sub, tenant_id = uuid4(), uuid4(), uuid4()
            nonowner_id, nonowner_sub = uuid4(), uuid4()
            inactive_id, inactive_sub = uuid4(), uuid4()
            legacy_owner_id, legacy_owner_sub = uuid4(), uuid4()
            await conn.execute(
                "INSERT INTO users (id, keycloak_sub, role, status, is_owner, tenant_id) "
                "VALUES ($1, $2, 'provider', 'active', true, $3), "
                "($4, $5, 'provider', 'active', false, $3), "
                "($6, $7, 'provider', 'suspended', true, $3), "
                "($8, $9, 'provider', 'active', true, NULL)",
                owner_id, owner_sub, tenant_id, nonowner_id, nonowner_sub,
                inactive_id, inactive_sub, legacy_owner_id, legacy_owner_sub,
            )

            owner_scope = await _resolve_cb_metrics_owner_scope(
                {"role": "provider", "_keycloak": True, "sub": str(owner_sub)}, conn
            )
            denied_scope = await _resolve_cb_metrics_owner_scope(
                {"role": "provider", "_keycloak": True, "sub": str(nonowner_sub), "is_owner": True}, conn
            )
            inactive_scope = await _resolve_cb_metrics_owner_scope(
                {"role": "provider", "_keycloak": True, "sub": str(inactive_sub), "is_owner": True}, conn
            )
            legacy_scope = await _resolve_cb_metrics_owner_scope(
                {"role": "provider", "_keycloak": True, "sub": str(legacy_owner_sub), "is_owner": True}, conn
            )
            assert owner_scope == tenant_id
            assert denied_scope is None
            assert inactive_scope is None
            assert legacy_scope == legacy_owner_id

            nonowner = await conn.fetchrow(
                "SELECT status, is_owner, tenant_id FROM users WHERE id = $1", nonowner_id
            )
            inactive = await conn.fetchrow(
                "SELECT status, is_owner, tenant_id FROM users WHERE id = $1", inactive_id
            )
            legacy = await conn.fetchrow(
                "SELECT status, is_owner, tenant_id FROM users WHERE id = $1", legacy_owner_id
            )
            assert (nonowner["status"], nonowner["is_owner"], nonowner["tenant_id"]) == ("active", False, tenant_id)
            assert (inactive["status"], inactive["is_owner"], inactive["tenant_id"]) == ("suspended", True, tenant_id)
            assert (legacy["status"], legacy["is_owner"], legacy["tenant_id"]) == ("active", True, None)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_cb_performance_query_filters_tenant_status_and_acceptance_windows_in_postgres():
    conn = await asyncpg.connect(_disposable_dsn())
    try:
        async with conn.transaction():
            await conn.execute("""
                CREATE TEMP TABLE users (
                    id uuid PRIMARY KEY,
                    role text NOT NULL,
                    status text NOT NULL,
                    is_owner boolean NOT NULL,
                    tenant_id uuid,
                    company_name text
                ) ON COMMIT DROP
            """)
            await conn.execute("""
                CREATE TEMP TABLE audit_visits (
                    id uuid PRIMARY KEY,
                    provider_id uuid NOT NULL,
                    auditor_id uuid,
                    status text NOT NULL,
                    report_accepted_at timestamptz,
                    created_at timestamptz NOT NULL,
                    scheduled_date date NOT NULL
                ) ON COMMIT DROP
            """)
            owner_id, auditor_id, tenant_id = uuid4(), uuid4(), uuid4()
            other_tenant = uuid4()
            await conn.execute(
                "INSERT INTO users (id, role, status, is_owner, tenant_id, company_name) VALUES "
                "($1, 'provider', 'active', true, $3, 'Synthetic CB'), "
                "($2, 'provider', 'active', false, $3, 'Synthetic Auditor')",
                owner_id, auditor_id, tenant_id,
            )

            now = datetime.now(timezone.utc)

            async def add_visit(*, provider, auditor, status, accepted_at, created_at, scheduled_date):
                await conn.execute(
                    "INSERT INTO audit_visits (id, provider_id, auditor_id, status, report_accepted_at, created_at, scheduled_date) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    uuid4(), provider, auditor, status, accepted_at, created_at, scheduled_date,
                )

            await add_visit(
                provider=tenant_id, auditor=auditor_id, status="report_accepted",
                accepted_at=now - timedelta(days=15), created_at=now - timedelta(days=17),
                scheduled_date=date.today() - timedelta(days=20),
            )
            await add_visit(
                provider=tenant_id, auditor=auditor_id, status="report_accepted",
                accepted_at=now - timedelta(days=105), created_at=now - timedelta(days=108),
                scheduled_date=date.today() - timedelta(days=110),
            )
            await add_visit(
                provider=other_tenant, auditor=auditor_id, status="report_accepted",
                accepted_at=now - timedelta(days=5), created_at=now - timedelta(days=7),
                scheduled_date=date.today() - timedelta(days=10),
            )
            await add_visit(
                provider=tenant_id, auditor=auditor_id, status="in_progress",
                accepted_at=None, created_at=now - timedelta(days=2),
                scheduled_date=date.today() - timedelta(days=3),
            )
            await add_visit(
                provider=tenant_id, auditor=auditor_id, status="report_accepted",
                accepted_at=now + timedelta(days=1), created_at=now - timedelta(days=1),
                scheduled_date=date.today() - timedelta(days=2),
            )
            await add_visit(
                provider=tenant_id, auditor=None, status="report_accepted",
                accepted_at=now - timedelta(days=20), created_at=now - timedelta(days=22),
                scheduled_date=date.today() - timedelta(days=25),
            )
            await add_visit(
                provider=tenant_id, auditor=auditor_id, status="report_accepted",
                accepted_at=now - timedelta(days=181), created_at=now - timedelta(days=183),
                scheduled_date=date.today() - timedelta(days=186),
            )

            result = await cb_performance_90d(
                {"role": "provider", "app_user_id": str(owner_id), "is_owner": None}, conn
            )
            assert result["attribution"] == "report_accepted_at"
            assert result["total"]["completed"] == {"current_90d": 1, "previous_90d": 1}
            assert result["total"]["cycle_time_hours"] == {
                "current_median": 48.0, "current_p90": 48.0,
                "previous_median": 72.0, "previous_p90": 72.0,
            }
            assert result["total"]["scheduled_to_acceptance_days"] == {
                "current_median": 5.0, "current_p90": 5.0,
                "previous_median": 5.0, "previous_p90": 5.0,
            }
            assert len(result["auditors"]) == 1
            assert result["auditors"][0]["auditor_id"] == str(auditor_id)
            assert result["auditors"][0]["name"] == "Synthetic Auditor"
            assert result["auditors"][0]["completed"] == {"current_90d": 1, "previous_90d": 1}
    finally:
        await conn.close()
