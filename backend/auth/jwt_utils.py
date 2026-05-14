"""Auth dependencies — Keycloak-only post Phase 4b cutover (ADR-005).

Backwards-compatible module name `jwt_utils.py` kept to avoid sprawling import
refactor across routers. Functions:

- `get_current_user`: Validates Keycloak JWT (RS256, JWKs from realm).
  PG profile lookup + JIT provisioning happens inside `keycloak_validator`.
- `require_business_owner / require_provider_owner / require_active_user`:
  Role/status guards consuming the dict returned by `get_current_user`.
- `require_admin`: Currently checks Keycloak realm role `platform_admin` from
  the same JWT. (Phase 4b: replaced dual-path JWT+opaque-session fallback.)

Legacy artifacts removed in Phase 4b (2026-05-14):
- create_access_token / create_refresh_token / decode_token / decode_refresh_token
  → no longer issuing manual HS256 tokens (Keycloak owns issuance).
- _validate_old_admin_session → opaque admin session file. Admin now uses
  Keycloak realm role.
- AUTH_KEYCLOAK_ENABLED flag → no longer feature-gated, Keycloak is the only path.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


_bearer = HTTPBearer(auto_error=False)


def decode_token(token: str) -> dict:
    """Backwards-compat shim — validates Keycloak JWT, returns claims dict.

    Used by file-download URL signing flows (document_router, certificate_router,
    audit_router) that need to authenticate via `?token=` query param. Post Phase
    4b, only Keycloak tokens are accepted.
    """
    from auth import keycloak_validator

    if not keycloak_validator.looks_like_keycloak_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    try:
        return keycloak_validator.validate_keycloak_token(token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid or expired token: {e}")


async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Resolve current user from Keycloak JWT. Returns claims dict with keys:
    sub, email, role, status, is_owner, tenant_id, _keycloak=True.
    """
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    from auth import keycloak_validator
    from auth.db import get_pool

    token = creds.credentials
    if not keycloak_validator.looks_like_keycloak_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

    claims = keycloak_validator.validate_keycloak_token(token)
    return await keycloak_validator.enrich_keycloak_claims(claims, get_pool())


def require_business_owner(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "business" or not user.get("is_owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business owner access required")
    return user


def require_provider_owner(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "provider" or not user.get("is_owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider owner access required")
    return user


def require_active_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not active")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Admin = Keycloak realm role `platform_admin` (assigned via Keycloak admin
    console or aminra-admin-cli service account). Post Phase 4b cutover the
    opaque /admin/login session fallback was removed.
    """
    realm_roles = user.get("realm_roles") or []
    if "platform_admin" not in realm_roles and user.get("role") != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
