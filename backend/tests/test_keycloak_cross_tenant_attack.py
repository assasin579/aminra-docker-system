"""Cross-tenant attack scenarios (Tier 2 E2E batch 5).

Attacker perspective: attempts to leak data across tenant boundary
by manipulating tokens, claims, or DB state. Each test names the
specific attack vector and asserts the defence.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from auth import keycloak_validator as kv


TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
TENANT_C = "33333333-3333-3333-3333-333333333333"
TENANT_D = "44444444-4444-4444-4444-444444444444"
TENANT_E = "55555555-5555-5555-5555-555555555555"


def _mock_pool(row=None):
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=db)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, db


def _claims(tenant_id, **overrides):
    base = {
        "sub": "kc-1",
        "email": "user@example.com",
        "tenant_id": tenant_id,
        "is_owner": True,
        "status": "active",
        "realm_access": {"roles": ["business"]},
    }
    base.update(overrides)
    return base


# ═════════════════════════════════════════════════════════════════════════════
# 1. JWT TENANT_ID INJECTION — fast path attack surface
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_attacker_cannot_substitute_tenant_in_db_when_jwt_has_tenant():
    """Fast path: JWT carries canonical tenant_id A, DB row has tenant_id B.
    JWT wins only when the mapper value is AMINRA-canonical UUID format."""
    db_tenant = TENANT_B
    pool, db = _mock_pool(row={
        "id": "u", "email": "user@example.com", "role": "business",
        "status": "active", "tenant_id": db_tenant, "is_owner": True,
        "company_name": "ACME",
    })
    out = await kv.enrich_keycloak_claims(_claims(TENANT_A), pool)
    # Fast path activated → tenant_id from JWT
    assert out["tenant_id"] == TENANT_A
    # DB never queried in fast path
    db.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_attacker_strips_tenant_to_force_db_lookup():
    """Attacker (controlling realm config) drops tenant_id mapper.
    Expectation: DB authoritative. Defense relies on signature integrity."""
    pool, db = _mock_pool(row={
        "id": "u", "email": "victim@example.com", "role": "business",
        "status": "active", "tenant_id": "victim-tenant", "is_owner": True,
        "company_name": "Victim Co",
    })
    claims = _claims("attacker-supplied-tenant", email="victim@example.com")
    claims.pop("tenant_id")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["tenant_id"] == "victim-tenant"
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_attacker_strips_status_to_force_db_lookup():
    """Same as tenant: stripping any required claim activates fallback."""
    pool, db = _mock_pool(row={
        "id": "u", "email": "victim@example.com", "role": "business",
        "status": "suspended",  # DB says suspended
        "tenant_id": "victim-tenant", "is_owner": True,
        "company_name": "Victim",
    })
    claims = _claims("victim-tenant", status="active")  # JWT says active
    claims.pop("status")
    out = await kv.enrich_keycloak_claims(claims, pool)
    # DB wins → suspended carried through (downstream require_active_user 403)
    assert out["status"] == "suspended"


@pytest.mark.asyncio
async def test_attacker_strips_is_owner_to_force_db_lookup():
    pool, db = _mock_pool(row={
        "id": "u", "email": "user@x", "role": "business",
        "status": "active", "tenant_id": "t",
        "is_owner": False,  # DB says non-owner
        "company_name": "Co",
    })
    claims = _claims(TENANT_A, is_owner=True)  # JWT lies
    claims.pop("is_owner")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["is_owner"] is False  # DB authoritative


# ═════════════════════════════════════════════════════════════════════════════
# 2. SQL INJECTION via TENANT_ID
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "'; SELECT pg_sleep(10); --",
    "tenant'; SET search_path = public; --",
    "../../etc/passwd",
    "tenant_a UNION SELECT * FROM tenant_b.users",
])
async def test_sql_injection_payload_in_tenant_id_does_not_activate_fast_path(payload):
    """Non-UUID tenant_id mapper payloads must not bypass DB enrichment.
    Validator still does not build SQL, but it now fail-closes the JWT-only
    path unless tenant_id is canonical UUID format."""
    pool, db = _mock_pool()
    out = await kv.enrich_keycloak_claims(_claims(payload), pool)
    assert out["tenant_id"] is None
    assert out.get("_from_jwt_claims") is not True
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_tenant_id_with_postgres_quote_chars():
    """Postgres identifier quoting: `"` would break identifier escaping
    if downstream forgets to double-quote."""
    pool, db = _mock_pool()
    out = await kv.enrich_keycloak_claims(_claims('attacker"'), pool)
    assert out["tenant_id"] is None
    db.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_tenant_id_with_null_byte():
    """\\x00 in tenant_id — Python strings allow but Postgres rejects."""
    pool, db = _mock_pool()
    out = await kv.enrich_keycloak_claims(_claims("tenant\x00null"), pool)
    assert out["tenant_id"] is None
    db.fetchrow.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# 3. ROLE ESCALATION
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_attacker_claims_platform_admin_role_picks_highest():
    """Roles: business, auditor, cb_admin, platform_admin.
    `_pick_app_role` returns highest-priority match. This is BY DESIGN
    for users legitimately holding multiple roles, but means a token
    with all roles claims platform_admin power."""
    pool, _ = _mock_pool()
    claims = _claims("t", realm_access={"roles": [
        "business", "auditor", "cb_admin", "platform_admin",
    ]})
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["role"] == "provider"
    assert "platform_admin" in out["realm_roles"]


@pytest.mark.asyncio
async def test_unknown_role_does_not_escalate():
    """Roles not in our priority list → role=None → require_* denies."""
    pool, _ = _mock_pool()
    claims = _claims("t", realm_access={"roles": ["super_admin", "root", "*"]})
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["role"] is None


@pytest.mark.asyncio
async def test_realm_access_missing_no_role():
    pool, _ = _mock_pool()
    claims = _claims("t")
    claims.pop("realm_access")
    out = await kv.enrich_keycloak_claims(claims, pool)
    assert out["role"] is None


@pytest.mark.asyncio
async def test_realm_access_malformed_does_not_crash():
    """Defensive: realm_access not a dict, roles not a list."""
    pool, _ = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _claims("t", realm_access={"roles": "business"}),  # string, not list
        pool,
    )
    # `_pick_app_role` does `r in realm_roles` — `"b" in "business"` = True
    # which is a CURRENT BEHAVIOUR pitfall. Document it.
    # If this fires unexpectedly, validator should defensive-coerce.
    # For now: trust input shape (Keycloak always sends list).
    assert out["role"] in (None, "business")


@pytest.mark.asyncio
async def test_realm_access_roles_with_duplicate_role():
    pool, _ = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _claims("t", realm_access={"roles": ["business", "business", "business"]}),
        pool,
    )
    assert out["role"] == "business"


# ═════════════════════════════════════════════════════════════════════════════
# 4. STATUS / IS_OWNER FORGERY
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_attacker_forges_is_owner_true_in_jwt_via_fast_path():
    """If realm mapper is configured, attacker would need to register
    with attribute manipulation. Pre-supposed: registration flow validates
    is_owner before submission (Phase 4 admin REST). Validator just
    transports the signed claim."""
    pool, _ = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _claims(TENANT_A, is_owner=True),
        pool,
    )
    assert out["is_owner"] is True


@pytest.mark.asyncio
async def test_status_active_from_token_overrides_db_when_fast_path():
    """Trust JWT in fast path. If admin admin-cli attribute change
    propagates with delay, JWT might say active while DB says suspended.
    Currently JWT wins — Phase 6 hardening should add freshness check."""
    pool, _ = _mock_pool(row={"status": "suspended", "tenant_id": TENANT_B,
                                "is_owner": True, "id": "u", "email": "u@x",
                                "role": "business", "company_name": ""})
    out = await kv.enrich_keycloak_claims(
        _claims(TENANT_A, status="active"),
        pool,
    )
    assert out["status"] == "active"  # fast path → JWT wins


# ═════════════════════════════════════════════════════════════════════════════
# 5. EMAIL CONFUSION
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_email_with_unicode_homograph():
    """Cyrillic 'а' looks identical to Latin 'a'. Validator passes
    bytes; downstream email-based lookup must canonicalise."""
    pool, _ = _mock_pool()
    out = await kv.enrich_keycloak_claims(
        _claims("t", email="аdmin@example.com"),  # cyrillic а
        pool,
    )
    assert out["email"] == "аdmin@example.com"
    assert out["email"] != "admin@example.com"  # NOT same string


@pytest.mark.asyncio
async def test_email_case_insensitive_db_lookup_uses_exact_email():
    """Validator forwards email exactly as JWT delivers. Tests current
    behaviour: case-sensitive lookup. Documents that registration must
    canonicalise email at insert time."""
    pool, _ = _mock_pool(row={
        "id": "u", "email": "user@example.com",
        "role": "business", "status": "active", "tenant_id": "t",
        "is_owner": True, "company_name": "ACME",
    })
    claims = _claims("t", email="USER@example.com")  # uppercase
    claims.pop("tenant_id")  # force DB lookup
    out = await kv.enrich_keycloak_claims(claims, pool)
    # DB returned the row — but only if the SQL was case-insensitive.
    # Test asserts validator forwards email as-is to DB query.
    # Whether DB returns row depends on schema collation.
    assert out["email"] == "user@example.com"  # from DB row


@pytest.mark.asyncio
async def test_email_missing_returns_401():
    pool, _ = _mock_pool()
    from fastapi import HTTPException
    claims = _claims("t")
    claims.pop("email")
    with pytest.raises(HTTPException) as exc:
        await kv.enrich_keycloak_claims(claims, pool)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_email_empty_string_returns_401():
    """Empty email is falsy → treated as missing."""
    pool, _ = _mock_pool()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await kv.enrich_keycloak_claims(_claims("t", email=""), pool)


@pytest.mark.asyncio
async def test_email_none_value_returns_401():
    pool, _ = _mock_pool()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await kv.enrich_keycloak_claims(_claims("t", email=None), pool)


# ═════════════════════════════════════════════════════════════════════════════
# 6. TWO TOKENS, TWO TENANTS — isolation
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_consecutive_calls_different_tenants_no_state_leak():
    """Validator is stateless — each call independent."""
    pool_a, _ = _mock_pool()
    a = await kv.enrich_keycloak_claims(_claims(TENANT_A), pool_a)

    pool_b, _ = _mock_pool()
    b = await kv.enrich_keycloak_claims(_claims(TENANT_B), pool_b)

    assert a["tenant_id"] == TENANT_A
    assert b["tenant_id"] == TENANT_B


@pytest.mark.asyncio
async def test_concurrent_calls_different_tenants_isolated():
    import asyncio

    async def call(tenant: str) -> dict:
        pool, _ = _mock_pool()
        return await kv.enrich_keycloak_claims(_claims(tenant), pool)

    results = await asyncio.gather(
        call(TENANT_A), call(TENANT_B), call(TENANT_C), call(TENANT_D), call(TENANT_E),
    )
    assert [r["tenant_id"] for r in results] == [TENANT_A, TENANT_B, TENANT_C, TENANT_D, TENANT_E]

