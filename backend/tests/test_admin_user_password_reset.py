"""Regression coverage for admin-managed user password reset.

The admin user editor has a password field. After Keycloak cutover, profile
PUT ignored that field, causing false-success password changes. Password resets
must call a dedicated Keycloak reset-password proxy endpoint instead.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auth import keycloak_admin as ka

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if (BACKEND_ROOT / "app.py").exists():
    # In the backend container tests live under /app/tests.
    APP_FILE = BACKEND_ROOT / "app.py"
    ADMIN_USER_MANAGER = BACKEND_ROOT / "frontend" / "aminra-web" / "components" / "AdminUserManager.tsx"
else:
    REPO_ROOT = BACKEND_ROOT.parent
    APP_FILE = REPO_ROOT / "backend" / "app.py"
    ADMIN_USER_MANAGER = (
        REPO_ROOT / "frontend" / "aminra-web" / "components" / "AdminUserManager.tsx"
    )


@pytest.fixture(autouse=True)
def _seeded_token(monkeypatch):
    ka._token_cache["token"] = "tok-admin"
    ka._token_cache["expires_at"] = time.time() + 300
    monkeypatch.setattr(ka, "ADMIN_CLI_SECRET", "test-secret")


def _resp(status_code: int, json_body: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body or {}
    r.headers = {}
    r.text = text
    return r


def test_keycloak_admin_reset_user_password_calls_reset_password_endpoint_and_revokes_sessions(monkeypatch):
    calls = []

    def fake_put(url, **kwargs):
        calls.append(("PUT", url, kwargs))
        return _resp(204)

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return _resp(204)

    monkeypatch.setattr(ka.httpx, "put", fake_put)
    monkeypatch.setattr(ka.httpx, "post", fake_post)

    ka.reset_user_password("kc-user-1", "StrongPass2026!")

    assert len(calls) == 2
    method, url, kwargs = calls[0]
    assert method == "PUT"
    assert url.endswith("/users/kc-user-1/reset-password")
    assert kwargs["json"] == {
        "type": "password",
        "value": "StrongPass2026!",
        "temporary": False,
    }
    method, url, kwargs = calls[1]
    assert method == "POST"
    assert url.endswith("/users/kc-user-1/logout")
    assert "StrongPass2026!" not in str(kwargs)


def test_keycloak_admin_reset_user_password_fails_closed_when_session_revoke_fails(monkeypatch):
    monkeypatch.setattr(ka.httpx, "put", lambda *a, **kw: _resp(204))
    monkeypatch.setattr(ka.httpx, "post", lambda *a, **kw: _resp(500, text="boom"))

    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.reset_user_password("kc-user-1", "StrongPass2026!")

    assert exc.value.status_code == 502
    assert "logout" in str(exc.value.detail).lower() or "session" in str(exc.value.detail).lower()
    assert "StrongPass2026!" not in str(exc.value.detail)


def test_keycloak_admin_reset_user_password_maps_password_history_error(monkeypatch):
    monkeypatch.setattr(
        ka.httpx,
        "put",
        lambda *a, **kw: _resp(400, text="invalidPasswordHistoryMessage"),
    )

    with pytest.raises(ka.KeycloakAdminError) as exc:
        ka.reset_user_password("kc-user-1", "RecentlyUsedPass2026!")

    assert exc.value.status_code == 400
    assert "mật khẩu gần đây" in str(exc.value.detail).lower()
    assert "RecentlyUsedPass" not in str(exc.value.detail)


def test_admin_backend_exposes_dedicated_reset_password_route():
    text = APP_FILE.read_text(encoding="utf-8")

    assert '@app.post("/admin/users/{user_id}/reset-password")' in text
    assert "class AdminResetPasswordRequest" in text
    assert "new_password: str" in text
    assert "keycloak_admin.reset_user_password" in text
    assert re.search(r"SELECT\s+[^\n]*keycloak_sub[^\n]*email", text, re.IGNORECASE)
    assert "sessions_revoked" in text
    assert "self_reset" in text
    assert "admin_claims" in text


def test_admin_profile_update_contract_does_not_accept_password_field():
    text = APP_FILE.read_text(encoding="utf-8")
    match = re.search(
        r"class AdminUpdateUserRequest\(BaseModel\):(?P<body>.*?)\n\nclass AdminResetPasswordRequest",
        text,
        re.DOTALL,
    )
    assert match, "AdminUpdateUserRequest block not found"
    assert "password:" not in match.group("body")
    assert "new_password" not in match.group("body")


def test_admin_user_editor_uses_reset_password_route_not_profile_put_password():
    text = ADMIN_USER_MANAGER.read_text(encoding="utf-8")

    assert "/admin/users/${editTarget.id}/reset-password" in text
    assert "new_password: form.password" in text
    assert "body.password = form.password" not in text
    # Password-only edit must be a valid save instead of showing "no changes".
    assert "profileBody" in text
    assert "passwordChanged" in text
