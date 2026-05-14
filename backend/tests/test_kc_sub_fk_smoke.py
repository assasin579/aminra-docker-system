"""Smoke regression for the KC-sub vs AMINRA-id class bug.

The bug: pre-Phase-4c code passed `user["sub"]` (Keycloak UUID) into
columns FK-constrained on `users.id` (AMINRA PG UUID). Under SSO, the
two UUIDs are never equal — every such write 500s with a
ForeignKeyViolationError on first real-traffic use.

This file provisions a fresh business owner through the admin path,
then hits each endpoint that previously hit the bug (and a couple of
related ones), asserting nothing 500s and no FK violation surfaces in
the response body.

If a future change re-introduces `user["sub"]` into a FK-write site,
this test should be the canary. The pre-commit `kc-sub-guard` is the
upstream defense; this is the downstream one.

Skips cleanly when TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD aren't set —
matches the convention for live-stack integration tests.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.uat


KC_PUBLIC = os.getenv("KEYCLOAK_PUBLIC_URL", "https://auth.silvergem.org")
KC_REALM = os.getenv("KEYCLOAK_REALM", "aminra")
KC_CLIENT = os.getenv("KEYCLOAK_PUBLIC_CLIENT_ID", "aminra-frontend")


def _kc_password_grant(email: str, password: str) -> httpx.Response:
    return httpx.post(
        f"{KC_PUBLIC}/realms/{KC_REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": KC_CLIENT,
            "username": email,
            "password": password,
        },
        timeout=10,
    )


def _admin_token() -> str | None:
    email = os.getenv("TEST_ADMIN_EMAIL")
    password = os.getenv("TEST_ADMIN_PASSWORD")
    if not (email and password):
        return None
    r = _kc_password_grant(email, password)
    if r.status_code != 200:
        return None
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def fresh_biz(client):
    """A freshly-provisioned business owner with a working KC token."""
    admin_tok = _admin_token()
    if not admin_tok:
        pytest.skip(
            "TEST_ADMIN_EMAIL + TEST_ADMIN_PASSWORD required (Keycloak user "
            "with realm role `platform_admin`)."
        )

    rid = uuid.uuid4().hex[:8]
    email = f"kc-sub-smoke-{rid}@aminra-qa.com"
    password = "KcSubSmoke2026!"

    create = client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "email": email,
            "password": password,
            "company_name": f"KCSubSmoke-{rid}",
            "role": "business",
        },
        timeout=10,
    )
    if create.status_code != 200:
        pytest.skip(f"/admin/users provision failed: HTTP {create.status_code}")

    grant = _kc_password_grant(email, password)
    if grant.status_code != 200:
        pytest.skip(f"KC grant failed for new user: HTTP {grant.status_code}")

    body = create.json()
    return {
        "email": email,
        "token": grant.json()["access_token"],
        "user_id": body["id"],
        "tenant_id": body["tenant_id"],
        "headers": {"Authorization": f"Bearer {grant.json()['access_token']}"},
    }


def _no_fk_violation(resp: httpx.Response, label: str) -> None:
    """Assert the response is not a 500 caused by FK violation. Other 4xx
    are acceptable — the test only catches the class bug, not endpoint
    business logic."""
    assert resp.status_code != 500, (
        f"{label}: HTTP 500 — possible KC-sub FK class bug regression.\n"
        f"Body: {resp.text[:500]}"
    )
    # Defensive: even non-500 responses sometimes leak the SQL error string.
    assert "ForeignKeyViolationError" not in resp.text, (
        f"{label}: response body contains FK violation marker.\n"
        f"Body: {resp.text[:500]}"
    )
    assert "audit_logs_user_id_fkey" not in resp.text, (
        f"{label}: response body references the canonical FK constraint."
    )


# ════════════════════════════════════════════════════════════════════════════
# Each test below exercises an endpoint that previously hit (or could hit)
# the class bug. They don't assert business-logic correctness — just that
# the FK-write path doesn't 500.
# ════════════════════════════════════════════════════════════════════════════


def test_industry_business_select_no_fk_violation(client, fresh_biz):
    """POST /industry-schemas/business-select previously 500'd here."""
    # Fetch a real schema id (response is a list of schema dicts)
    schemas = client.get("/industry-schemas", headers=fresh_biz["headers"])
    if schemas.status_code != 200 or not schemas.json():
        pytest.skip("no industry schemas available")
    schema_id = schemas.json()[0]["id"]

    r = client.post(
        "/industry-schemas/business-select",
        headers=fresh_biz["headers"],
        json={"schema_id": schema_id},
    )
    _no_fk_violation(r, "industry_schemas/business-select")
    # First call should land 200; subsequent calls 409. Either is fine.
    assert r.status_code in (200, 409), r.text


def test_notifications_list_no_fk_violation(client, fresh_biz):
    """GET /api/notifications/ — WHERE user_id = $sub previously mis-targeted."""
    r = client.get("/api/notifications/", headers=fresh_biz["headers"])
    _no_fk_violation(r, "GET /api/notifications/")
    assert r.status_code == 200, r.text


def test_notifications_unread_count_no_fk_violation(client, fresh_biz):
    r = client.get("/api/notifications/unread-count", headers=fresh_biz["headers"])
    _no_fk_violation(r, "GET /api/notifications/unread-count")
    assert r.status_code == 200, r.text


def test_notifications_read_all_no_fk_violation(client, fresh_biz):
    r = client.put("/api/notifications/read-all", headers=fresh_biz["headers"])
    _no_fk_violation(r, "PUT /api/notifications/read-all")
    assert r.status_code == 200, r.text


def test_auth_company_profile_no_fk_violation(client, fresh_biz):
    """PUT /auth/company-profile uses resolve_canonical_user_id directly."""
    r = client.put(
        "/auth/company-profile",
        headers=fresh_biz["headers"],
        json={"company_name": "KCSubSmoke (renamed)"},
    )
    _no_fk_violation(r, "PUT /auth/company-profile")
    assert r.status_code == 200, r.text


def test_auth_company_profile_get_roundtrip(client, fresh_biz):
    """GET /auth/company-profile previously 500'd because it fed the JWT
    `tenant_id` slug (e.g. "demo-biz") into `WHERE users.id = $1`. Without
    a working GET the FE settings page reloads with an empty form even
    when PUT actually persisted, surfacing as "thông tin không được lưu".
    """
    sentinel = f"Smoke Co — verified {uuid.uuid4().hex[:8]}"

    # 1. PUT a unique value
    put_r = client.put(
        "/auth/company-profile",
        headers=fresh_biz["headers"],
        json={"company_name": sentinel, "address": "GET-roundtrip St"},
    )
    _no_fk_violation(put_r, "PUT /auth/company-profile")
    assert put_r.status_code == 200, put_r.text

    # 2. GET — must succeed AND return the value we just wrote
    get_r = client.get("/auth/company-profile", headers=fresh_biz["headers"])
    _no_fk_violation(get_r, "GET /auth/company-profile")
    assert get_r.status_code == 200, get_r.text
    body = get_r.json()
    assert body["company_name"] == sentinel, (
        f"GET drift: PUT wrote {sentinel!r}, GET returned {body['company_name']!r}"
    )
    assert body["address"] == "GET-roundtrip St", body


def test_auth_me_returns_aminra_id(client, fresh_biz):
    """Sanity: /auth/me's `id` is the AMINRA users.id, not the KC sub."""
    r = client.get("/auth/me", headers=fresh_biz["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == fresh_biz["user_id"], (
        f"id drift: /auth/me returned {body['id']!r}, "
        f"/admin/users provisioned {fresh_biz['user_id']!r}"
    )
