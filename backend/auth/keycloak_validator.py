"""Keycloak JWT validation for dual-auth migration (ADR-005 Phase 3a).

When AUTH_KEYCLOAK_ENABLED=true, tokens issued by Keycloak realm `aminra`
are validated alongside the legacy HS256 tokens. JWKs are fetched once
per `_JWKS_TTL` and cached in-process.

Claim shape returned by `validate_keycloak_token` is the RAW Keycloak JWT
payload. Enrichment to the existing app `user` dict shape (with role,
tenant_id, is_owner, status) is done in `enrich_keycloak_claims` via a
DB lookup by email — DB stays authoritative for app-domain fields during
the migration. Phase 4 will add Keycloak custom token mappers.
"""

from __future__ import annotations

import os
import time
import threading
from typing import Optional

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.utils import base64url_decode

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
# When backend runs inside docker network but token issuer is the public
# URL (browser-facing), JWKs fetch must use the internal route for
# reachability while issuer comparison uses the public URL.
KEYCLOAK_INTERNAL_URL = os.getenv(
    "KEYCLOAK_INTERNAL_URL", KEYCLOAK_URL,
).rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "aminra")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "aminra-backend")

_JWKS_URL = f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
_ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
_JWKS_TTL = 3600

_jwks_cache: dict[str, object] = {"keys": None, "fetched_at": 0.0}
_jwks_lock = threading.Lock()


def _fetch_jwks(force: bool = False) -> list[dict]:
    now = time.time()
    keys = _jwks_cache.get("keys")
    if not force and keys and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL:
        return keys  # type: ignore[return-value]
    with _jwks_lock:
        keys = _jwks_cache.get("keys")
        if not force and keys and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL:
            return keys  # type: ignore[return-value]
        resp = httpx.get(_JWKS_URL, timeout=5.0)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = now
        return keys


def _key_for_kid(kid: str, allow_refresh: bool = True) -> Optional[dict]:
    for k in _fetch_jwks():
        if k.get("kid") == kid:
            return k
    if allow_refresh:
        for k in _fetch_jwks(force=True):
            if k.get("kid") == kid:
                return k
    return None


def looks_like_keycloak_token(token: str) -> bool:
    """Cheap kid-based pre-check; avoids a full decode when we know the
    token is HS256-issued by the legacy path."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return False
    return header.get("alg") in ("RS256", "RS384", "RS512") and bool(header.get("kid"))


def validate_keycloak_token(token: str) -> dict:
    """Verify signature, issuer, audience, expiry. Return raw claims.

    Raises HTTPException 401 on any validation failure.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Malformed token: {e}")

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing kid")

    key = _key_for_kid(kid)
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key")

    alg = header.get("alg", "RS256")
    if alg not in ("RS256", "RS384", "RS512"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Disallowed alg: {alg}",
        )
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=KEYCLOAK_AUDIENCE,
            issuer=_ISSUER,
        )
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    except Exception as e:
        # python-jose can raise TypeError on malformed numeric claims
        # (exp/nbf/iat as string/list/dict) and JWKError on unsupported
        # key shapes. We MUST surface those as 401, not 500 — otherwise
        # an attacker can DoS or fingerprint by triggering server errors.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token rejected: {type(e).__name__}",
        )

    return claims


_ROLE_PRIORITY = ("platform_admin", "cb_admin", "auditor", "business")


def _pick_app_role(realm_roles: list[str]) -> Optional[str]:
    for r in _ROLE_PRIORITY:
        if r in realm_roles:
            return r
    return None


_FAST_PATH_REQUIRED = ("email", "tenant_id", "is_owner", "status")


def _has_full_mapper_claims(claims: dict) -> bool:
    """True when Keycloak token mappers populated all app-domain claims AND
    the values are AMINRA-canonical (UUID for tenant_id, not a slug).

    Phase 3b enabled this for /auth/me perf; but the realm currently stores
    `tenant_id` user-attributes as slugs (e.g. "demo-biz") and the fast
    path silently fed those slugs into `WHERE tenant_id = $1` downstream,
    breaking the whole stack. Until KC attributes are migrated to UUIDs,
    only trust the fast path when tenant_id parses as a UUID.
    """
    import uuid as _uuid

    if not all(claims.get(k) is not None for k in _FAST_PATH_REQUIRED):
        return False
    try:
        _uuid.UUID(str(claims["tenant_id"]))
        return True
    except (ValueError, TypeError):
        return False


def _claims_to_user_via_jwt(claims: dict) -> dict:
    """Build app user dict from JWT claims alone (mapper fast path).

    `tenant_id` is normalised to string; `is_owner` to bool. Mapper jsonType
    `boolean` may serialise the value as a string in some Keycloak versions
    so coerce defensively.
    """
    is_owner_raw = claims["is_owner"]
    is_owner = is_owner_raw is True or str(is_owner_raw).lower() == "true"

    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    return {
        "sub": claims.get("sub"),
        "email": claims["email"],
        "role": _pick_app_role(realm_roles),
        "is_owner": is_owner,
        "status": claims["status"],
        "tenant_id": str(claims["tenant_id"]),
        "_keycloak": True,
        "_from_jwt_claims": True,
    }


async def enrich_keycloak_claims(claims: dict, db_pool) -> dict:
    """Map Keycloak JWT claims → existing app user dict shape.

    Fast path (Phase 3b): when realm has the user-attribute mappers, the
    JWT carries `tenant_id`/`is_owner`/`status` directly and we return
    without touching the DB.

    Fallback path (Phase 3a): DB lookup by email is authoritative. Used
    for users created before mappers were configured, or when mappers
    aren't yet active in the realm.
    """
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    if _has_full_mapper_claims(claims):
        return _claims_to_user_via_jwt(claims)

    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    keycloak_role = _pick_app_role(realm_roles)

    async with db_pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT id, email, role, status, tenant_id, is_owner, company_name "
            "FROM users WHERE email = $1",
            email,
        )

    if not row:
        return {
            "sub": claims.get("sub"),
            "email": email,
            "role": keycloak_role,
            "is_owner": False,
            "status": "pending",
            "tenant_id": None,
            "_keycloak": True,
        }

    db_role = row["role"]
    if keycloak_role and db_role and keycloak_role != db_role:
        import logging
        logging.getLogger(__name__).warning(
            "Role drift for %s: keycloak=%s db=%s — using db",
            email, keycloak_role, db_role,
        )

    return {
        "sub": str(row["id"]),
        "email": row["email"],
        "role": db_role,
        "is_owner": bool(row["is_owner"]),
        "status": row["status"],
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
        "company_name": row["company_name"],
        "_keycloak": True,
    }
