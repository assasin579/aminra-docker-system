"""Phase 3b fast-path tests for keycloak_validator.

When the Keycloak realm has the tenant_id / is_owner / status protocol
mappers configured (per scripts/keycloak-bootstrap.sh §4b), the JWT
carries app-domain claims directly. enrich_keycloak_claims must then
skip the DB lookup entirely.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from auth import keycloak_validator as kv


def _mock_pool(row=None):
    """asyncpg-shaped pool. db.fetchrow.assert_called assertions are used
    to verify whether the fallback path was taken."""
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=db)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, db


def _full_mapper_claims(**overrides):
    base = {
        "sub": "kc-uuid-1",
        "email": "user@example.com",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "is_owner": True,
        "status": "active",
        "realm_access": {"roles": ["business"]},
    }
    base.update(overrides)
    return base


# ── Fast path activation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_path_skips_db_when_all_mapper_claims_present():
    pool, db = _mock_pool(row={"should": "not be reached"})
    out = await kv.enrich_keycloak_claims(_full_mapper_claims(), pool)
    assert out["_from_jwt_claims"] is True
    assert out["tenant_id"] == "22222222-2222-2222-2222-222222222222"
    assert out["is_owner"] is True
    assert out["status"] == "active"
    assert out["role"] == "business"
    db.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_fast_path_handles_string_boolean_for_is_owner():
    """Some Keycloak versions serialise jsonType=boolean as 'true'/'false'."""
    pool, db = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _full_mapper_claims(is_owner="true"), pool
    )
    assert out["is_owner"] is True
    db.fetchrow.assert_not_called()

    pool, db = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _full_mapper_claims(is_owner="false"), pool
    )
    assert out["is_owner"] is False


@pytest.mark.asyncio
async def test_fast_path_normalises_tenant_id_to_string():
    pool, _ = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _full_mapper_claims(tenant_id="22222222-2222-2222-2222-222222222222"), pool,
    )
    assert out["tenant_id"] == "22222222-2222-2222-2222-222222222222"
    assert isinstance(out["tenant_id"], str)


@pytest.mark.asyncio
async def test_fast_path_rejects_non_uuid_tenant_id_mapper_value():
    """Stale Keycloak user attributes used slugs/ints for tenant_id. Those must
    not activate JWT-only enrichment because downstream tenant queries require
    AMINRA-canonical UUIDs."""
    pool, db = _mock_pool(row={
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": "33333333-3333-3333-3333-333333333333",
        "is_owner": True,
        "company_name": "ACME",
    })
    out = await kv.enrich_keycloak_claims(_full_mapper_claims(tenant_id=12345), pool)
    assert out.get("_from_jwt_claims") is not True
    assert out["tenant_id"] == "33333333-3333-3333-3333-333333333333"
    db.fetchrow.assert_called_once()


# ── Fallback path activation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_when_tenant_id_missing():
    """Mapper not configured for tenant_id → DB lookup is required."""
    pool, db = _mock_pool(row={
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "is_owner": True,
        "company_name": "ACME",
    })
    claims = _full_mapper_claims()
    claims.pop("tenant_id")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out.get("_from_jwt_claims") is not True
    assert out["_keycloak"] is True
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_when_is_owner_missing():
    pool, db = _mock_pool(row=None)
    claims = _full_mapper_claims()
    claims.pop("is_owner")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_when_status_missing():
    pool, db = _mock_pool(row=None)
    claims = _full_mapper_claims()
    claims.pop("status")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_treats_explicit_none_as_missing():
    """A claim sent as null shouldn't activate the fast path."""
    pool, db = _mock_pool(row=None)
    out = await kv.enrich_keycloak_claims(
        _full_mapper_claims(tenant_id=None), pool,
    )
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()


# ── Helpers ──────────────────────────────────────────────────────────────────


def test_has_full_mapper_claims():
    base = {
        "email": "u@x",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "is_owner": True,
        "status": "active",
    }
    assert kv._has_full_mapper_claims(base) is True
    assert kv._has_full_mapper_claims({**base, "tenant_id": "tenant-slug"}) is False
    assert kv._has_full_mapper_claims({**base, "tenant_id": None}) is False
    for missing in ("email", "tenant_id", "is_owner", "status"):
        bad = dict(base)
        del bad[missing]
        assert kv._has_full_mapper_claims(bad) is False
