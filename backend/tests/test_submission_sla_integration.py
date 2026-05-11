"""Integration tests cho SLA tracking — real DB + admin endpoint."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest


@pytest.fixture
async def conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
async def overdue_submission(conn):
    """Insert an overdue submission for testing escalation queue."""
    biz = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE role='business' AND is_owner=true LIMIT 1"
    )
    prov = await conn.fetchrow(
        "SELECT id FROM users WHERE role='provider' AND is_owner=true LIMIT 1"
    )
    if not biz or not prov:
        pytest.skip("Need seeded users")

    sub_id = uuid4()
    submitted = datetime.now(timezone.utc) - timedelta(days=30)
    deadline = datetime.now(timezone.utc) - timedelta(days=5)
    await conn.execute(
        """
        INSERT INTO submissions
            (id, business_tenant, provider_id, document_ids, status, company_name,
             submitted_at, deadline)
        VALUES ($1, $2, $3, '{}'::uuid[], 'reviewing', 'OverdueTest', $4, $5)
        """,
        sub_id, biz["tenant_id"], prov["id"], submitted, deadline,
    )
    yield {"submission_id": str(sub_id), "provider_id": str(prov["id"])}
    await conn.execute("DELETE FROM submissions WHERE id = $1", sub_id)


# ── list_overdue_submissions ───────────────────────────────────────────────

class TestListOverdueIntegration:
    async def test_overdue_submission_appears_in_query(self, conn, overdue_submission):
        from services.submission_sla import list_overdue_submissions

        items = await list_overdue_submissions(conn, limit=200)
        ids = [i["submission_id"] for i in items]
        assert overdue_submission["submission_id"] in ids

        item = next(i for i in items if i["submission_id"] == overdue_submission["submission_id"])
        assert item["status"] == "reviewing"
        assert item["days_overdue"] >= 4  # ~5 days overdue

    async def test_excludes_approved_submissions(self, conn, overdue_submission):
        from services.submission_sla import list_overdue_submissions

        # Mark as approved → should disappear from queue
        await conn.execute(
            "UPDATE submissions SET status='approved' WHERE id = $1",
            overdue_submission["submission_id"],
        )
        items = await list_overdue_submissions(conn, limit=200)
        ids = [i["submission_id"] for i in items]
        assert overdue_submission["submission_id"] not in ids


# ── find_at_risk_submissions e2e ───────────────────────────────────────────

class TestFindAtRiskIntegration:
    async def test_at_risk_includes_overdue(self, conn, overdue_submission):
        from services.submission_sla import find_at_risk_submissions

        result = await find_at_risk_submissions(conn)
        ids = [r.submission_id for r in result]
        # Our overdue submission should be in the at-risk list with threshold=100 OR 80
        assert overdue_submission["submission_id"] in ids
        item = next(r for r in result if r.submission_id == overdue_submission["submission_id"])
        # 30-day window + 5 days past deadline = elapsed 35/30 ~117% → threshold=80 (first unsent)
        assert item.threshold in (80, 100)


# ── Admin endpoint ─────────────────────────────────────────────────────────

class TestAdminOverdueEndpoint:
    async def test_admin_can_view_queue(self, conn, overdue_submission):
        from auth.admin_router import admin_overdue_submissions

        admin_user = {
            "sub": str(uuid4()),
            "email": "admin@aminra.com",
            "role": "admin",
        }
        result = await admin_overdue_submissions(
            limit=200, admin=admin_user, db=conn,
        )
        assert "items" in result
        assert "count" in result
        assert overdue_submission["submission_id"] in [i["submission_id"] for i in result["items"]]


# ── Provider scope (cross-tenant isolation) ────────────────────────────────


@pytest.fixture
async def overdue_two_providers(conn):
    """Insert 1 overdue submission for provider A + 1 for provider B."""
    biz = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE role='business' AND is_owner=true LIMIT 1"
    )
    provs = await conn.fetch(
        "SELECT id FROM users WHERE role='provider' AND is_owner=true LIMIT 2"
    )
    if not biz or len(provs) < 2:
        pytest.skip("Need ≥2 seeded providers")

    sub_a, sub_b = uuid4(), uuid4()
    submitted = datetime.now(timezone.utc) - timedelta(days=30)
    deadline = datetime.now(timezone.utc) - timedelta(days=5)
    for sub_id, prov in [(sub_a, provs[0]), (sub_b, provs[1])]:
        await conn.execute(
            """
            INSERT INTO submissions
                (id, business_tenant, provider_id, document_ids, status, company_name,
                 submitted_at, deadline)
            VALUES ($1, $2, $3, '{}'::uuid[], 'reviewing', 'XTenantOverdue', $4, $5)
            """,
            sub_id, biz["tenant_id"], prov["id"], submitted, deadline,
        )
    yield {
        "sub_a": str(sub_a), "prov_a": str(provs[0]["id"]),
        "sub_b": str(sub_b), "prov_b": str(provs[1]["id"]),
    }
    await conn.execute("DELETE FROM submissions WHERE id = ANY($1::uuid[])", [sub_a, sub_b])


class TestProviderScopeIsolation:
    async def test_provider_a_sees_only_own(self, conn, overdue_two_providers):
        """Provider A's overdue list MUST exclude provider B's submission."""
        from services.submission_sla import list_overdue_submissions

        items = await list_overdue_submissions(
            conn, limit=200, provider_id=overdue_two_providers["prov_a"],
        )
        ids = {i["submission_id"] for i in items}
        assert overdue_two_providers["sub_a"] in ids
        assert overdue_two_providers["sub_b"] not in ids

    async def test_provider_b_sees_only_own(self, conn, overdue_two_providers):
        from services.submission_sla import list_overdue_submissions

        items = await list_overdue_submissions(
            conn, limit=200, provider_id=overdue_two_providers["prov_b"],
        )
        ids = {i["submission_id"] for i in items}
        assert overdue_two_providers["sub_b"] in ids
        assert overdue_two_providers["sub_a"] not in ids

    async def test_admin_unscoped_sees_both(self, conn, overdue_two_providers):
        """Without scope param, admin path sees cross-tenant."""
        from services.submission_sla import list_overdue_submissions

        items = await list_overdue_submissions(conn, limit=200)
        ids = {i["submission_id"] for i in items}
        assert overdue_two_providers["sub_a"] in ids
        assert overdue_two_providers["sub_b"] in ids

    async def test_auditor_filter_supersedes_provider(self, conn, overdue_two_providers):
        """When both provided, auditor_id (narrower) wins. Auditor unassigned →
        no auditor_id matches → empty result (defensive)."""
        from services.submission_sla import list_overdue_submissions

        items = await list_overdue_submissions(
            conn, limit=200,
            provider_id=overdue_two_providers["prov_a"],
            auditor_id=str(uuid4()),  # random — no submission has this auditor
        )
        ids = {i["submission_id"] for i in items}
        assert overdue_two_providers["sub_a"] not in ids
        assert overdue_two_providers["sub_b"] not in ids
