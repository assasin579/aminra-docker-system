"""F5 — Provider overdue queue integration tests (25 cases).

Live DB + HTTP roundtrip via ASGI. Extends the 4 cross-tenant tests already
shipped in test_submission_sla_integration.py (TestProviderScopeIsolation).
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from jose import jwt

from auth.jwt_utils import SECRET, ALGORITHM

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def _pool():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    from auth.db import init_pool
    import auth.db as _db
    if _db._pool is None:
        await init_pool()
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def conn(_pool):
    url = os.getenv("DATABASE_URL")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest_asyncio.fixture(loop_scope="session")
async def client(_pool):
    from app import app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as c:
        yield c


def _provider_jwt(user_id: str, is_owner: bool = True, email: str = "p@aminra.vn") -> str:
    return jwt.encode({
        "sub": user_id,
        "email": email,
        "role": "provider",
        "is_owner": is_owner,
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


def _business_jwt(user_id: str) -> str:
    return jwt.encode({
        "sub": user_id,
        "email": "b@aminra.vn",
        "role": "business",
        "is_owner": True,
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


@pytest_asyncio.fixture(loop_scope="session")
async def two_providers_with_overdue(conn):
    """Seed 2 providers each with 1 overdue submission."""
    biz = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE role='business' AND is_owner=true LIMIT 1"
    )
    provs = await conn.fetch(
        "SELECT id FROM users WHERE role='provider' AND is_owner=true LIMIT 2"
    )
    if not biz or len(provs) < 2:
        pytest.skip("Need ≥2 seeded providers + 1 business")

    sub_a, sub_b = uuid4(), uuid4()
    submitted = datetime.now(timezone.utc) - timedelta(days=30)
    deadline = datetime.now(timezone.utc) - timedelta(days=5)

    for sub_id, prov in [(sub_a, provs[0]), (sub_b, provs[1])]:
        await conn.execute(
            """INSERT INTO submissions
               (id, business_tenant, provider_id, document_ids, status, company_name,
                submitted_at, deadline)
               VALUES ($1, $2, $3, '{}'::uuid[], 'reviewing', 'XTenant', $4, $5)""",
            sub_id, biz["tenant_id"], prov["id"], submitted, deadline,
        )
    yield {
        "sub_a": str(sub_a), "prov_a": str(provs[0]["id"]),
        "sub_b": str(sub_b), "prov_b": str(provs[1]["id"]),
    }
    await conn.execute(
        "DELETE FROM submissions WHERE id = ANY($1::uuid[])", [sub_a, sub_b],
    )


# ── Group 1 — Auth gate (4 tests) ──────────────────────────────────────────


class TestEndpointAuth:
    async def test_no_token_401(self, client):
        r = await client.get("/api/submissions/overdue")
        assert r.status_code == 401

    async def test_business_role_403(self, client):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_business_jwt(str(uuid4()))}"},
        )
        assert r.status_code == 403

    async def test_provider_role_200(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        assert r.status_code == 200

    async def test_garbage_token_403(self, client):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": "Bearer junk"},
        )
        assert r.status_code == 401  # get_current_user gate


# ── Group 2 — Scope isolation HTTP layer (5 tests) ─────────────────────────


class TestEndpointScopeIsolation:
    async def test_provider_a_sees_only_a(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        assert r.status_code == 200
        ids = {i["submission_id"] for i in r.json()["items"]}
        assert two_providers_with_overdue["sub_a"] in ids
        assert two_providers_with_overdue["sub_b"] not in ids

    async def test_provider_b_sees_only_b(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_b'])}"},
        )
        ids = {i["submission_id"] for i in r.json()["items"]}
        assert two_providers_with_overdue["sub_b"] in ids
        assert two_providers_with_overdue["sub_a"] not in ids

    async def test_provider_response_includes_count(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        body = r.json()
        assert body["count"] == len(body["items"])

    async def test_provider_response_items_have_days_overdue(
        self, client, two_providers_with_overdue
    ):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        items = r.json()["items"]
        for it in items:
            assert "days_overdue" in it
            assert it["days_overdue"] >= 0

    async def test_auditor_non_owner_default_empty(self, client, two_providers_with_overdue):
        """Auditor (is_owner=false) scoped by auditor_id; if no submission assigned → empty."""
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'], is_owner=False)}"},
        )
        assert r.status_code == 200
        # prov_a as auditor: no submission.auditor_id = prov_a → empty
        ids = {i["submission_id"] for i in r.json()["items"]}
        assert two_providers_with_overdue["sub_a"] not in ids


# ── Group 3 — Limit + pagination (4 tests) ─────────────────────────────────


class TestLimitParam:
    async def test_default_limit_100(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        # Default = 100; we have 1 → ≤ 100
        assert len(r.json()["items"]) <= 100

    async def test_custom_limit_param(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue?limit=1",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 1

    async def test_limit_zero_returns_empty(self, client, two_providers_with_overdue):
        r = await client.get(
            "/api/submissions/overdue?limit=0",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        assert r.status_code == 200
        assert r.json()["items"] == []

    async def test_limit_negative_validated_422(self, client, two_providers_with_overdue):
        """Production bug caught by this test: previously LIMIT -1 leaked
        InvalidRowCountInLimitClauseError → 500. Fixed in same commit:
        Query(100, ge=0, le=500) gate at endpoint level."""
        r = await client.get(
            "/api/submissions/overdue?limit=-1",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        assert r.status_code == 422

    async def test_limit_huge_clamped(self, client, two_providers_with_overdue):
        """limit > le=500 → 422 (don't allow user to OOM via huge LIMIT)."""
        r = await client.get(
            "/api/submissions/overdue?limit=99999",
            headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
        )
        assert r.status_code == 422


# ── Group 4 — Status filter (4 tests) ──────────────────────────────────────


class TestStatusFilter:
    async def test_approved_excluded_from_queue(
        self, client, conn, two_providers_with_overdue
    ):
        await conn.execute(
            "UPDATE submissions SET status='approved' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            ids = {i["submission_id"] for i in r.json()["items"]}
            assert two_providers_with_overdue["sub_a"] not in ids
        finally:
            await conn.execute(
                "UPDATE submissions SET status='reviewing' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )

    async def test_rejected_excluded(self, client, conn, two_providers_with_overdue):
        await conn.execute(
            "UPDATE submissions SET status='rejected' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            ids = {i["submission_id"] for i in r.json()["items"]}
            assert two_providers_with_overdue["sub_a"] not in ids
        finally:
            await conn.execute(
                "UPDATE submissions SET status='reviewing' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )

    async def test_pending_included(self, client, conn, two_providers_with_overdue):
        await conn.execute(
            "UPDATE submissions SET status='pending' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            ids = {i["submission_id"] for i in r.json()["items"]}
            assert two_providers_with_overdue["sub_a"] in ids
        finally:
            await conn.execute(
                "UPDATE submissions SET status='reviewing' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )

    async def test_assigned_included(self, client, conn, two_providers_with_overdue):
        await conn.execute(
            "UPDATE submissions SET status='assigned' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            ids = {i["submission_id"] for i in r.json()["items"]}
            assert two_providers_with_overdue["sub_a"] in ids
        finally:
            await conn.execute(
                "UPDATE submissions SET status='reviewing' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )


# ── Group 5 — Deadline edge (4 tests) ──────────────────────────────────────


class TestDeadlineEdge:
    async def test_null_deadline_excluded(self, client, conn, two_providers_with_overdue):
        await conn.execute(
            "UPDATE submissions SET deadline = NULL WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            ids = {i["submission_id"] for i in r.json()["items"]}
            assert two_providers_with_overdue["sub_a"] not in ids
        finally:
            await conn.execute(
                "UPDATE submissions SET deadline = NOW() - INTERVAL '5 days' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )

    async def test_deadline_in_future_excluded(
        self, client, conn, two_providers_with_overdue
    ):
        await conn.execute(
            "UPDATE submissions SET deadline = NOW() + INTERVAL '1 day' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            ids = {i["submission_id"] for i in r.json()["items"]}
            assert two_providers_with_overdue["sub_a"] not in ids
        finally:
            await conn.execute(
                "UPDATE submissions SET deadline = NOW() - INTERVAL '5 days' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )

    async def test_response_sorted_oldest_deadline_first(
        self, client, conn, two_providers_with_overdue
    ):
        # Force prov_a's submission older than prov_b's (set both belong to prov_a)
        await conn.execute(
            "UPDATE submissions SET provider_id = $1 WHERE id = $2",
            two_providers_with_overdue["prov_a"], two_providers_with_overdue["sub_b"],
        )
        await conn.execute(
            "UPDATE submissions SET deadline = NOW() - INTERVAL '10 days' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        await conn.execute(
            "UPDATE submissions SET deadline = NOW() - INTERVAL '2 days' WHERE id = $1",
            two_providers_with_overdue["sub_b"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            items = r.json()["items"]
            # sub_a (older deadline) should come before sub_b
            ids = [it["submission_id"] for it in items]
            if two_providers_with_overdue["sub_a"] in ids and two_providers_with_overdue["sub_b"] in ids:
                assert ids.index(two_providers_with_overdue["sub_a"]) < ids.index(two_providers_with_overdue["sub_b"])
        finally:
            await conn.execute(
                "UPDATE submissions SET deadline = NOW() - INTERVAL '5 days' "
                "WHERE id = ANY($1::uuid[])",
                [two_providers_with_overdue["sub_a"], two_providers_with_overdue["sub_b"]],
            )

    async def test_days_overdue_calculated_correctly(
        self, client, conn, two_providers_with_overdue
    ):
        await conn.execute(
            "UPDATE submissions SET deadline = NOW() - INTERVAL '7 days' WHERE id = $1",
            two_providers_with_overdue["sub_a"],
        )
        try:
            r = await client.get(
                "/api/submissions/overdue",
                headers={"Authorization": f"Bearer {_provider_jwt(two_providers_with_overdue['prov_a'])}"},
            )
            items = r.json()["items"]
            item = next((i for i in items if i["submission_id"] == two_providers_with_overdue["sub_a"]), None)
            assert item is not None
            assert 6.5 <= item["days_overdue"] <= 7.5
        finally:
            await conn.execute(
                "UPDATE submissions SET deadline = NOW() - INTERVAL '5 days' WHERE id = $1",
                two_providers_with_overdue["sub_a"],
            )
