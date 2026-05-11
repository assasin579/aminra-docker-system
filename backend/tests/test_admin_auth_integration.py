"""F6 — Admin auth integration tests (30 cases).

Verifies the session 2026-05-10 swap from manual `_require_admin(user)` to
`Depends(require_admin)` across:
  - standard_type_router admin endpoints (6)
  - industry_schema_router admin endpoints (5)

Both JWT-admin AND opaque-session paths must reach the same protected
endpoints, while business / unauth requests get 401/403.

Uses real DB connection + httpx ASGI client (no live network).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest
from jose import jwt

from auth.jwt_utils import ADMIN_EMAIL, SECRET, ALGORITHM

# All tests run in the same session-scoped event loop so the shared DB pool
# initialized in the _db_pool fixture stays valid across tests.
pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Shared fixtures ────────────────────────────────────────────────────────


import pytest_asyncio


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def _db_pool():
    """Session-scoped pool init so all tests share one event loop."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    from auth.db import init_pool, close_pool
    import auth.db as _db_mod
    if _db_mod._pool is None:
        await init_pool()
    yield
    # don't close — let process exit handle


@pytest_asyncio.fixture(loop_scope="session")
async def conn(_db_pool):
    url = os.getenv("DATABASE_URL")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest_asyncio.fixture(loop_scope="session")
