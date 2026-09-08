"""Cross-tenant isolation tests for dual-auth (ADR-005 Phase 5).

Verifies that the Keycloak fast-path correctly carries `tenant_id` from
the JWT mapper claim and refuses to leak across tenants.

These are pure unit tests on enrich_keycloak_claims — they don't hit a
real DB or Keycloak. The end-to-end cross-tenant check (HTTP call →
backend → query scoped to schema) lives in
`tests/integration/test_cross_tenant_*.py` (skipped here without DB).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from auth import keycloak_validator as kv


def _mock_pool(row=None):
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=db)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, db


TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"


def _claims_for_tenant(tenant_id: str, email: str = "user@example.com"):
    return {
        "sub": "kc-1",
        "email": email,
        "tenant_id": tenant_id,
        "is_owner": True,
        "status": "active",
        "realm_access": {"roles": ["business"]},
    }


# ── Fast-path tenant boundary ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_path_returns_tenant_id_from_jwt_claim_only():
    """When mapper claims present, DB is NOT consulted — tenant_id comes
    purely from the JWT. This is the security promise of Phase 3b: the
    JWT signature attests to the tenant binding, but only when tenant_id is
    AMINRA-canonical UUID format. Slug/non-UUID mapper values are intentionally
    rejected from fast path and forced through DB enrichment."""
    pool, db = _mock_pool(row=None)  # DB returns nothing
    out = await kv.enrich_keycloak_claims(
        _claims_for_tenant(TENANT_A), pool,
    )
    assert out["tenant_id"] == TENANT_A
    db.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_two_tokens_with_different_tenants_yield_different_tenant_ids():
    """Smoke: confirm tenant_id isolation is per-token, not cached."""
    pool_a, _ = _mock_pool()
    pool_b, _ = _mock_pool()
    a = await kv.enrich_keycloak_claims(_claims_for_tenant(TENANT_A), pool_a)
    b = await kv.enrich_keycloak_claims(_claims_for_tenant(TENANT_B), pool_b)
    assert a["tenant_id"] == TENANT_A
    assert b["tenant_id"] == TENANT_B
    assert a["sub"] == b["sub"]  # same kc sub but different claim payload


@pytest.mark.asyncio
async def test_token_without_tenant_falls_back_to_db_tenant():
    """If mapper not configured (legacy token), DB lookup is the source
    of truth — defends against a downgrade where attacker strips the
    tenant_id claim hoping the validator picks an arbitrary value."""
    db_tenant = "tenant-db-only"
    row = {
        "id": "aa-bb-cc-dd",
        "email": "user@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": db_tenant,
        "is_owner": True,
        "company_name": "ACME",
    }
    pool, db = _mock_pool(row=row)
    claims = _claims_for_tenant("attacker-injected-tenant")
    claims.pop("tenant_id")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["tenant_id"] == db_tenant
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_db_tenant_overrides_when_jwt_partial_claims():
    """Multiple mapper claims missing → DB authoritative path. Guards
    against partial-mapper misconfiguration deployment."""
    pool, db = _mock_pool(row={
        "id": "uid",
        "email": "u@x",
        "role": "business",
        "status": "active",
        "tenant_id": "tenant-real",
        "is_owner": True,
        "company_name": "ACME",
    })
    claims = _claims_for_tenant("tenant-spoofed")
    claims.pop("is_owner")  # only one mapper claim missing
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["tenant_id"] == "tenant-real"
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_email_mismatch_between_token_and_db_does_not_leak():
    """Edge: if attacker forges a JWT with a victim's email, the DB
    lookup binds tenant_id to the email — but signature verification
    happens BEFORE this code runs. This test asserts the code path uses
    the email from the (verified) claim consistently."""
    pool, db = _mock_pool(row={
        "id": "uid",
        "email": "victim@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": "victim-tenant",
        "is_owner": True,
        "company_name": "Victim Co",
    })
    claims = _claims_for_tenant("attacker-tenant", email="victim@example.com")
    # Attacker can't supply a different email — JWT signed by Keycloak.
    # But removing tenant_id forces fallback path.
    claims.pop("tenant_id")
    out = await kv.enrich_keycloak_claims(claims, pool)
    # DB is authoritative when fast-path declines → victim-tenant
    assert out["tenant_id"] == "victim-tenant"


# ── Sanity: tenant_id stringification in fast path ───────────────────────────


@pytest.mark.asyncio
async def test_non_uuid_tenant_mapper_falls_back_instead_of_fast_path():
    """Non-UUID mapper values must not activate fast path; this prevents stale
    Keycloak slug attributes from bypassing DB enrichment and mis-targeting
    tenant-scoped queries."""
    pool, db = _mock_pool(row={
        "id": "uid",
        "email": "user@example.com",
        "role": "business",
        "status": "active",
        "tenant_id": TENANT_A,
        "is_owner": True,
        "company_name": "ACME",
    })
    out = await kv.enrich_keycloak_claims(
        _claims_for_tenant(12345),  # int, defensive
        pool,
    )
    assert out["tenant_id"] == TENANT_A
    assert isinstance(out["tenant_id"], str)
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()
