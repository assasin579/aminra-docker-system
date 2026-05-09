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
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "aminra")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "aminra-backend")

_JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
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

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[header.get("alg", "RS256")],
            audience=KEYCLOAK_AUDIENCE,
            issuer=_ISSUER,
        )
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

    return claims


_ROLE_PRIORITY = ("platform_admin", "cb_admin", "auditor", "business")


def _pick_app_role(realm_roles: list[str]) -> Optional[str]:
    for r in _ROLE_PRIORITY:
        if r in realm_roles:
            return r
    return None


async def enrich_keycloak_claims(claims: dict, db_pool) -> dict:
    """Map Keycloak JWT claims → existing app user dict shape.

    DB is authoritative for tenant_id / is_owner / status during the
    migration window. Email is the join key.
    """
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    keycloak_role = _pick_app_role(realm_roles)

    async with db_pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT id, email, role, status, tenant_id, is_owner, company_name "
            "FROM users WHERE email = $1",
            email,
        )

    if not row:
        # Keycloak-authenticated user has no DB record yet (post Phase 4
        # re-register flow). Return minimal shape; downstream require_*
        # guards will reject as expected.
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
        # Realm role drift vs DB — log but trust DB during migration.
        # Phase 4 sync will reconcile. Avoid raising to not break login.
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
