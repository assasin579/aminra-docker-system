from __future__ import annotations

from fastapi import HTTPException, status


def require_platform_admin_capability(user: dict) -> dict:
    """Require a verified Keycloak platform_admin realm capability.

    `role` is intentionally ignored: Keycloak maps platform_admin into the
    provider DB role, and accepting normalized roles risks privilege confusion.
    """
    roles = user.get("realm_roles")
    if user.get("_keycloak") is not True or not isinstance(roles, (list, tuple, set)) or "platform_admin" not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verified platform_admin capability required")
    if not user.get("sub"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verified identity subject required")
    return user
