"""Keycloak admin REST edge cases (Tier 2 E2E batch 3).

Operator perspective: registration flow has 4 sequential admin REST
calls. Each can fail independently. Each test names the operational
incident — partial-failure compensation is the audit-trail story.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from auth import keycloak_admin as ka


def _resp(status_code: int, json_body: dict | None = None,
          headers: dict | None = None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body or {}
    r.headers = headers or {}
    r.text = text
    return r


@pytest.fixture(autouse=True)
def _reset_token_cache(monkeypatch):
    ka._token_cache["token"] = None
    ka._token_cache["expires_at"] = 0.0
    monkeypatch.setattr(ka, "ADMIN_CLI_SECRET", "test-secret")
    yield


@pytest.fixture
def _seeded_token():
    ka._token_cache["token"] = "tok-abc"
    ka._token_cache["expires_at"] = time.time() + 300


# ═════════════════════════════════════════════════════════════════════════════
# 1. TOKEN ACQUISITION FAILURE MODES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("status_code,detail_substr", [
    (400, "fetch failed"),
    (401, "fetch failed"),     # invalid_client
    (403, "fetch failed"),
    (404, "fetch failed"),     # wrong realm path
    (500, "fetch failed"),
    (502, "fetch failed"),
    (503, "fetch failed"),
])
def test_token_acquisition_http_errors(monkeypatch, status_code, detail_substr):
    monkeypatch.setattr(
        ka.httpx, "post",
        lambda *a, **kw: _resp(status_code, text="error body"),
    )
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka._get_admin_token()
    assert exc.value.status_code == 502
    assert detail_substr in exc.value.detail.lower()


def test_token_acquisition_returns_token_in_response(monkeypatch):
    monkeypatch.setattr(
        ka.httpx, "post",
        lambda *a, **kw: _resp(200, {"access_token": "abc", "expires_in": 60}),
    )
    assert ka._get_admin_token() == "abc"


def test_token_acquisition_uses_skew_threshold(monkeypatch):
    """Cache invalidates 30s before actual expiry to avoid race."""
    calls = {"n": 0}

    def fake_post(*a, **kw):
        calls["n"] += 1
        return _resp(200, {"access_token": f"tok-{calls['n']}", "expires_in": 60})

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    ka._get_admin_token()
    # Set cache to expire in 20s (within 30s skew) — should refetch
    ka._token_cache["expires_at"] = time.time() + 20
    ka._get_admin_token()
    assert calls["n"] == 2


def test_concurrent_token_fetches_serialise(monkeypatch):
    """Lock prevents thundering herd against /token endpoint."""
    import threading
    calls = {"n": 0}

    def fake_post(*a, **kw):
        calls["n"] += 1
        time.sleep(0.05)
        return _resp(200, {"access_token": "tok", "expires_in": 60})

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    threads = [threading.Thread(target=ka._get_admin_token) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert calls["n"] == 1


def test_missing_secret_blocks_immediately(monkeypatch):
    monkeypatch.setattr(ka, "ADMIN_CLI_SECRET", "")
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka._get_admin_token()
    assert exc.value.status_code == 500


def test_missing_secret_does_not_call_keycloak(monkeypatch):
    """No secret → no network call. Defense against running in unconfigured env."""
    monkeypatch.setattr(ka, "ADMIN_CLI_SECRET", "")
    called = {"n": 0}

    def fake_post(*a, **kw):
        called["n"] += 1
        return _resp(200, {"access_token": "tok", "expires_in": 60})

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    with pytest.raises(ka.KeycloakAdminError):
        ka._get_admin_token()
    assert called["n"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# 2. USER PAYLOAD CONSTRUCTION EDGES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("email", [
    "user@example.com",
    "user+tag@example.com",
    "ngọc@công-ty.vn",                  # Unicode
    "u" * 250 + "@x.com",               # boundary length
    "very.long.email.with.many.dots@subdomain.subdomain.example.com",
])
def test_user_payload_email_variants(email):
    p = ka._user_payload(email=email, tenant_id="t", is_owner=True, user_status="active")
    assert p["username"] == email
    assert p["email"] == email


@pytest.mark.parametrize("status_value", [
    "active", "pending", "suspended",
    "ACTIVE",                          # case variants — passed through
    "unknown-status",                  # typo — passed through (no client validation)
    "",                                 # empty — passed through
])
def test_user_payload_status_variants(status_value):
    p = ka._user_payload(email="u@x", tenant_id="t", is_owner=True,
                         user_status=status_value)
    assert p["attributes"]["status"] == [status_value]


@pytest.mark.parametrize("tenant_id,expected", [
    ("uuid-string", ["uuid-string"]),
    (None, None),                                  # OMITTED from attributes
    ("", [""]),                                    # empty string preserved
    (12345, ["12345"]),                            # int coerced
    ("special chars: <>&'\"", ["special chars: <>&'\""]),
    ("a" * 1000, ["a" * 1000]),                    # long
])
def test_user_payload_tenant_id_variants(tenant_id, expected):
    p = ka._user_payload(email="u@x", tenant_id=tenant_id, is_owner=True,
                         user_status="active")
    if expected is None:
        assert "tenant_id" not in p["attributes"]
    else:
        assert p["attributes"]["tenant_id"] == expected


@pytest.mark.parametrize("is_owner,expected", [
    (True, ["true"]),
    (False, ["false"]),
    (1, ["true"]),                # truthy
    (0, ["false"]),
    ("yes", ["true"]),            # any truthy string
    ("", ["false"]),              # falsy string
])
def test_user_payload_is_owner_coerces_to_string_list(is_owner, expected):
    p = ka._user_payload(email="u@x", tenant_id="t", is_owner=is_owner,
                         user_status="active")
    assert p["attributes"]["is_owner"] == expected


def test_user_payload_required_actions_default_verify_email():
    p = ka._user_payload(email="u@x", tenant_id="t", is_owner=True, user_status="active")
    assert p["requiredActions"] == ["VERIFY_EMAIL"]


def test_user_payload_email_verified_starts_false():
    """Migration scope: never auto-verify. Owner must click email link."""
    p = ka._user_payload(email="u@x", tenant_id="t", is_owner=True, user_status="active")
    assert p["emailVerified"] is False
    assert p["enabled"] is True


# ═════════════════════════════════════════════════════════════════════════════
# 3. CREATE USER FAILURE MODES — partial state risk surface
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("create_status", [400, 401, 403, 422, 500])
def test_create_user_create_step_fails(_seeded_token, monkeypatch, create_status):
    monkeypatch.setattr(ka.httpx, "post",
                        lambda *a, **kw: _resp(create_status, text="oops"))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(email="u@x", password="x", role="business",
                       tenant_id="t", is_owner=True, user_status="active")
    # 409 maps to 400, others to 502
    if create_status == 409:
        assert exc.value.status_code == 400
    else:
        assert exc.value.status_code == 502


def test_create_user_409_maps_to_400_not_502(_seeded_token, monkeypatch):
    """409 = email exists. Surface as 400 to caller (user-facing error),
    NOT 502 (which implies upstream server problem)."""
    monkeypatch.setattr(ka.httpx, "post",
                        lambda *a, **kw: _resp(409, text="conflict"))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(email="dup@x", password="x", role="business",
                       tenant_id="t", is_owner=True, user_status="active")
    assert exc.value.status_code == 400


@pytest.mark.parametrize("location_header", [
    "",
    "/users/",                                # trailing slash, empty id
    "https://keycloak.local/admin/realms/aminra/users/",
    "no-slash-at-all",                        # caller has to handle
    "/path/with/many/segments/uuid-123",
])
def test_create_user_location_header_parsing(_seeded_token, monkeypatch, location_header):
    """Location header: rsplit('/', 1)[-1] — hardly ever fails, but
    'no-slash-at-all' returns the whole string, which is a string id.
    Empty / trailing-slash returns empty string — must reject."""

    def fake_post(url, **kw):
        if url.endswith("/users"):
            return _resp(201, headers={"Location": location_header})
        # role-mappings/realm post — returns 204 No Content
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(200, {"id": "r", "name": "business"}))
    if location_header.endswith("/") or location_header == "":
        with pytest.raises(ka.KeycloakAdminError) as exc:
            ka.create_user(email="u@x", password="x", role="business",
                           tenant_id="t", is_owner=True, user_status="active")
        # Empty str from rsplit('/',1)[-1] is falsy → branched to 502 path
        assert exc.value.status_code == 502
    else:
        uid = ka.create_user(email="u@x", password="x", role="business",
                              tenant_id="t", is_owner=True, user_status="active")
        assert uid == location_header.rsplit("/", 1)[-1]


def test_create_user_password_step_fails_after_create_succeeds(_seeded_token, monkeypatch):
    """User created, password reset 502 → ghost user in Keycloak.
    create_user MUST raise so caller knows to compensate (delete user
    via keycloak_admin._delete_user — Phase 4 followup TODO)."""
    monkeypatch.setattr(ka.httpx, "post",
                        lambda *a, **kw: _resp(201, headers={"Location": "/users/uid-1"}))
    monkeypatch.setattr(ka.httpx, "put",
                        lambda *a, **kw: _resp(500, text="db down"))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(200, {"id": "r", "name": "business"}))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(email="u@x", password="x", role="business",
                       tenant_id="t", is_owner=True, user_status="active")
    assert exc.value.status_code == 502
    assert "reset_password" in exc.value.detail


def test_create_user_role_lookup_404(_seeded_token, monkeypatch):
    """Caller passed a role that doesn't exist in the realm → 404."""
    monkeypatch.setattr(ka.httpx, "post",
                        lambda *a, **kw: _resp(201, headers={"Location": "/users/uid-1"}))
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(404, text="not found"))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(email="u@x", password="x", role="nonexistent",
                       tenant_id="t", is_owner=True, user_status="active")
    assert exc.value.status_code == 502


