"""Verify Keycloak signatures, live realm authority and current application scope.

Signing keys are cached independently of principals. Mutable application tenant,
owner, role and status are loaded from the database; mapper snapshots never
bypass current application authority.
"""

from __future__ import annotations

import json
import os
import time
import threading
from typing import Optional

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import PyJWTError
from jwt.algorithms import RSAAlgorithm

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
    except PyJWTError:
        return False
    return header.get("alg") in ("RS256", "RS384", "RS512") and bool(header.get("kid"))


def validate_keycloak_token(token: str) -> dict:
    """Verify signature, issuer, audience, expiry. Return raw claims.

    Raises HTTPException 401 on any validation failure.
    """
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as e:
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
    if key.get("kty") != "RSA":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported signing key type",
        )
    key_alg = key.get("alg")
    if key_alg and key_alg != alg:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token alg does not match JWK alg",
        )
    try:
        verification_key = RSAAlgorithm.from_jwk(json.dumps(key))
        claims = jwt.decode(
            token,
            verification_key,  # type: ignore[arg-type]
            algorithms=[alg],
            audience=KEYCLOAK_AUDIENCE,
            issuer=_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    except Exception as e:
        # PyJWT/cryptography can raise TypeError or ValueError on malformed
        # numeric claims or unsupported key shapes. We MUST surface those as
        # 401, not 500 — otherwise an attacker can DoS or fingerprint by
        # triggering server errors.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token rejected: {type(e).__name__}",
        )

    if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject claim",
        )

    return claims


_ROLE_PRIORITY = ("platform_admin", "cb_admin", "auditor", "business")

# Keycloak realm role names → AMINRA `users.role` enum values.
# AMINRA PG `users.role` currently has only `business` / `provider`; platform
# admin authority is represented by the Keycloak `platform_admin` realm role
# and checked via `realm_roles` (see `require_admin`). Do not invent an `admin`
# app role at the auth boundary: it creates noisy false "role drift" warnings
# and breaks routers that enrich from the DB row.
_KC_TO_PG_ROLE = {
    "platform_admin": "provider",
    "cb_admin": "provider",
    "auditor": "provider",   # auditor is a sub-user under a provider org;
                              # is_owner distinguishes from cb_admin downstream
    "business": "business",
}


def _pick_app_role(realm_roles: list[str]) -> Optional[str]:
    """Pick the most-privileged KC realm role on the token (KC vocabulary)."""
    for r in _ROLE_PRIORITY:
        if r in realm_roles:
            return r
    return None


def _normalize_role_to_pg(kc_role: Optional[str]) -> Optional[str]:
    """Translate KC realm role → AMINRA PG `users.role` enum value.
    Returns None when no mapping exists (caller decides whether to 401)."""
    if kc_role is None:
        return None
    return _KC_TO_PG_ROLE.get(kc_role, kc_role)


async def enrich_keycloak_claims(claims: dict, db_pool) -> dict:
    """Map Keycloak JWT claims → existing app user dict shape.

    The database projection is authoritative for current tenant, owner, role
    and account status on every request. Token mapper snapshots cannot
    restore revoked application authority. Missing rows stay unscoped until
    the explicit registration/profile reconciliation gate provisions them.
    """
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    keycloak_role = _pick_app_role(realm_roles)
    if not keycloak_role:
        raise HTTPException(status_code=401, detail="Application role required")

    async with db_pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT id, email, keycloak_sub, role, status, tenant_id, is_owner, company_name "
            "FROM users WHERE lower(email) = $1",
            email.lower(),
        )

    if not row:
        is_owner_raw = claims.get("is_owner")
        is_owner = is_owner_raw is True or str(is_owner_raw).lower() == "true"
        return {
            "sub": claims.get("sub"),
            "keycloak_sub": claims.get("sub"),
            "email": email,
            "role": _normalize_role_to_pg(keycloak_role),
            "is_owner": is_owner,
            "status": claims.get("status") or "pending",
            "tenant_id": None,
            "realm_roles": realm_roles,
            "company_name": claims.get("company_name"),
            "_keycloak": True,
        }

    # A verified email never transfers an already-bound application identity.
    # Mapper claims are snapshots, so mutable authority always comes from DB.
    if row["keycloak_sub"] and str(row["keycloak_sub"]) != str(claims.get("sub")):
        raise HTTPException(status_code=401, detail="Identity binding mismatch")
    if row["status"] not in ("active", "pending"):
        raise HTTPException(status_code=403, detail="Account not active")

    db_role = row["role"]
    kc_role_normalized = _normalize_role_to_pg(keycloak_role)
    if kc_role_normalized and db_role and kc_role_normalized != db_role:
        import logging
        logging.getLogger(__name__).warning(
            "Role drift for %s: keycloak=%s (=%s) db=%s — using db",
            email, keycloak_role, kc_role_normalized, db_role,
        )

    return {
        "sub": str(row["id"]),  # legacy app-id shape kept until all routers use app_user_id
        "keycloak_sub": claims.get("sub"),
        "app_user_id": str(row["id"]),
        "email": row["email"],
        "role": db_role,
        "is_owner": bool(row["is_owner"]),
        "status": row["status"],
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
        "realm_roles": realm_roles,
        "company_name": row["company_name"],
        "_keycloak": True,
    }


async def authenticate_keycloak_token(token: str, db_pool) -> dict:
    """Verify token, current identity-provider authority and current DB scope."""
    from .live_authority import current_realm_roles
    claims = validate_keycloak_token(token)
    roles = await current_realm_roles(token, claims)
    current = {**claims, 'realm_access': {**(claims.get('realm_access') or {}), 'roles': list(roles)}}
    return await enrich_keycloak_claims(current, db_pool)