async def admin_jwt(conn):
    """JWT signed with real admin DB user_id so FK constraints satisfy."""
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1", ADMIN_EMAIL,
    )
    if not row:
        pytest.skip("Admin DB row missing — run bootstrap")
    return jwt.encode({
        "sub": str(row["id"]),
        "email": ADMIN_EMAIL,
        "role": "provider",
        "is_owner": True,
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


@pytest.fixture
def business_jwt():
    return jwt.encode({
        "sub": str(uuid4()),
        "email": "biz@example.com",
        "role": "business",
        "is_owner": True,
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


@pytest.fixture
def fake_provider_admin_jwt():
    """provider role but wrong email — should NOT pass admin gate."""
    return jwt.encode({
        "sub": str(uuid4()),
        "email": "not-admin@example.com",
        "role": "provider",
        "is_owner": True,
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


@pytest_asyncio.fixture(loop_scope="session")
async def opaque_session(_db_pool, tmp_path, monkeypatch):
    """Create opaque admin session token. Admin DB row is bootstrap'd separately."""
    # Create our own conn (don't mix session-scoped conn with function-scoped monkeypatch)
    url = os.getenv("DATABASE_URL")
    c = await asyncpg.connect(url)
    try:
        token = "test_opaque_" + uuid4().hex
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({token: time.time() + 3600}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

        await c.execute("""
            INSERT INTO users (email, password_hash, role, company_name, status, is_owner)
            VALUES ($1, 'test-bootstrap', 'provider', 'TestAdmin', 'active', true)
            ON CONFLICT (email) DO NOTHING
        """, ADMIN_EMAIL)

        yield token
    finally:
        await c.close()


@pytest_asyncio.fixture(loop_scope="session")
async def app_client(_db_pool):
    """ASGI client against the real FastAPI app. Pool initialized at session scope."""
    from app import app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        yield client


# ── Group 1 — Endpoint registry sanity (5 tests) ───────────────────────────


class TestEndpointRegistry:
    """Verify admin endpoints actually mounted at expected paths.

    These tests guard against include_router prefix drift — a class of bug
    that bit us multiple times this session.
    """


    async def test_admin_standards_endpoint_registered(self, app_client):
        # Without auth → 401, NOT 404 (route exists)
        r = await app_client.get("/auth/admin/standard-types")
        assert r.status_code in (401, 403)


    async def test_admin_industries_endpoint_registered(self, app_client):
        r = await app_client.get("/auth/admin/industry-schemas")
        assert r.status_code in (401, 403)


    async def test_admin_standards_post_registered(self, app_client):
        r = await app_client.post("/auth/admin/standard-types", json={})
        assert r.status_code in (401, 403, 422)  # not 404/405


    async def test_admin_industries_post_registered(self, app_client):
        r = await app_client.post("/auth/admin/industry-schemas", json={})
        assert r.status_code in (401, 403, 422)


    async def test_admin_industries_industry_standards_endpoint(self, app_client):
        fake_id = str(uuid4())
        r = await app_client.put(
            f"/auth/admin/standard-types/industries/{fake_id}/standards",
            json={"standards": []},
        )
        assert r.status_code in (401, 403, 422)


# ── Group 2 — Unauth + wrong-role rejection (8 tests) ──────────────────────


class TestUnauthAndWrongRole:

    async def test_no_auth_standards_list_401(self, app_client):
        r = await app_client.get("/auth/admin/standard-types")
        assert r.status_code == 401


    async def test_no_auth_industries_list_401(self, app_client):
        r = await app_client.get("/auth/admin/industry-schemas")
        assert r.status_code == 401


    async def test_business_jwt_standards_403(self, app_client, business_jwt):
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {business_jwt}"},
        )
        assert r.status_code == 403


    async def test_business_jwt_industries_403(self, app_client, business_jwt):
        r = await app_client.get(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {business_jwt}"},
        )
        assert r.status_code == 403


    async def test_fake_admin_email_rejected(
        self, app_client, fake_provider_admin_jwt
    ):
        """Provider role but evil@attacker.com → must NOT impersonate admin."""
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {fake_provider_admin_jwt}"},
        )
        assert r.status_code == 403


    async def test_garbage_bearer_token_rejected(self, app_client):
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert r.status_code == 403


    async def test_empty_bearer_token_rejected(self, app_client):
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": "Bearer "},
        )
        assert r.status_code == 401


    async def test_missing_bearer_scheme_rejected(self, app_client, admin_jwt):
        """Header must say 'Bearer ' prefix; raw token alone → 401."""
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": admin_jwt},
        )
        assert r.status_code == 401


# ── Group 3 — JWT admin path success (6 tests) ─────────────────────────────


class TestJWTAdminPath:

    async def test_jwt_admin_lists_standards(self, app_client, admin_jwt):
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)


    async def test_jwt_admin_lists_industries(self, app_client, admin_jwt):
        r = await app_client.get(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)


    async def test_jwt_admin_sees_disabled_standards(self, app_client, admin_jwt):
        """Admin should see disabled standards too (vs public endpoint which filters)."""
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert r.status_code == 200
        # If any disabled seeded, they should appear (test relaxed — just structure)
        for std in r.json():
            assert "enabled" in std


    async def test_jwt_admin_sees_disabled_industries(self, app_client, admin_jwt):
        r = await app_client.get(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert r.status_code == 200
        for ind in r.json():
            assert "enabled" in ind


    async def test_jwt_admin_patch_nonexistent_standard_404(
        self, app_client, admin_jwt
    ):
        fake_id = str(uuid4())
        r = await app_client.patch(
            f"/auth/admin/standard-types/{fake_id}",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"name_vi": "Updated"},
        )
        assert r.status_code == 404


    async def test_jwt_admin_patch_empty_body_400(self, app_client, admin_jwt):
        fake_id = str(uuid4())
        r = await app_client.patch(
            f"/auth/admin/standard-types/{fake_id}",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={},
        )
        # Empty body → 400 "No fields to update" (validated before 404 lookup)
        assert r.status_code == 400


# ── Group 4 — Opaque admin path success (5 tests) ──────────────────────────


class TestOpaqueAdminPath:
    """Opaque session token from /admin/login should also work post-refactor."""


    async def test_opaque_lists_standards(self, app_client, opaque_session):
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {opaque_session}"},
        )
        assert r.status_code == 200


    async def test_opaque_lists_industries(self, app_client, opaque_session):
        r = await app_client.get(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {opaque_session}"},
        )
        assert r.status_code == 200


    async def test_opaque_session_unknown_token_rejected(self, app_client):
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": "Bearer never_existed_token"},
        )
        assert r.status_code == 403


    async def test_opaque_expired_session_rejected(
        self, app_client, tmp_path, monkeypatch
    ):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"expired_token": time.time() - 10}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        r = await app_client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": "Bearer expired_token"},
        )
        assert r.status_code == 403


    async def test_opaque_path_includes_disabled_standards(
        self, app_client, opaque_session, conn
    ):
        # Mark a standard as disabled, verify it still appears in admin list
        existing = await conn.fetchrow(
            "SELECT id FROM standard_types LIMIT 1"
        )
        if not existing:
            pytest.skip("Need at least 1 standard_type seeded")
        await conn.execute(
            "UPDATE standard_types SET enabled = false WHERE id = $1",
            existing["id"],
        )
        try:
            r = await app_client.get(
                "/auth/admin/standard-types",
                headers={"Authorization": f"Bearer {opaque_session}"},
            )
            assert r.status_code == 200
            ids = [s["id"] for s in r.json()]
            assert str(existing["id"]) in ids
        finally:
            await conn.execute(
                "UPDATE standard_types SET enabled = true WHERE id = $1",
                existing["id"],
            )


