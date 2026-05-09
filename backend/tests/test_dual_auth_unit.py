"""Unit tests for dual-auth Keycloak validator (ADR-005 Phase 3a).

Stand-alone — no live Keycloak, no DB. Generates an RSA keypair in
process, signs tokens, monkeypatches the JWKs cache, and exercises the
validator paths that get_current_user relies on.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt as jose_jwt
from jose.utils import base64url_encode

from auth import keycloak_validator as kv


# ── Test helpers ─────────────────────────────────────────────────────────────


def _make_rsa_jwk(kid: str = "test-kid"):
    """Generate a fresh RSA keypair + matching JWK dict."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_numbers = priv.public_key().public_numbers()
    n = base64url_encode(pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, "big")).decode()
    e = base64url_encode(pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, "big")).decode()
    jwk = {"kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256", "n": n, "e": e}
    return priv_pem, jwk


def _sign_rs256(priv_pem: str, claims: dict, kid: str = "test-kid") -> str:
    return jose_jwt.encode(claims, priv_pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    kv._jwks_cache["keys"] = None
    kv._jwks_cache["fetched_at"] = 0.0
    yield


@pytest.fixture
def keypair():
    return _make_rsa_jwk()


# ── looks_like_keycloak_token ────────────────────────────────────────────────


def test_looks_like_keycloak_returns_true_for_rs256_with_kid(keypair):
    priv_pem, _ = keypair
    token = _sign_rs256(priv_pem, {"sub": "u"}, kid="abc")
    assert kv.looks_like_keycloak_token(token) is True


def test_looks_like_keycloak_returns_false_for_hs256():
    token = jose_jwt.encode({"sub": "u"}, "test-secret", algorithm="HS256")
    assert kv.looks_like_keycloak_token(token) is False


def test_looks_like_keycloak_returns_false_for_garbage():
    assert kv.looks_like_keycloak_token("not.a.token") is False
    assert kv.looks_like_keycloak_token("") is False


# ── validate_keycloak_token ──────────────────────────────────────────────────


def _claims(**overrides):
    base = {
        "sub": "kc-uuid-1",
        "email": "user@example.com",
        "iss": kv._ISSUER,
        "aud": kv.KEYCLOAK_AUDIENCE,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "realm_access": {"roles": ["business"]},
    }
    base.update(overrides)
    return base


def test_validate_accepts_correct_token(monkeypatch, keypair):
    priv_pem, jwk = keypair
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    token = _sign_rs256(priv_pem, _claims())
    out = kv.validate_keycloak_token(token)
    assert out["email"] == "user@example.com"
    assert out["realm_access"]["roles"] == ["business"]


def test_validate_rejects_wrong_audience(monkeypatch, keypair):
    priv_pem, jwk = keypair
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    token = _sign_rs256(priv_pem, _claims(aud="wrong-aud"))
    with pytest.raises(HTTPException) as exc:
        kv.validate_keycloak_token(token)
    assert exc.value.status_code == 401


def test_validate_rejects_wrong_issuer(monkeypatch, keypair):
    priv_pem, jwk = keypair
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    token = _sign_rs256(priv_pem, _claims(iss="https://evil.example.com"))
    with pytest.raises(HTTPException) as exc:
        kv.validate_keycloak_token(token)
    assert exc.value.status_code == 401


def test_validate_rejects_expired_token(monkeypatch, keypair):
    priv_pem, jwk = keypair
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    token = _sign_rs256(priv_pem, _claims(exp=int(time.time()) - 60))
    with pytest.raises(HTTPException) as exc:
        kv.validate_keycloak_token(token)
    assert exc.value.status_code == 401


def test_validate_rejects_unknown_kid(monkeypatch, keypair):
    priv_pem, jwk = keypair
    # JWKs returns DIFFERENT kid than token header
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [{**jwk, "kid": "other-kid"}])
    token = _sign_rs256(priv_pem, _claims(), kid="test-kid")
    with pytest.raises(HTTPException) as exc:
        kv.validate_keycloak_token(token)
    assert exc.value.status_code == 401
    assert "Unknown signing key" in exc.value.detail


