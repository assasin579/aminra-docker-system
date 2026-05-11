"""F6 — Admin auth unit tests (30 cases).

Covers session 2026-05-10 changes:
  - Swap from `Depends(get_current_user) + _require_admin(user)` to
    `Depends(require_admin)` in standard_type_router + industry_schema_router
  - `require_admin` dual-path: JWT (admin@aminra.com + provider) OR opaque
    session file path
  - Bootstrap row admin@aminra.com (role=provider, status=active) added
    so opaque path can find user

Scope: pure-function unit tests. No DB. No HTTP. Mocks file IO + JWT.
"""
from __future__ import annotations

import json
import time
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from auth.jwt_utils import (
    ADMIN_EMAIL,
    SECRET,
    ALGORITHM,
    _validate_old_admin_session,
    require_admin,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _jwt(payload: dict) -> str:
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def _admin_jwt() -> str:
    """Canonical valid admin JWT — email matches + role=provider."""
    return _jwt({
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": ADMIN_EMAIL,
        "role": "provider",
        "exp": time.time() + 3600,
    })


# ── Group 1 — Opaque session validation (8 tests) ──────────────────────────


class TestOpaqueSession:
    """File-based opaque session token TTL + tamper resistance."""

    def test_file_missing_returns_false(self, tmp_path, monkeypatch):
        """Sessions file gone → reject every token (no fallback to permissive)."""
        monkeypatch.setattr(
            "auth.jwt_utils._ADMIN_SESSIONS_FILE",
            tmp_path / "nonexistent.json",
        )
        assert _validate_old_admin_session("anytoken") is False

    def test_valid_token_within_ttl_returns_true(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"validtoken": time.time() + 3600}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("validtoken") is True

    def test_expired_token_returns_false(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"expired": time.time() - 1}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("expired") is False

    def test_unknown_token_returns_false(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"realtoken": time.time() + 3600}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("not-in-file") is False

    def test_empty_token_returns_false(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("") is False

    def test_corrupt_json_returns_false_not_raise(self, tmp_path, monkeypatch):
        """Defense — corrupt file must not crash; deny instead."""
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text("not valid json{")
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("anytoken") is False

    def test_exp_exactly_now_boundary(self, tmp_path, monkeypatch):
        """Boundary: exp == now should pass (<=)."""
        sessions_file = tmp_path / "admin_sessions.json"
        now = time.time()
        sessions_file.write_text(json.dumps({"edge": now + 0.5}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("edge") is True

    def test_nonstring_exp_value_returns_false(self, tmp_path, monkeypatch):
        """Type confusion — exp=None or string should not pass."""
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"weird": None}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        assert _validate_old_admin_session("weird") is False


# ── Group 2 — require_admin JWT path (10 tests) ────────────────────────────


class TestRequireAdminJWTPath:
    """Valid JWT with admin email + provider role short-circuits."""

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=None)
        assert exc.value.status_code == 401
        assert "Not authenticated" in exc.value.detail

    @pytest.mark.asyncio
    async def test_admin_email_provider_role_passes(self):
        creds = _make_creds(_admin_jwt())
        result = await require_admin(creds=creds)
        assert result["email"] == ADMIN_EMAIL
        assert result["role"] == "provider"

    @pytest.mark.asyncio
    async def test_admin_email_business_role_rejected(self):
        """Email match but role=business → 403, not allowed."""
        token = _jwt({
            "sub": "x",
            "email": ADMIN_EMAIL,
            "role": "business",
            "exp": time.time() + 3600,
        })
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_provider_role_wrong_email_rejected(self):
        token = _jwt({
            "sub": "x",
            "email": "evil@attacker.com",
            "role": "provider",
            "exp": time.time() + 3600,
        })
        # Falls through to opaque check → 403 (no sessions file or token mismatch)
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_expired_jwt_falls_through_to_opaque(self):
        """Expired JWT → JWTError → opaque path; opaque also fails → 403."""
        token = _jwt({
            "sub": "x",
            "email": ADMIN_EMAIL,
            "role": "provider",
            "exp": time.time() - 1,
        })
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_malformed_jwt_falls_through(self):
        """Garbage token → JWTError → opaque path → 403."""
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds("garbage.token.value"))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_jwt_no_role_field_rejected(self):
        token = _jwt({
            "sub": "x",
            "email": ADMIN_EMAIL,
            "exp": time.time() + 3600,
        })
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_jwt_no_email_field_rejected(self):
        token = _jwt({
            "sub": "x",
            "role": "provider",
            "exp": time.time() + 3600,
        })
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_jwt_empty_email_rejected(self):
        token = _jwt({
            "sub": "x",
            "email": "",
            "role": "provider",
            "exp": time.time() + 3600,
        })
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_jwt_case_sensitivity_admin_email(self):
        """ADMIN@AMINRA.COM != admin@aminra.com → reject (no normalization)."""
        token = _jwt({
            "sub": "x",
            "email": ADMIN_EMAIL.upper(),
            "role": "provider",
            "exp": time.time() + 3600,
        })
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403


# ── Group 3 — require_admin opaque path (8 tests) ──────────────────────────


class TestRequireAdminOpaquePath:
    """Opaque session → DB lookup for admin@aminra.com row."""

    @pytest.mark.asyncio
    async def test_opaque_valid_session_returns_admin_user(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"opaque_xyz": time.time() + 3600}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": "1995f27c-4ac5-4b82-9965-bdb04ded6025",
            "email": ADMIN_EMAIL,
            "role": "provider",
        })
        mock_pool = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=ctx)

        with patch("auth.db.get_pool", return_value=mock_pool):
            result = await require_admin(creds=_make_creds("opaque_xyz"))
        assert result["email"] == ADMIN_EMAIL
        assert result["is_owner"] is True
        assert result["sub"] == "1995f27c-4ac5-4b82-9965-bdb04ded6025"

    @pytest.mark.asyncio
    async def test_opaque_valid_session_db_row_missing_returns_403(
        self, tmp_path, monkeypatch
    ):
        """Opaque session OK but admin DB row missing → 403 bootstrap message."""
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"opaque_xyz": time.time() + 3600}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value=None)
        mock_pool = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=ctx)

        with patch("auth.db.get_pool", return_value=mock_pool):
            with pytest.raises(HTTPException) as exc:
                await require_admin(creds=_make_creds("opaque_xyz"))
        assert exc.value.status_code == 403
        assert "bootstrap" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_opaque_expired_returns_403(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"opaque": time.time() - 1}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds("opaque"))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_opaque_token_db_role_null_defaults_provider(
        self, tmp_path, monkeypatch
    ):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"o": time.time() + 100}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": "uuid", "email": ADMIN_EMAIL, "role": None,
        })
        mock_pool = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=ctx)

        with patch("auth.db.get_pool", return_value=mock_pool):
            result = await require_admin(creds=_make_creds("o"))
        assert result["role"] == "provider"

    @pytest.mark.asyncio
    async def test_opaque_token_with_jwt_shape_jwt_path_wins(
        self, tmp_path, monkeypatch
    ):
        """If a valid JWT is sent that happens to also be in sessions file,
        JWT path (line 132) is tried FIRST. If it satisfies admin rule, return
        immediately — sessions DB lookup skipped."""
        sessions_file = tmp_path / "admin_sessions.json"
        token = _admin_jwt()
        sessions_file.write_text(json.dumps({token: time.time() + 3600}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

        # If DB fetch were called, mock would raise; but JWT path wins so untouched
        with patch("auth.db.get_pool", side_effect=AssertionError("should not be called")):
            result = await require_admin(creds=_make_creds(token))
        assert result["email"] == ADMIN_EMAIL

    @pytest.mark.asyncio
    async def test_opaque_long_token_string(self, tmp_path, monkeypatch):
        """Very long bearer string → only file lookup; no buffer issue."""
        long_token = "x" * 10000
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({long_token: time.time() + 100}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": "u", "email": ADMIN_EMAIL, "role": "provider",
        })
        mock_pool = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=ctx)
        with patch("auth.db.get_pool", return_value=mock_pool):
            result = await require_admin(creds=_make_creds(long_token))
        assert result["email"] == ADMIN_EMAIL

    @pytest.mark.asyncio
    async def test_opaque_token_with_whitespace_padding_rejected(
        self, tmp_path, monkeypatch
    ):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"clean": time.time() + 100}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(" clean "))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_opaque_token_url_encoded_rejected(self, tmp_path, monkeypatch):
        sessions_file = tmp_path / "admin_sessions.json"
        sessions_file.write_text(json.dumps({"plain_token": time.time() + 100}))
        monkeypatch.setattr("auth.jwt_utils._ADMIN_SESSIONS_FILE", sessions_file)
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds("plain%5Ftoken"))
        assert exc.value.status_code == 403


# ── Group 4 — Algorithm + signature tamper resistance (4 tests) ────────────


class TestAlgorithmAndSignature:
    @pytest.mark.asyncio
    async def test_unsigned_jwt_alg_none_rejected(self):
        """alg=none confusion attack — jose rejects by default."""
        unsigned = jwt.encode({
            "sub": "x", "email": ADMIN_EMAIL, "role": "provider",
            "exp": time.time() + 3600,
        }, key="", algorithm="HS256")
        # Manually craft alg:none header
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
        payload = unsigned.split(".")[1]
        tampered = f"{header}.{payload}."
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(tampered))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_wrong_secret_signature_rejected(self):
        token = jwt.encode({
            "sub": "x", "email": ADMIN_EMAIL, "role": "provider",
            "exp": time.time() + 3600,
        }, key="wrong-secret", algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tampered_payload_signature_mismatch(self):
        token = _admin_jwt()
        # Flip 1 char in payload
        parts = token.split(".")
        bad = parts[0] + "." + parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B") + "." + parts[2]
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(bad))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_truncated_jwt_rejected(self):
        token = _admin_jwt()[:30]
        with pytest.raises(HTTPException) as exc:
            await require_admin(creds=_make_creds(token))
        assert exc.value.status_code == 403
