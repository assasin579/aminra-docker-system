"""UAT test infrastructure.

Shared helpers + fixtures for the 4 critical-flow UAT suites:
- A: Halal Certification Lifecycle
- B: Onsite Audit + NCR
- C: Multi-tenant Isolation
- D: Cert Verification + Recall

Design principles:
- Module-scope fixtures (avoid /auth/business/register rate-limit)
- Idempotent + cleanup via finally
- Skip cleanly when backend / endpoint not reachable
- No hardcoded credentials or tenant IDs
- All DB mutation goes through documented helpers (auditable)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid

import httpx
import pytest

DB_CONTAINER = os.getenv("AMINRA_DB_CONTAINER", "aminra-docker-system-postgres-db-1")
BACKEND_CONTAINER = os.getenv("AMINRA_BACKEND_CONTAINER", "aminra-docker-system-aminra-backend-1")

# Phase 4c-7: Keycloak SSO is the sole auth path. UAT provisions test users
# via /admin/users (which mirrors a Keycloak account with emailVerified=True)
# so the password grant works without an email round-trip. Both the admin
# token and individual user tokens come straight from the realm.
KC_PUBLIC_URL = os.getenv("KEYCLOAK_PUBLIC_URL", "https://auth.silvergem.org")
KC_REALM = os.getenv("KEYCLOAK_REALM", "aminra")
KC_CLIENT_ID = os.getenv("KEYCLOAK_PUBLIC_CLIENT_ID", "aminra-frontend")


# ── Backend reachability ────────────────────────────────────────────────────


def backend_unreachable(client) -> bool:
    """Check if backend /health is reachable. Used to skip suite cleanly."""
    try:
        return client.get("/health", timeout=5).status_code != 200
    except Exception:
        return True


# ── psql helper ─────────────────────────────────────────────────────────────


def psql(sql: str, *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a parameterless psql command. Use only with constant SQL — never
    with user-controlled input (this helper does not parameterize)."""
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available in this runtime; DB invariant must run from host QA context")
    return subprocess.run(
        [
            "docker", "exec", DB_CONTAINER,
            "psql", "-U", "aminra_user", "-d", "aminra", "-tAc", sql,
        ],
        check=check, capture_output=True, timeout=15,
    )


def psql_value(sql: str) -> str:
    """Return the trimmed stdout of a psql query as a string."""
    out = psql(sql, check=False)
    return out.stdout.decode().strip()


# ── Feature flag toggle (used by Luồng D for document_versioning_v1) ────────


def set_feature_flag(name: str, enabled: bool) -> None:
    """Toggle feature flag in DB and restart backend to bust in-process cache.

    NOTE: this restarts the backend container. Suite-level setup only.
    """
    val = "true" if enabled else "false"
    psql(f"UPDATE feature_flags SET default_enabled={val} WHERE name='{name}'", check=False)
    subprocess.run(
        ["docker", "restart", BACKEND_CONTAINER],
        check=False, capture_output=True, timeout=30,
    )
    for _ in range(20):
        time.sleep(1)
        try:
            import httpx
            if httpx.get("http://localhost:8100/health", timeout=2).status_code == 200:
                return
        except Exception:
            continue


# ── Keycloak auth helpers (Phase 4c-7) ──────────────────────────────────────


def kc_password_grant(email: str, password: str) -> httpx.Response:
    """OAuth password grant directly against the Keycloak realm.

    Replaces the legacy `POST /auth/login` removed in Phase 4b. Returns the
    raw httpx.Response so callers can assert both happy (200 + access_token)
    and error paths (400/401) without changing structure.
    """
    return httpx.post(
        f"{KC_PUBLIC_URL}/realms/{KC_REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": KC_CLIENT_ID,
            "username": email,
            "password": password,
        },
        timeout=10,
    )


_ADMIN_TOKEN_CACHE: dict[str, object] = {"token": None, "expires_at": 0.0}


def _get_platform_admin_token() -> str | None:
    """Cached platform_admin token (or None when test admin creds aren't configured).

    Set `TEST_ADMIN_EMAIL` + `TEST_ADMIN_PASSWORD` to a Keycloak user with the
    `platform_admin` realm role to enable UAT user provisioning. Without them
    register_business skips cleanly — the rest of the suite still runs against
    pre-seeded users.
    """
    email = os.getenv("TEST_ADMIN_EMAIL")
    password = os.getenv("TEST_ADMIN_PASSWORD")
    if not email or not password:
        return None
    now = time.time()
    if _ADMIN_TOKEN_CACHE["token"] and now < float(_ADMIN_TOKEN_CACHE["expires_at"]) - 30:
        return _ADMIN_TOKEN_CACHE["token"]  # type: ignore[return-value]
    r = kc_password_grant(email, password)
    if r.status_code != 200:
        return None
    data = r.json()
    _ADMIN_TOKEN_CACHE["token"] = data["access_token"]
    _ADMIN_TOKEN_CACHE["expires_at"] = now + int(data.get("expires_in", 60))
    return data["access_token"]


