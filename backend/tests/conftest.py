import os

# Test-only JWT secret. Set BEFORE importing any module that reads it at
# module-load time (e.g. auth.jwt_utils raises if missing). Real value is
# injected by docker-compose env / Vault in dev + prod. Tests must NEVER
# rely on this value to validate real tokens.
os.environ.setdefault(
    "JWT_SECRET",
    "pytest-only-secret-do-not-use-in-prod-aaaaaaaaaaaaaaaaaaaaaaaa",
)


# ─── DATABASE_URL auto-detect for in-container test runs ────────────────────
#
# The 246 supply-chain + sealing + anchor tests skip when DATABASE_URL is
# unset (~50% of all skips). When pytest runs inside the AMINRA backend
# container with the postgres-db service reachable on the docker network,
# auto-fill DATABASE_URL with dev creds so those tests run.
#
# Safety:
#   - Only fires inside a container (`/.dockerenv` exists).
#   - Only fires if the user hasn't already set DATABASE_URL.
#   - Only uses default DEV creds — production sets DATABASE_URL via
#     Vault so this branch never runs there.
#   - Probes the service with a short timeout; on any failure, leaves
#     DATABASE_URL unset so dependent tests skip cleanly.

def _maybe_autodetect_database_url() -> None:
    if os.getenv("DATABASE_URL"):
        return
    from pathlib import Path as _P
    if not _P("/.dockerenv").exists():
        return
    # Compose service name + dev creds. Real prod sets DATABASE_URL elsewhere.
    candidate = (
        "postgresql://aminra_user:aminra_secure_2026"
        "@aminra-docker-system-postgres-db-1:5432/aminra"
    )
    try:
        import asyncio as _asyncio
        import asyncpg as _asyncpg
        async def _probe() -> bool:
            try:
                conn = await _asyncpg.connect(candidate, timeout=2)
                await conn.close()
                return True
            except Exception:
                return False
        if _asyncio.run(_probe()):
            os.environ["DATABASE_URL"] = candidate
    except Exception:
        # asyncpg/asyncio import failed or runtime hiccup — leave URL unset.
        pass


_maybe_autodetect_database_url()

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


# ─── Host-only test auto-skip ────────────────────────────────────────────────
#
# Some tests need resources only available on the host CI runner, not inside
# the backend Docker container:
#   - subprocess `docker` CLI (migration / audit log immutability checks)
#   - filesystem layout at REPO_ROOT (Procfile, Dockerfile, env.example)
#   - running frontend service for HTTP-render assertions
#
# Auto-skip these when running inside the container so in-container CI signal
# stays clean. Host CI must run pytest with HOST_CI=1 to opt back in.

from pathlib import Path as _Path

_IN_CONTAINER = _Path("/.dockerenv").exists() and os.getenv("HOST_CI") != "1"

# Match against pytest nodeid (e.g. "tests/test_x.py::TestY::test_z").
_HOST_ONLY_PATTERNS: tuple[str, ...] = (
    # Whole files reading REPO_ROOT files or subprocessing docker
    "tests/test_config_tunables.py",
    "tests/test_document_versioning_func.py",
    "tests/test_document_versioning_sec.py",
    "tests/test_document_versioning_integration.py",
    # Specific classes inside multi-class regression file
    "tests/test_document_versioning_regression.py::TestServiceHealth",
    "tests/test_document_versioning_regression.py::TestNegativeRegression",
    "tests/test_document_versioning_regression.py::TestFlagOnAdditions",
    "tests/test_document_versioning_regression.py::TestFlagOffBaseline",
    "tests/test_document_versioning_regression.py::TestWorkflows",
    "tests/test_document_versioning_regression.py::TestFrontendRenders",
)


def pytest_collection_modifyitems(config, items):
    """Skip host-only tests when running inside the container."""
    if not _IN_CONTAINER:
        return
    skip = pytest.mark.skip(
        reason="host-only test (docker CLI / repo-root files / running FE) — set HOST_CI=1 to opt in"
    )
    for item in items:
        if any(p in item.nodeid for p in _HOST_ONLY_PATTERNS):
            item.add_marker(skip)
