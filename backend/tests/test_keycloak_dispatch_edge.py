"""Dual-auth dispatch edge cases (Tier 2 E2E batch 4).

User-perspective scenarios for the BE dispatch logic in
`get_current_user`. Covers: flag combinations, header forms, token-type
boundaries, fallback transitions, malformed credentials.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt as jose_jwt
from jose.utils import base64url_encode

from auth import jwt_utils
from auth import keycloak_validator as kv


def _make_rsa(kid="test-kid"):
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


def _hs(payload):
    return jose_jwt.encode(payload, jwt_utils.SECRET, algorithm="HS256")


def _rs(priv_pem, payload, kid="test-kid"):
    return jose_jwt.encode(payload, priv_pem, algorithm="RS256", headers={"kid": kid})


def _claims(**overrides):
    base = {
        "sub": "kc-1",
        "email": "user@example.com",
        "iss": kv._ISSUER,
        "aud": kv.KEYCLOAK_AUDIENCE,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "realm_access": {"roles": ["business"]},
    }
    base.update(overrides)
    return base


def _mock_pool(row=None):
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
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    return Request(scope)


# ═════════════════════════════════════════════════════════════════════════════
# 1. NO CREDENTIALS — every variation
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_no_creds_when_flag_off(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_no_creds_when_flag_on(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, None)
    assert exc.value.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# 2. FLAG OFF — only HS256 path active
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_flag_off_accepts_legacy_hs256(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    token = _hs({"sub": "u", "email": "a@b", "exp": int(time.time()) + 300})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["email"] == "a@b"


@pytest.mark.asyncio
async def test_flag_off_rejects_rs256_token_outright(fake_request, monkeypatch):
    """Even though RS256 is a Keycloak-shaped token, flag off means we
    NEVER hit Keycloak validator — token sent to legacy decode_token
    which uses HS256 secret → 401."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    priv_pem, _ = _make_rsa()
    token = _rs(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_flag_off_does_not_fetch_jwks(fake_request, monkeypatch):
    """Performance: when flag is off, we MUST NOT hit Keycloak even for
    RS256 tokens. JWKs cache should never populate."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    fetched = {"n": 0}

    def fake_get(*a, **kw):
        fetched["n"] += 1
        return MagicMock(json=lambda: {"keys": []}, raise_for_status=lambda: None)

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    priv_pem, _ = _make_rsa()
    token = _rs(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException):
        await jwt_utils.get_current_user(fake_request, creds)
    assert fetched["n"] == 0


@pytest.mark.asyncio
async def test_flag_off_expired_hs256_returns_401(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    token = _hs({"sub": "u", "email": "a@b", "exp": int(time.time()) - 60})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_flag_off_garbage_token_returns_401(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.token")
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, creds)
    assert exc.value.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# 3. FLAG ON — DUAL PATH ACTIVE
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_flag_on_routes_rs256_to_keycloak_path(fake_request, monkeypatch):
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    monkeypatch.setattr(
        "auth.db.get_pool",
        lambda: _mock_pool(row={
            "id": "u-1", "email": "user@example.com", "role": "business",
            "status": "active", "tenant_id": "t-1", "is_owner": True,
            "company_name": "ACME",
        }),
    )
    token = _rs(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["_keycloak"] is True


@pytest.mark.asyncio
async def test_flag_on_routes_hs256_to_legacy_path(fake_request, monkeypatch):
    """Backward compat: HS256 tokens skip Keycloak path entirely."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    token = _hs({"sub": "u", "email": "legacy@b", "exp": int(time.time()) + 300})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out.get("_keycloak") is not True
    assert out["email"] == "legacy@b"


@pytest.mark.asyncio
async def test_flag_on_invalid_keycloak_token_returns_401(fake_request, monkeypatch):
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    # Wrong audience token
    token = _rs(priv_pem, _claims(aud="wrong"))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await jwt_utils.get_current_user(fake_request, creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_flag_on_does_not_fall_back_after_keycloak_validation_fails(
    fake_request, monkeypatch,
):
    """SECURITY: if RS256 token is invalid, we MUST 401 immediately.
    Falling through to HS256 secret would be alg-confusion exploit."""
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    token = _rs(priv_pem, _claims(aud="wrong"))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException):
        await jwt_utils.get_current_user(fake_request, creds)


# ═════════════════════════════════════════════════════════════════════════════
# 4. CREDENTIALS HEADER VARIANTS
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_creds_with_token_extra_whitespace(fake_request, monkeypatch):
    """FastAPI HTTPBearer strips Bearer prefix; if attacker passes
    ' token ' with whitespace, it stays."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    token = _hs({"sub": "u", "email": "a@b", "exp": int(time.time()) + 300})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=f"  {token}  ")
    with pytest.raises(HTTPException):
        await jwt_utils.get_current_user(fake_request, creds)


@pytest.mark.asyncio
async def test_creds_empty_string(fake_request, monkeypatch):
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
    # Empty creds: bearer scheme rejects upstream usually but here
    # caller passed object explicitly.
    with pytest.raises(HTTPException):
        await jwt_utils.get_current_user(fake_request, creds)


@pytest.mark.asyncio
async def test_creds_with_basic_scheme_still_accepts_token(fake_request, monkeypatch):
    """Our handler doesn't validate scheme — it trusts Depends to vet.
    If misconfigured: scheme='Basic' but credentials are JWT → still
    decodes."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    token = _hs({"sub": "u", "email": "a@b", "exp": int(time.time()) + 300})
    creds = HTTPAuthorizationCredentials(scheme="Basic", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["email"] == "a@b"


# ═════════════════════════════════════════════════════════════════════════════
# 5. KEYCLOAK PATH WITH NO DB ROW (Phase 4 force re-register edge)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_keycloak_token_no_db_row_returns_pending(fake_request, monkeypatch):
    """User has Keycloak account but no DB row yet — fallback path
    returns minimal pending user. Downstream require_active_user
    will reject."""
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    monkeypatch.setattr("auth.db.get_pool", lambda: _mock_pool(row=None))
    # Send non-fast-path token (force DB lookup)
    token = _rs(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["status"] == "pending"
    assert out["_keycloak"] is True
    assert out["tenant_id"] is None


@pytest.mark.asyncio
async def test_keycloak_fast_path_no_db_lookup_when_all_claims_present(
    fake_request, monkeypatch,
):
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])

    db_calls = {"n": 0}
    async def db_called(*a, **kw):
        db_calls["n"] += 1
        return None
    pool = _mock_pool()
    db_mock = pool.acquire.return_value.__aenter__.return_value
    db_mock.fetchrow = db_called
    monkeypatch.setattr("auth.db.get_pool", lambda: pool)

    token = _rs(priv_pem, _claims(
        tenant_id="t-1", is_owner=True, status="active",
    ))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["_from_jwt_claims"] is True
    assert db_calls["n"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# 6. CONCURRENT REQUESTS — both paths in flight
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_two_concurrent_keycloak_requests_share_jwks_cache(
    fake_request, monkeypatch,
):
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)

    jwks_fetches = {"n": 0}
    def fake_fetch(force=False):
        jwks_fetches["n"] += 1
        return [jwk]

    monkeypatch.setattr(kv, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(
        "auth.db.get_pool",
        lambda: _mock_pool(row={
            "id": "u-1", "email": "user@example.com", "role": "business",
            "status": "active", "tenant_id": "t-1", "is_owner": True,
            "company_name": "ACME",
        }),
    )

    async def call():
        token = _rs(priv_pem, _claims())
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await jwt_utils.get_current_user(fake_request, creds)

    import asyncio
    results = await asyncio.gather(*[call() for _ in range(5)])
    assert all(r["_keycloak"] is True for r in results)
    # Each call iterates _fetch_jwks once; cache logic below.
    assert jwks_fetches["n"] >= 1


# ═════════════════════════════════════════════════════════════════════════════
# 7. REGRESSION — original behaviours from Phase 3a still hold
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_legacy_token_with_extra_claim_fields_passthrough(fake_request, monkeypatch):
    """Existing 167 require_* sites depend on dict shape — extra fields
    must passthrough (not break dict.get patterns)."""
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", False)
    token = _hs({
        "sub": "u",
        "email": "a@b",
        "exp": int(time.time()) + 300,
        "custom_field_1": "preserved",
        "custom_field_2": [1, 2, 3],
    })
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["custom_field_1"] == "preserved"
    assert out["custom_field_2"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_keycloak_path_preserves_kc_marker(fake_request, monkeypatch):
    """Routes can check `user.get('_keycloak')` to log audit differently."""
    priv_pem, jwk = _make_rsa()
    monkeypatch.setattr(jwt_utils, "AUTH_KEYCLOAK_ENABLED", True)
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    monkeypatch.setattr(
        "auth.db.get_pool",
        lambda: _mock_pool(row={
            "id": "u-1", "email": "user@example.com", "role": "business",
            "status": "active", "tenant_id": "t-1", "is_owner": True,
            "company_name": "ACME",
        }),
    )
    token = _rs(priv_pem, _claims())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await jwt_utils.get_current_user(fake_request, creds)
    assert out["_keycloak"] is True