# ── Business owner provisioning ─────────────────────────────────────────────


def register_business(client, *, suffix: str = "") -> dict:
    """Provision a fresh business owner via the admin path so the user lands
    with `emailVerified=True` and is immediately usable for password grant.

    Skips the test when the admin creds are missing or any step fails — UAT
    must not silently fall back to broken auth paths.
    """
    admin_token = _get_platform_admin_token()
    if not admin_token:
        pytest.skip(
            "UAT register_business needs TEST_ADMIN_EMAIL + TEST_ADMIN_PASSWORD "
            "for a Keycloak user with realm role `platform_admin`."
        )

    rid = uuid.uuid4().hex[:8]
    email = f"uat-{rid}{suffix}@aminra-qa.com"
    password = "UATPass2026!"
    r = client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": email,
            "password": password,
            "company_name": f"UAT-{rid}",
            "company_code": f"UAT-{rid}",
            "role": "business",
        },
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"Cannot provision business via /admin/users (HTTP {r.status_code}): {r.text[:200]}")
    body = r.json()

    grant = kc_password_grant(email, password)
    if grant.status_code != 200:
        pytest.skip(f"KC password grant failed for new business (HTTP {grant.status_code}): {grant.text[:200]}")
    token = grant.json()["access_token"]

    return {
        "email": email,
        "password": password,
        "token": token,
        "user_id": body["id"],
        "tenant_id": body["tenant_id"],
    }


def auth_headers(creds: dict) -> dict:
    return {"Authorization": f"Bearer {creds['token']}"}


# ── Document insertion (bypasses upload endpoint for speed) ─────────────────


def insert_doc(tenant_id: str, user_id: str, status: str = "uploaded", **extra) -> str:
    """Insert minimal document row directly. Returns doc UUID."""
    doc_id = str(uuid.uuid4())
    cols = ["id", "filename", "original_filename", "user_id", "tenant_id", "status"]
    vals = [
        f"'{doc_id}'", "'uat.pdf'", "'uat.pdf'",
        f"'{user_id}'", f"'{tenant_id}'", f"'{status}'",
    ]
    for k, v in extra.items():
        cols.append(k)
        vals.append("NULL" if v is None else f"'{v}'")
    psql(f"INSERT INTO documents ({', '.join(cols)}) VALUES ({', '.join(vals)})")
    return doc_id


def set_approval(doc_id: str, status: str) -> None:
    """Force approval_status via direct UPDATE (test-only setup)."""
    psql(f"UPDATE documents SET approval_status='{status}' WHERE id='{doc_id}'")


def delete_doc(doc_id: str) -> None:
    """Cleanup helper. Removes incoming/outgoing chain links to bypass delete-block trigger."""
    psql(
        f"UPDATE documents SET version_parent_id=NULL, superseded_by_id=NULL "
        f"WHERE version_parent_id='{doc_id}' OR superseded_by_id='{doc_id}'; "
        f"DELETE FROM documents WHERE id='{doc_id}'",
        check=False,
    )


# ── Audit log helper ────────────────────────────────────────────────────────


def audit_count(entity_id: str, action: str | None = None) -> int:
    where = f"entity_id='{entity_id}'"
    if action:
        where += f" AND action='{action}'"
    out = psql(f"SELECT COUNT(*) FROM audit_logs WHERE {where}", check=False)
    try:
        return int(out.stdout.decode().strip() or "0")
    except Exception:
        return 0


# ── Endpoint-not-implemented detection ──────────────────────────────────────


def skip_if_not_implemented(response, endpoint: str) -> None:
    """If response is 404 because endpoint doesn't exist (vs resource not found),
    skip cleanly. Heuristic: 404 + body contains 'Not Found' (FastAPI default)."""
    if response.status_code == 404 and "Not Found" in response.text and "{" not in response.text[:5]:
        pytest.skip(f"Endpoint {endpoint} not implemented yet")


# ── Reusable module-scope fixtures ──────────────────────────────────────────


@pytest.fixture(scope="module")
def biz_a(client):
    """Module-scope tenant A. Used as the 'subject' tenant in most UAT scenarios."""
    if backend_unreachable(client):
        pytest.skip("Backend not reachable")
    return register_business(client, suffix="-a")


@pytest.fixture(scope="module")
def biz_b(client):
    """Module-scope tenant B. Used to verify isolation."""
    if backend_unreachable(client):
        pytest.skip("Backend not reachable")
    return register_business(client, suffix="-b")


@pytest.fixture
def hdr_a(biz_a):
    return auth_headers(biz_a)


@pytest.fixture
def hdr_b(biz_b):
    return auth_headers(biz_b)
