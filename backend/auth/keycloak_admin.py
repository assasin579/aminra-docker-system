"""Keycloak admin REST API helper (ADR-005 Phase 4).

Used by the registration flow + admin tooling to create users in Keycloak
with the right user attributes (tenant_id, is_owner, status) so that the
Phase 3b token mappers populate the JWT claims correctly.

Auth: client_credentials grant on the `aminra-admin-cli` client (created
by scripts/keycloak-bootstrap.sh §4c). Token cached in-process per TTL.

Phase 4 scope is BE-side helper + tests with mocked HTTP. Live wiring
into the registration endpoint happens during Phase 2 FE migration.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

import httpx
from fastapi import HTTPException, status

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "aminra")
ADMIN_CLI_CLIENT_ID = os.getenv("KEYCLOAK_ADMIN_CLI_CLIENT_ID", "aminra-admin-cli")
ADMIN_CLI_SECRET = os.getenv("KEYCLOAK_ADMIN_CLI_SECRET", "")

_TOKEN_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
_ADMIN_BASE = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"

_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}
_token_lock = threading.Lock()
# Refresh 30s before expiry to avoid race with a request straddling the boundary.
_TOKEN_REFRESH_SKEW = 30


class KeycloakAdminError(HTTPException):
    """Raised when admin API returns a non-2xx response."""


def _get_admin_token() -> str:
    if not ADMIN_CLI_SECRET:
        raise KeycloakAdminError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="KEYCLOAK_ADMIN_CLI_SECRET not configured",
        )
    now = time.time()
    cached_token = _token_cache.get("token")
    cached_exp = _token_cache.get("expires_at", 0.0)
    if cached_token and now < (cached_exp - _TOKEN_REFRESH_SKEW):
        return cached_token  # type: ignore[return-value]

    with _token_lock:
        cached_token = _token_cache.get("token")
        cached_exp = _token_cache.get("expires_at", 0.0)
        if cached_token and now < (cached_exp - _TOKEN_REFRESH_SKEW):
            return cached_token  # type: ignore[return-value]

        resp = httpx.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": ADMIN_CLI_CLIENT_ID,
                "client_secret": ADMIN_CLI_SECRET,
            },
            timeout=5.0,
        )
        if resp.status_code != 200:
            raise KeycloakAdminError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Admin token fetch failed: {resp.status_code}",
            )
        data = resp.json()
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 60))
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + expires_in
        return token


def _admin_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_admin_token()}",
        "Content-Type": "application/json",
    }


def _user_payload(
    email: str,
    tenant_id: Optional[str],
    is_owner: bool,
    user_status: str,
    company_name: Optional[str] = None,
    email_verified: bool = False,
) -> dict:
    """Build POST /users payload. Keycloak expects attributes as
    `dict[str, list[str]]` — every value is a list of strings even when
    semantically scalar."""
    attributes: dict[str, list[str]] = {
        "is_owner": ["true" if is_owner else "false"],
        "status": [user_status],
    }
    if tenant_id is not None:
        attributes["tenant_id"] = [str(tenant_id)]
    # The realm profile (KC user-profile config) marks firstName + lastName as
    # required for the `user` role; without both, password grants fail with
    # `Account is not fully set up`. AMINRA accounts are companies, not
    # persons — fill firstName with `company_name` and lastName with a stable
    # placeholder so KC validation passes and admins still see a recognisable
    # label in the KC console.
    payload: dict = {
        "username": email,
        "email": email,
        "enabled": True,
        "emailVerified": email_verified,
        "attributes": attributes,
        "requiredActions": [] if email_verified else ["VERIFY_EMAIL"],
        "firstName": company_name or email.split("@", 1)[0],
        "lastName": "Account",
    }
    return payload


def create_user(
    *,
    email: str,
    password: str,
    role: str,
    tenant_id: Optional[str] = None,
    is_owner: bool = True,
    user_status: str = "active",
    company_name: Optional[str] = None,
    require_mfa: bool = False,
    email_verified: bool = False,
) -> str:
    """Create a Keycloak user + set initial password + assign realm role.

    Returns the new user's Keycloak UUID.

    Raises KeycloakAdminError on any step failure. Caller is responsible
    for compensating (e.g. delete partial DB row) if create succeeds but
    password/role assignment fails.

    `email_verified=True` skips the VERIFY_EMAIL required action — use when
    the creator vouches for the identity (admin-created accounts).
    """
    payload = _user_payload(
        email, tenant_id, is_owner, user_status, company_name,
        email_verified=email_verified,
    )
    if require_mfa:
        payload["requiredActions"].append("CONFIGURE_TOTP")

    resp = httpx.post(
        f"{_ADMIN_BASE}/users",
        headers=_admin_headers(),
        json=payload,
        timeout=10.0,
    )
    if resp.status_code != 201:
        raise KeycloakAdminError(
            status_code=status.HTTP_400_BAD_REQUEST if resp.status_code == 409
            else status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak create_user failed ({resp.status_code}): {resp.text[:200]}",
        )
    location = resp.headers.get("Location", "")
    if not location:
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Keycloak create_user missing Location header",
        )
    user_id = location.rsplit("/", 1)[-1]
    if not user_id:
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak create_user Location header has empty user id: {location!r}",
        )

    pw_resp = httpx.put(
        f"{_ADMIN_BASE}/users/{user_id}/reset-password",
        headers=_admin_headers(),
        json={"type": "password", "value": password, "temporary": False},
        timeout=10.0,
    )
    if pw_resp.status_code not in (200, 204):
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak reset_password failed ({pw_resp.status_code})",
        )

    role_resp = httpx.get(
        f"{_ADMIN_BASE}/roles/{role}",
        headers=_admin_headers(),
        timeout=5.0,
    )
    if role_resp.status_code != 200:
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak get_role({role}) failed ({role_resp.status_code})",
        )
    role_obj = role_resp.json()

    grant_resp = httpx.post(
        f"{_ADMIN_BASE}/users/{user_id}/role-mappings/realm",
        headers=_admin_headers(),
        json=[{"id": role_obj["id"], "name": role_obj["name"]}],
        timeout=5.0,
    )
    if grant_resp.status_code not in (200, 204):
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak grant_role failed ({grant_resp.status_code})",
        )

    return user_id


def set_required_actions(user_id: str, actions: list[str]) -> None:
    """Replace the user's requiredActions list.

    Used to force VERIFY_EMAIL or CONFIGURE_TOTP at next login.
    """
    resp = httpx.put(
        f"{_ADMIN_BASE}/users/{user_id}",
        headers=_admin_headers(),
        json={"requiredActions": actions},
        timeout=5.0,
    )
    if resp.status_code not in (200, 204):
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak set_required_actions failed ({resp.status_code})",
        )


def delete_user(user_id: str) -> None:
    """Delete a Keycloak user by UUID. Idempotent — a 404 is treated as success
    so callers can safely run this after a partial deletion."""
    resp = httpx.delete(
        f"{_ADMIN_BASE}/users/{user_id}",
        headers=_admin_headers(),
        timeout=10.0,
    )
    if resp.status_code in (204, 404):
        return
    raise KeycloakAdminError(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Keycloak delete_user failed ({resp.status_code}): {resp.text[:200]}",
    )


def find_user_by_email(email: str) -> Optional[str]:
    """Look up a Keycloak user UUID by email (exact match). Returns None if not found."""
    resp = httpx.get(
        f"{_ADMIN_BASE}/users",
        params={"email": email, "exact": "true"},
        headers=_admin_headers(),
        timeout=5.0,
    )
    if resp.status_code != 200:
        raise KeycloakAdminError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak find_user_by_email failed ({resp.status_code})",
        )
    users = resp.json()
    if not users:
        return None
    return users[0]["id"]
