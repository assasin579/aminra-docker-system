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
