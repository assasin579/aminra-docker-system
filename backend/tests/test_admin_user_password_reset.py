"""Regression coverage for Keycloak-owned credential management."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auth import keycloak_admin as ka

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if (BACKEND_ROOT / "app.py").exists():
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


def test_admin_backend_deprecates_app_side_password_reset_route():
    text = APP_FILE.read_text(encoding="utf-8")

    assert '@app.post("/admin/users/{user_id}/reset-password")' in text
    reset_start = text.index("async def admin_reset_user_password")
    reset_body = text[reset_start : text.index("\n\n@app.put", reset_start)]
    guard_pos = reset_body.index("_raise_keycloak_only_account_management()")
    assert "_require_admin(request)" in reset_body[:guard_pos]
    assert "keycloak_admin.reset_user_password" not in reset_body[:guard_pos]
    assert '"identity_lifecycle_owner": "keycloak"' in text


def test_admin_user_editor_has_no_password_reset_or_profile_mutation_ui():
    text = ADMIN_USER_MANAGER.read_text(encoding="utf-8")

    assert 'data-identity-owner="keycloak"' in text
    assert "Open in Keycloak" in text
    assert "reset mật khẩu" in text
    assert "/admin/users/${editTarget.id}/reset-password" not in text
    assert "new_password: form.password" not in text
    assert "body.password = form.password" not in text
    assert "passwordChanged" not in text
    assert "profileBody" not in text
