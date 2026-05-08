import os
from uuid import uuid4

import asyncpg
import pytest
import httpx


# ─── Shared DB + auth fixtures (supply chain test suites) ────────────────────


class _FakeClient:
    host = "10.0.0.1"


class FakeRequest:
    """Stand-in for FastAPI Request — only client.host + headers are used by
    audit logging. Avoids spinning up the full ASGI stack for unit tests."""
    client = _FakeClient()
    headers = {"user-agent": "pytest"}


@pytest.fixture
async def db_tx():
    """Per-test asyncpg connection wrapped in an outer transaction that rolls
    back on teardown. Keeps the dev DB pristine across test runs."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    c = await asyncpg.connect(url)
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        try:
            await tr.rollback()
        finally:
            await c.close()


def _user_payload(row, role="business"):
    return {
        "sub": str(row["id"]),
        "email": row["email"],
        "role": role,
        "is_owner": True,
        "tenant_id": str(row["tenant_id"]) if "tenant_id" in row.keys() else str(row["id"]),
    }


@pytest.fixture
async def biz_a(db_tx):
    """First business tenant — primary actor in most tests."""
    row = await db_tx.fetchrow(
        "SELECT id, email, tenant_id FROM users "
        "WHERE role='business' AND is_owner=true ORDER BY created_at LIMIT 1"
    )
    if not row:
        pytest.skip("Need a business owner user in DB")
    return _user_payload(row, "business")


@pytest.fixture
async def biz_b(db_tx, biz_a):
    """Second business tenant — different tenant_id from biz_a, used for
    cross-tenant isolation tests."""
    row = await db_tx.fetchrow(
        "SELECT id, email, tenant_id FROM users "
        "WHERE role='business' AND is_owner=true AND tenant_id <> $1 "
        "ORDER BY created_at LIMIT 1",
        biz_a["tenant_id"],
    )
    if not row:
        pytest.skip("Need 2 business tenants for cross-tenant tests")
    return _user_payload(row, "business")


@pytest.fixture
async def prov_user(db_tx):
    row = await db_tx.fetchrow(
        "SELECT id, email FROM users "
        "WHERE role='provider' AND is_owner=true ORDER BY created_at LIMIT 1"
    )
    if not row:
        pytest.skip("Need a provider user in DB")
    return {
        "sub": str(row["id"]),
        "email": row["email"],
        "role": "provider",
        "is_owner": True,
        "tenant_id": str(row["id"]),
    }


@pytest.fixture
def fake_request():
    return FakeRequest()


# ─── Original session-scoped HTTP client + admin login ───────────────────────


@pytest.fixture(scope="session")
def client():
    """HTTP client that talks to the running backend.

    Default targets the backend on the localhost-mapped host port (8100), but
    when pytest runs *inside* the backend container, the service is at port
    8000 instead. We auto-detect by trying 8000 first.
    """
    explicit = os.getenv("TEST_BACKEND_URL")
    if explicit:
        base_url = explicit
    elif os.path.exists("/.dockerenv"):
        base_url = "http://localhost:8000"
    else:
        base_url = "http://localhost:8100"
    with httpx.Client(base_url=base_url, timeout=60) as c:
        yield c


@pytest.fixture(scope="session")
def admin_credentials() -> tuple[str, str] | None:
    """Test login credentials. Set TEST_ADMIN_EMAIL + TEST_ADMIN_PASSWORD in env
    to enable live-login tests; otherwise dependent tests skip cleanly.
    """
    email = os.getenv("TEST_ADMIN_EMAIL")
    password = os.getenv("TEST_ADMIN_PASSWORD")
    if not email or not password:
        return None
    return email, password


@pytest.fixture(scope="session")
def admin_token(client, admin_credentials):
    """Live JWT for admin_credentials, or None if credentials aren't configured."""
    if admin_credentials is None:
        return None
    email, password = admin_credentials
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None
