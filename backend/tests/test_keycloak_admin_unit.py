"""Unit tests for keycloak_admin (ADR-005 Phase 4).

No live Keycloak. Mocks httpx at the module level.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from auth import keycloak_admin as ka


@pytest.fixture(autouse=True)
def _reset_token_cache(monkeypatch):
    ka._token_cache["token"] = None
    ka._token_cache["expires_at"] = 0.0
    monkeypatch.setattr(ka, "ADMIN_CLI_SECRET", "test-secret")
    yield


def _resp(status_code: int, json_body: dict | None = None, headers: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body or {}
    r.headers = headers or {}
    r.text = text
    return r


# ── _get_admin_token ─────────────────────────────────────────────────────────


def test_get_admin_token_caches_within_ttl(monkeypatch):
    call_count = {"n": 0}

    def fake_post(url, **kwargs):
        call_count["n"] += 1
        return _resp(200, {"access_token": "tok-1", "expires_in": 60})

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    t1 = ka._get_admin_token()
    t2 = ka._get_admin_token()
    t3 = ka._get_admin_token()
    assert t1 == t2 == t3 == "tok-1"
    assert call_count["n"] == 1


def test_get_admin_token_refreshes_after_expiry(monkeypatch):
    call_count = {"n": 0}

    def fake_post(url, **kwargs):
        call_count["n"] += 1
        return _resp(200, {"access_token": f"tok-{call_count['n']}", "expires_in": 60})

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    ka._get_admin_token()
    # Force expiry
    ka._token_cache["expires_at"] = time.time() - 1
    ka._get_admin_token()
    assert call_count["n"] == 2


def test_get_admin_token_raises_without_secret(monkeypatch):
    monkeypatch.setattr(ka, "ADMIN_CLI_SECRET", "")
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka._get_admin_token()
    assert exc.value.status_code == 500


def test_get_admin_token_raises_on_keycloak_error(monkeypatch):
    monkeypatch.setattr(
        ka.httpx, "post", lambda *a, **kw: _resp(401, text="invalid client"),
    )
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka._get_admin_token()
    assert exc.value.status_code == 502


# ── _user_payload ────────────────────────────────────────────────────────────


def test_user_payload_attributes_are_list_of_strings():
    p = ka._user_payload(
        email="u@example.com",
        tenant_id="tnt-1",
        is_owner=True,
        user_status="active",
    )
    # Keycloak admin REST requires every attribute value to be list[str].
    assert p["attributes"]["tenant_id"] == ["tnt-1"]
    assert p["attributes"]["is_owner"] == ["true"]
    assert p["attributes"]["status"] == ["active"]
    assert p["username"] == "u@example.com"
    assert p["email"] == "u@example.com"
    assert p["enabled"] is True
    assert p["emailVerified"] is False
    assert "VERIFY_EMAIL" in p["requiredActions"]


def test_user_payload_omits_tenant_id_when_none():
    p = ka._user_payload(email="u@x", tenant_id=None, is_owner=False, user_status="pending")
    assert "tenant_id" not in p["attributes"]
    assert p["attributes"]["is_owner"] == ["false"]


def test_user_payload_includes_company_name_as_first_name():
    p = ka._user_payload(
        email="u@x", tenant_id="t", is_owner=True, user_status="active",
        company_name="ACME Co",
    )
    assert p["firstName"] == "ACME Co"


# ── create_user ──────────────────────────────────────────────────────────────


@pytest.fixture
def _seeded_token(monkeypatch):
    """Pre-populate token cache so create_user calls don't first hit /token."""
    ka._token_cache["token"] = "tok-abc"
    ka._token_cache["expires_at"] = time.time() + 300
    yield


def test_create_user_happy_path(monkeypatch, _seeded_token):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        if url.endswith("/users"):
            return _resp(201, headers={"Location": "https://kc/users/new-uuid-1"})
        if url.endswith("/role-mappings/realm"):
            return _resp(204)
        raise AssertionError(f"unexpected POST {url}")

    def fake_put(url, **kwargs):
        calls.append(("PUT", url, kwargs))
        if "/reset-password" in url:
            return _resp(204)
        raise AssertionError(f"unexpected PUT {url}")

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        if "/roles/business" in url:
            return _resp(200, {"id": "role-id-1", "name": "business"})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", fake_put)
    monkeypatch.setattr(ka.httpx, "get", fake_get)

    uid = ka.create_user(
        email="dn1@example.com",
        password="LongComplexPa$$w0rd!",
        role="business",
        tenant_id="tnt-1",
        is_owner=True,
        user_status="active",
        company_name="DN1",
    )
    assert uid == "new-uuid-1"
    methods = [c[0] for c in calls]
    assert methods == ["POST", "PUT", "GET", "POST"]
    create_kwargs = calls[0][2]
    assert create_kwargs["json"]["attributes"]["tenant_id"] == ["tnt-1"]


def test_create_user_409_email_conflict(monkeypatch, _seeded_token):
    monkeypatch.setattr(ka.httpx, "post", lambda *a, **kw: _resp(409, text="user exists"))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(
            email="dup@x", password="x", role="business",
            tenant_id="t", is_owner=True, user_status="active",
        )
    assert exc.value.status_code == 400


def test_create_user_missing_location_header(monkeypatch, _seeded_token):
    monkeypatch.setattr(ka.httpx, "post", lambda *a, **kw: _resp(201, headers={}))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(
            email="u@x", password="x", role="business",
            tenant_id="t", is_owner=True, user_status="active",
        )
    assert exc.value.status_code == 502


def test_create_user_with_mfa_required(monkeypatch, _seeded_token):
    captured: dict = {}

    def fake_post(url, **kwargs):
        if url.endswith("/users"):
            captured["body"] = kwargs["json"]
            return _resp(201, headers={"Location": "https://kc/users/u1"})
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get", lambda *a, **kw: _resp(200, {"id": "r", "name": "auditor"}))

    ka.create_user(
        email="auditor1@x", password="x", role="auditor",
        tenant_id="t", is_owner=False, user_status="active",
        require_mfa=True,
    )
    assert "CONFIGURE_TOTP" in captured["body"]["requiredActions"]
    assert "VERIFY_EMAIL" in captured["body"]["requiredActions"]


def test_create_user_role_lookup_failure(monkeypatch, _seeded_token):
    monkeypatch.setattr(ka.httpx, "post", lambda *a, **kw: _resp(201, headers={"Location": "https://kc/users/u1"}))
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get", lambda *a, **kw: _resp(404, text="role not found"))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(
            email="u@x", password="x", role="bogus",
            tenant_id="t", is_owner=True, user_status="active",
        )
    assert exc.value.status_code == 502


# ── set_required_actions ─────────────────────────────────────────────────────


def test_set_required_actions(monkeypatch, _seeded_token):
    captured: dict = {}

    def fake_put(url, **kwargs):
        captured["url"] = url
        captured["body"] = kwargs["json"]
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "put", fake_put)
    ka.set_required_actions("user-uuid-1", ["VERIFY_EMAIL", "UPDATE_PASSWORD"])
    assert captured["url"].endswith("/users/user-uuid-1")
    assert captured["body"]["requiredActions"] == ["VERIFY_EMAIL", "UPDATE_PASSWORD"]


def test_set_required_actions_failure(monkeypatch, _seeded_token):
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(403))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.set_required_actions("u1", [])
    assert exc.value.status_code == 502