def test_create_user_role_grant_step_fails(_seeded_token, monkeypatch):
    """User + password OK, role grant 403 (admin-cli missing permission).
    Ghost user with no role — admin should investigate role mappings."""
    posts = {"n": 0}

    def fake_post(*a, **kw):
        posts["n"] += 1
        if posts["n"] == 1:                                       # /users
            return _resp(201, headers={"Location": "/users/uid-1"})
        return _resp(403, text="role_grant denied")               # role-mappings

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(200, {"id": "r", "name": "business"}))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.create_user(email="u@x", password="x", role="business",
                       tenant_id="t", is_owner=True, user_status="active")
    assert exc.value.status_code == 502
    assert "grant_role" in exc.value.detail


# ═════════════════════════════════════════════════════════════════════════════
# 4. CREATE USER WITH MFA REQUIREMENT
# ═════════════════════════════════════════════════════════════════════════════


def test_create_user_mfa_appends_configure_totp(_seeded_token, monkeypatch):
    captured = {}

    def fake_post(url, **kw):
        if url.endswith("/users"):
            captured["body"] = kw["json"]
            return _resp(201, headers={"Location": "/users/uid-1"})
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(200, {"id": "r", "name": "auditor"}))
    ka.create_user(email="auditor@x", password="x", role="auditor",
                   tenant_id="t", is_owner=False, user_status="active",
                   require_mfa=True)
    assert captured["body"]["requiredActions"] == ["VERIFY_EMAIL", "CONFIGURE_TOTP"]


