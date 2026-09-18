"""Canonical AMINRA identity resolution and Keycloak ↔ app projection sync.

Keycloak owns identity/account state. AMINRA's `users` row is an application
profile projection keyed by `users.id`; Keycloak `sub` must never be used as an
app foreign key. This module is the single place where token claims are mapped
back to the canonical AMINRA user row.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status


_ALLOWED_APP_ROLES = {"business", "provider"}


def _parse_uuid(value) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _bool_claim(value, default: bool = False) -> bool:
    if value is None:
        return default
    if value is True or value is False:
        return bool(value)
    return str(value).lower() in {"1", "true", "yes", "y"}


def _app_role_from_claims(user: dict) -> str:
    role = user.get("role") or "business"
    if role == "platform_admin":
        return "provider"
    return role if role in _ALLOWED_APP_ROLES else "business"


def _keycloak_sub_from_user(user: dict) -> Optional[uuid.UUID]:
    # `keycloak_sub` is added by keycloak_validator for fallback-enriched users.
    # If absent, a Keycloak-token user still carries the Keycloak UUID in `sub`.
    return _parse_uuid(user.get("keycloak_sub") or user.get("sub"))


async def get_or_reconcile_user_from_keycloak_claims(user: dict, db):
    """Return the canonical AMINRA `users` row for a Keycloak-authenticated user.

    Safe repairs applied automatically:
      - link/update `users.keycloak_sub` when exact email uniquely identifies row
      - mirror safe account fields from Keycloak claims (`status`, `is_owner`)
      - repair owner invariant: owner rows must have `tenant_id = id`

    Ambiguous conflicts fail closed with 409 rather than returning a wrong
    profile. Destructive repairs are deliberately not attempted here.
    """
    if not user.get("_keycloak"):
        app_id = _parse_uuid(user.get("app_user_id") or user.get("sub"))
        if not app_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid app user identity")
        row = await db.fetchrow("SELECT * FROM users WHERE id = $1", app_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return row

    email = (user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing email claim")
    kc_sub = _keycloak_sub_from_user(user)
    if not kc_sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing valid Keycloak subject")

    row_by_sub = await db.fetchrow("SELECT * FROM users WHERE keycloak_sub = $1", kc_sub)
    row_by_email = await db.fetchrow("SELECT * FROM users WHERE lower(email) = $1", email)

    if row_by_sub and row_by_email and row_by_sub["id"] != row_by_email["id"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "identity_state_conflict",
                "message": "Keycloak subject and email map to different AMINRA users",
                "identity_lifecycle_owner": "keycloak",
            },
        )

    row = row_by_sub or row_by_email
    role = _app_role_from_claims(user)
    status_claim = user.get("status") or "active"
    is_owner = _bool_claim(user.get("is_owner"), default=True)

    if not row:
        tenant_uuid = _parse_uuid(user.get("tenant_id"))
        row = await db.fetchrow(
            """
            INSERT INTO users (email, keycloak_sub, role, company_name,
                               status, is_owner, tenant_id)
            VALUES ($1, $2, $3::user_role, $4, $5::user_status, $6, $7)
            RETURNING *
            """,
            email,
            kc_sub,
            role,
            user.get("company_name") or email.split("@")[0],
            status_claim,
            is_owner,
            tenant_uuid,
        )
    else:
        updates: list[str] = []
        values = []

        if row.get("keycloak_sub") != kc_sub:
            updates.append(f"keycloak_sub = ${len(values) + 1}")
            values.append(kc_sub)
        if status_claim and row.get("status") != status_claim:
            updates.append(f"status = ${len(values) + 1}::user_status")
            values.append(status_claim)
        if bool(row.get("is_owner")) != is_owner:
            updates.append(f"is_owner = ${len(values) + 1}")
            values.append(is_owner)

        if updates:
            values.append(row["id"])
            row = await db.fetchrow(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ${len(values)} RETURNING *",
                *values,
            )

    if row.get("is_owner") and row.get("tenant_id") is None:
        row = await db.fetchrow("UPDATE users SET tenant_id = id WHERE id = $1 RETURNING *", row["id"])

    return row


async def resolve_canonical_user_id(user: dict, db) -> Optional[uuid.UUID]:
    """Return the AMINRA `users.id` UUID for the authenticated principal."""
    if user.get("app_user_id"):
        app_id = _parse_uuid(user.get("app_user_id"))
        if app_id:
            return app_id

    if user.get("_keycloak"):
        row = await get_or_reconcile_user_from_keycloak_claims(user, db)
        return row["id"] if row else None

    raw_sub = user.get("sub")
    sub_uuid = _parse_uuid(raw_sub)
    if sub_uuid is not None:
        row = await db.fetchrow(
            "SELECT id FROM users WHERE keycloak_sub = $1 OR id = $1 LIMIT 1",
            sub_uuid,
        )
        if row:
            return row["id"]

    email = user.get("email")
    if email:
        row = await db.fetchrow("SELECT id FROM users WHERE lower(email) = $1", str(email).lower())
        if row:
            return row["id"]

    return None


async def resolve_canonical_tenant_id(user: dict, db) -> Optional[uuid.UUID]:
    """Return the canonical AMINRA tenant id for the authenticated principal."""
    row = await get_or_reconcile_user_from_keycloak_claims(user, db) if user.get("_keycloak") else None
    if row is None:
        user_id = await resolve_canonical_user_id(user, db)
        if not user_id:
            return None
        row = await db.fetchrow("SELECT id, tenant_id, is_owner FROM users WHERE id = $1", user_id)
    if not row:
        return None
    if row["is_owner"]:
        return row["tenant_id"] or row["id"]
    return row["tenant_id"]
