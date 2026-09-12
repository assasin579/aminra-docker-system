"""P0 role-boundary smoke tests against the live local stack.

These tests complement anonymous-route checks by using real Keycloak demo
tokens and asserting lower-privilege roles cannot reach admin/provider-only
surfaces. They are intentionally read-only except for one provider-only action
against a nil UUID, which must be rejected before mutation.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pytest

# Defaults are container-local because this test is primarily executed with
# `docker compose exec aminra-backend ...`. Host/public overrides still work via
# env vars, but the default path must avoid Cloudflare/public auth routing and
# must hit the backend port as seen from inside its own container.
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
KC_TOKEN_URL = os.getenv(
    "KEYCLOAK_TOKEN_URL",
    "http://keycloak:8080",
).rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "aminra")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "aminra-frontend")
DEMO_PW = os.getenv("DEMO_PW", "DemoP@ss2026")
PROVIDER_DEMO_PW = os.getenv("PROVIDER_DEMO_PW", DEMO_PW)
ADMIN_DEMO_PW = os.getenv("ADMIN_DEMO_PW")


def _token(email: str, password: str = DEMO_PW) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": email,
        "password": password,
    }).encode()
    # The backend validates tokens against KEYCLOAK_URL, which is the browser/public
    # issuer (`https://auth.silvergem.org` in the demo stack). When this smoke
    # test runs inside Docker, it still posts to the container-local Keycloak URL;
    # forwarding headers make Keycloak mint a token with the same issuer the
    # backend expects, without routing secrets through Cloudflare/public auth.
    req = urllib.request.Request(
        f"{KC_TOKEN_URL}/realms/{REALM}/protocol/openid-connect/token",
        data=data,
        headers={
            "X-Forwarded-Proto": os.getenv("KEYCLOAK_PUBLIC_PROTO", "https"),
            "X-Forwarded-Host": os.getenv("KEYCLOAK_PUBLIC_HOST", "auth.silvergem.org"),
            "X-Forwarded-Port": os.getenv("KEYCLOAK_PUBLIC_PORT", "443"),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - controlled test URL
        body = json.loads(resp.read())
    return body["access_token"]


def _request(method: str, path: str, token: str, body: dict | None = None) -> int:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - local test URL
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


@pytest.fixture(scope="module")
def business_token() -> str:
    return _token("biz-demo-1@demo.aminra.vn")


@pytest.fixture(scope="module")
def provider_token() -> str:
    return _token("cb-demo@demo.aminra.vn", PROVIDER_DEMO_PW)


@pytest.fixture(scope="module")
def admin_token() -> str:
    if not ADMIN_DEMO_PW:
        pytest.skip("ADMIN_DEMO_PW must be explicitly provided for platform-admin smoke")
    return _token("demo-platform-admin@demo.aminra.vn", ADMIN_DEMO_PW)


@pytest.mark.parametrize("path", [
    "/auth/admin/analytics",
    "/auth/admin/overdue-submissions",
    "/auth/admin/audit-logs",
    "/auth/admin/pending-providers",
])
def test_business_cannot_access_admin_surfaces(business_token: str, path: str):
    assert _request("GET", path, business_token) == 403


@pytest.mark.parametrize("path", [
    "/auth/admin/analytics",
    "/auth/admin/overdue-submissions",
    "/auth/admin/audit-logs",
    "/auth/admin/pending-providers",
])
def test_provider_cannot_access_platform_admin_surfaces(provider_token: str, path: str):
    assert _request("GET", path, provider_token) == 403


def test_business_cannot_issue_certificate_provider_only_action(business_token: str):
    status = _request(
        "POST",
        "/api/submissions/issue-certificate/00000000-0000-0000-0000-000000000000",
        business_token,
        {"expiry_months": 12, "notes": "role-boundary smoke"},
    )
    assert status == 403


@pytest.mark.parametrize("path", [
    "/auth/admin/analytics",
    "/auth/admin/overdue-submissions",
    "/auth/admin/audit-logs",
])
def test_platform_admin_can_access_admin_read_surfaces(admin_token: str, path: str):
    assert _request("GET", path, admin_token) == 200