def test_create_user_no_mfa_only_verify_email(_seeded_token, monkeypatch):
    captured = {}

    def fake_post(url, **kw):
        if url.endswith("/users"):
            captured["body"] = kw["json"]
            return _resp(201, headers={"Location": "/users/uid-1"})
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(200, {"id": "r", "name": "business"}))
    ka.create_user(email="u@x", password="x", role="business",
                   tenant_id="t", is_owner=True, user_status="active")
    assert captured["body"]["requiredActions"] == ["VERIFY_EMAIL"]


# ═════════════════════════════════════════════════════════════════════════════
# 5. SET REQUIRED ACTIONS
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("ok_status", [200, 204])
def test_set_required_actions_success_codes(_seeded_token, monkeypatch, ok_status):
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(ok_status))
    ka.set_required_actions("uid-1", ["VERIFY_EMAIL"])  # no raise


@pytest.mark.parametrize("err_status", [400, 401, 403, 404, 500])
def test_set_required_actions_failures_raise(_seeded_token, monkeypatch, err_status):
    monkeypatch.setattr(ka.httpx, "put",
                        lambda *a, **kw: _resp(err_status, text="err"))
    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.set_required_actions("uid-1", [])
    assert exc.value.status_code == 502


def test_set_required_actions_empty_list_clears(_seeded_token, monkeypatch):
    """Empty list = clear all required actions. Used to unblock a user
    after admin manually verifies email out-of-band."""
    captured = {}

    def fake_put(url, **kw):
        captured["body"] = kw["json"]
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "put", fake_put)
    ka.set_required_actions("uid-1", [])
    assert captured["body"] == {"requiredActions": []}


def test_set_required_actions_url_includes_user_id(_seeded_token, monkeypatch):
    captured = {}

    def fake_put(url, **kw):
        captured["url"] = url
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "put", fake_put)
    ka.set_required_actions("the-user-id-xyz", ["VERIFY_EMAIL"])
    assert "/users/the-user-id-xyz" in captured["url"]


# ═════════════════════════════════════════════════════════════════════════════
# 6. ADMIN HEADERS / AUTH
# ═════════════════════════════════════════════════════════════════════════════


def test_admin_headers_include_bearer_token(monkeypatch, _seeded_token):
    h = ka._admin_headers()
    assert h["Authorization"] == "Bearer tok-abc"
    assert h["Content-Type"] == "application/json"


def test_admin_call_refetches_token_when_expired(_seeded_token, monkeypatch):
    """Mid-flow: token cache expires between calls. Next admin op
    triggers fresh fetch."""
    posts = {"n": 0}
    tokens_fetched = []

    def fake_post(url, **kw):
        posts["n"] += 1
        if "/protocol/openid-connect/token" in url:
            tokens_fetched.append(posts["n"])
            return _resp(200, {"access_token": f"tok-{posts['n']}", "expires_in": 60})
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "post", fake_post)
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "get",
                        lambda *a, **kw: _resp(200, {"id": "r", "name": "business"}))

    # First call uses seeded token (no /token call)
    ka._admin_headers()
    # Force expiry
    ka._token_cache["expires_at"] = time.time() - 1
    # Next call refetches
    ka._admin_headers()
    assert len(tokens_fetched) == 1
