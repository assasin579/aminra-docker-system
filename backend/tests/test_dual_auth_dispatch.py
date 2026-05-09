"""Dispatch tests for get_current_user dual-auth (ADR-005 Phase 3a).

Exercises the routing logic in jwt_utils.get_current_user without a live
Keycloak. Uses monkeypatched flag + JWKs cache + DB pool.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt as jose_jwt
from jose.utils import base64url_encode

from auth import jwt_utils
from auth import keycloak_validator as kv


def _make_rsa_jwk(kid: str = "test-kid"):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    n = priv.public_key().public_numbers().n
    e = priv.public_key().public_numbers().e
    jwk = {
        "kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256",
        "n": base64url_encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).decode(),
        "e": base64url_encode(e.to_bytes((e.bit_length() + 7) // 8, "big")).decode(),
    }
    return priv_pem, jwk


def _hs_token(payload: dict) -> str:
    return jose_jwt.encode(payload, jwt_utils.SECRET, algorithm="HS256")


def _rs_token(priv_pem: str, payload: dict) -> str:
    return jose_jwt.encode(payload, priv_pem, algorithm="RS256", headers={"kid": "test-kid"})


def _claims(**overrides):
    base = {
        "sub": "kc-1",
        "email": "kc-user@example.com",
        "iss": kv._ISSUER,
        "aud": kv.KEYCLOAK_AUDIENCE,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "realm_access": {"roles": ["business"]},
    }
    base.update(overrides)
    return base


def _mock_pool(row):
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=db)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.fixture(autouse=True)
def _reset_jwks():
    kv._jwks_cache["keys"] = None
    kv._jwks_cache["fetched_at"] = 0.0
    yield


@pytest.fixture
def fake_request():
    from fastapi import Request
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    return Request(scope)


# ── Flag OFF: only manual HS256 accepted ─────────────────────────────────────


@pytest.mark.asyncio
async def test_flag_off_accepts_manual_hs256(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    token = _hs_token({"sub": "u1", "email": "a@b.com", "exp": int(time.time()) + 300})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_flag_off_rejects_rs256_token(fake_request, monkeypatch):
    """With flag off, RS256 token is sent to decode_token (HS256 path) which
    rejects it as malformed/invalid."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    priv_pem, _ = _make_rsa_jwk()
    token = _rs_token(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_no_creds_raises_401(fake_request):
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, None)
    assert exc.value.status_code == 401


# ── Flag ON: dual-auth, both token types accepted ────────────────────────────


@pytest.mark.asyncio
async def test_flag_on_accepts_keycloak_rs256(fake_request, monkeypatch):
    priv_pem, jwk = _make_rsa_jwk()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])

    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "kc-user@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "is_owner": True,
        "company_name": "ACME",
    }
    monkeypatch.setattr("auth.db.get_pool", lambda: _mock_pool(row))

    token = _rs_token(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["email"] == "kc-user@example.com"
    assert out["_keycloak"] is True
    assert out["role"] == "business"


@pytest.mark.asyncio
async def test_flag_on_still_accepts_manual_hs256(fake_request, monkeypatch):
    """Backward-compat during migration: HS256 tokens issued by the legacy
    /auth/login flow must keep working when the flag is on."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    token = _hs_token({"sub": "u1", "email": "legacy@b.com", "exp": int(time.time()) + 300})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["email"] == "legacy@b.com"
    assert out.get("_keycloak") is not True


@pytest.mark.asyncio
async def test_flag_on_rejects_invalid_keycloak_token(fake_request, monkeypatch):
    priv_pem, jwk = _make_rsa_jwk()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])

    # Wrong audience
    token = _rs_token(priv_pem, _claims(aud="different-app"))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, creds)
    assert exc.value.status_code == 401