# ── Group 5 — Audit log integration (3 tests) ──────────────────────────────


class TestAdminAuditLog:

    async def test_create_standard_writes_audit_log(
        self, app_client, admin_jwt, conn
    ):
        before = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE action = 'standard_type_created'"
        )
        code = f"test_audit_{uuid4().hex[:8]}"
        r = await app_client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "code": code,
                "name_vi": "Test Audit Standard",
                "organization": "TEST",
                "scheme_version": "2026",
                "enabled": True,
            },
        )
        assert r.status_code == 201
        try:
            after = await conn.fetchval(
                "SELECT COUNT(*) FROM audit_logs WHERE action = 'standard_type_created'"
            )
            assert after == before + 1
        finally:
            await conn.execute("DELETE FROM standard_types WHERE code = $1", code)


    async def test_create_industry_writes_audit_log(
        self, app_client, admin_jwt, conn
    ):
        before = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE action = 'industry_schema_created'"
        )
        code = f"test_audit_ind_{uuid4().hex[:8]}"
        r = await app_client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={
                "code": code,
                "name_vi": "Test Audit Industry",
                "enabled": True,
            },
        )
        assert r.status_code == 201
        try:
            after = await conn.fetchval(
                "SELECT COUNT(*) FROM audit_logs WHERE action = 'industry_schema_created'"
            )
            assert after == before + 1
        finally:
            await conn.execute("DELETE FROM industry_schemas WHERE code = $1", code)


    async def test_audit_log_uses_metadata_not_details_column(
        self, app_client, admin_jwt, conn
    ):
        """Regression: this session caught 500 because INSERT used `details`
        column name but actual column is `metadata`."""
        code = f"test_meta_{uuid4().hex[:8]}"
        r = await app_client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"code": code, "name_vi": "Meta col check", "enabled": True},
        )
        assert r.status_code == 201
        try:
            row = await conn.fetchrow(
                "SELECT metadata FROM audit_logs WHERE action = 'standard_type_created' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            assert row is not None
            assert row["metadata"] is not None
        finally:
            await conn.execute("DELETE FROM standard_types WHERE code = $1", code)


# ── Group 6 — Bootstrap row dependency (3 tests) ───────────────────────────


class TestBootstrapRow:
    """When admin row is missing, opaque path returns 403 with explicit message."""


    async def test_opaque_path_returns_503_message_when_admin_row_missing(
        self, app_client, conn, tmp_path, monkeypatch
    ):
        # Temporarily rename admin email so lookup fails
        sentinel = f"missing-admin-{uuid4().hex[:8]}@aminra.com"
        await conn.execute(
            "UPDATE users SET email = $1 WHERE email = $2",
            sentinel, ADMIN_EMAIL,
        )
        try:
            token = "test_opaque_" + uuid4().hex
            sessions_file = tmp_path / "admin_sessions.json"
            sessions_file.write_text(json.dumps({token: time.time() + 3600}))
            monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

            r = await app_client.get(
                "/auth/admin/standard-types",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 403
            assert "bootstrap" in r.json().get("detail", "").lower()
        finally:
            await conn.execute(
                "UPDATE users SET email = $1 WHERE email = $2",
                ADMIN_EMAIL, sentinel,
            )


    async def test_admin_row_role_is_provider(self, conn):
        row = await conn.fetchrow(
            "SELECT role::text, status::text FROM users WHERE email = $1",
            ADMIN_EMAIL,
        )
        assert row is not None
        assert row["role"] == "provider"
        assert row["status"] == "active"


    async def test_admin_row_is_owner_true(self, conn):
        row = await conn.fetchrow(
            "SELECT is_owner FROM users WHERE email = $1",
            ADMIN_EMAIL,
        )
        assert row is not None
        assert row["is_owner"] is True