def test_validate_rejects_token_signed_by_different_key(monkeypatch, keypair):
    _, jwk = keypair
    other_priv, _ = _make_rsa_jwk(kid="test-kid")  # Same kid, different key
    monkeypatch.setattr(kv, "_fetch_jwks", lambda force=False: [jwk])
    token = _sign_rs256(other_priv, _claims())
    with pytest.raises(HTTPException) as exc:
        kv.validate_keycloak_token(token)
    assert exc.value.status_code == 401


def test_validate_rejects_garbage_token():
    with pytest.raises(HTTPException):
        kv.validate_keycloak_token("not.a.token")


# ── enrich_keycloak_claims ───────────────────────────────────────────────────


def _mock_pool(row=None):
    """Build an asyncpg-shaped pool mock that returns a single row."""
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=db)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.mark.asyncio
async def test_enrich_returns_db_user_shape():
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "is_owner": True,
        "company_name": "ACME Co",
    }
    pool = _mock_pool(row=row)
    out = await kv.enrich_keycloak_claims(
        {"sub": "kc-1", "email": "user@example.com", "realm_access": {"roles": ["business"]}},
        pool,
    )
    assert out["email"] == "user@example.com"
    assert out["role"] == "business"
    assert out["is_owner"] is True
    assert out["status"] == "active"
    assert out["tenant_id"] == "22222222-2222-2222-2222-222222222222"
    assert out["_keycloak"] is True


@pytest.mark.asyncio
async def test_enrich_handles_missing_db_row():
    """Keycloak-authenticated user with no DB record yet (post Phase 4
    re-register flow). Should return minimal pending shape."""
    pool = _mock_pool(row=None)
    out = await kv.enrich_keycloak_claims(
        {"sub": "kc-1", "email": "newuser@example.com", "realm_access": {"roles": ["auditor"]}},
        pool,
    )
    assert out["email"] == "newuser@example.com"
    assert out["role"] == "auditor"
    assert out["status"] == "pending"
    assert out["tenant_id"] is None
    assert out["_keycloak"] is True


@pytest.mark.asyncio
async def test_enrich_rejects_token_without_email():
    pool = _mock_pool(row=None)
    with pytest.raises(HTTPException) as exc:
        await kv.enrich_keycloak_claims({"sub": "kc-1"}, pool)
    assert exc.value.status_code == 401


# ── _pick_app_role priority ──────────────────────────────────────────────────


def test_pick_app_role_priority_order():
    assert kv._pick_app_role(["business", "platform_admin"]) == "platform_admin"
    assert kv._pick_app_role(["business", "auditor"]) == "auditor"
    assert kv._pick_app_role(["cb_admin", "auditor"]) == "cb_admin"
    assert kv._pick_app_role(["business"]) == "business"


def test_pick_app_role_returns_none_when_no_app_role():
    assert kv._pick_app_role([]) is None
    assert kv._pick_app_role(["offline_access", "uma_authorization"]) is None


# ── JWKs cache behaviour ─────────────────────────────────────────────────────


def test_jwks_cache_does_not_refetch_within_ttl(monkeypatch):
    call_count = {"n": 0}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self):
            call_count["n"] += 1
            return {"keys": [{"kid": "k1", "kty": "RSA"}]}

    monkeypatch.setattr(kv.httpx, "get", lambda *a, **kw: _FakeResp())
    kv._fetch_jwks()
    kv._fetch_jwks()
    kv._fetch_jwks()
    assert call_count["n"] == 1


def test_jwks_cache_refetches_after_ttl(monkeypatch):
    call_count = {"n": 0}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self):
            call_count["n"] += 1
            return {"keys": [{"kid": f"k{call_count['n']}", "kty": "RSA"}]}

    monkeypatch.setattr(kv.httpx, "get", lambda *a, **kw: _FakeResp())
    kv._fetch_jwks()
    # Simulate TTL elapsed
    kv._jwks_cache["fetched_at"] = time.time() - kv._JWKS_TTL - 1
    kv._fetch_jwks()
    assert call_count["n"] == 2


def test_jwks_cache_force_refetches(monkeypatch):
    call_count = {"n": 0}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self):
            call_count["n"] += 1
            return {"keys": []}

    monkeypatch.setattr(kv.httpx, "get", lambda *a, **kw: _FakeResp())
    kv._fetch_jwks()
    kv._fetch_jwks(force=True)
    assert call_count["n"] == 2
