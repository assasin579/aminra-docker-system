"""Canonical AMINRA identity resolution.

A Keycloak JWT's `sub` claim is the Keycloak user UUID, which never matches
the AMINRA `users.id` PG UUID. Endpoints that previously read `user["sub"]`
straight into `WHERE id = $1` queries silently mis-targeted rows (or 404'd)
once the SSO cutover landed (Phase 4b).

The fix is to resolve identity through the JIT-linked `keycloak_sub` column
first, then fall back to email lookup. Pre-Phase-4 sessions issued PG-rooted
tokens where `sub` *was* the AMINRA id, so we also accept that shape — it's
free to support and keeps test fixtures working without rewrite.
"""

from __future__ import annotations

import uuid
from typing import Optional


async def resolve_canonical_user_id(user: dict, db) -> Optional[uuid.UUID]:
    """Return the AMINRA `users.id` UUID for the authenticated principal.

    Lookup order:
      1. `sub` interpreted as a Keycloak UUID → match on `users.keycloak_sub`
      2. `sub` interpreted as an AMINRA UUID → match on `users.id`
         (covers test fixtures + the pre-SSO token shape)
      3. `email` → match on `users.email` (last resort; expensive)

    Returns None when no row matches. Callers should 404 in that case.
    """
    raw_sub = user.get("sub")
    if raw_sub:
        try:
            sub_uuid = uuid.UUID(str(raw_sub))
        except (ValueError, TypeError):
            sub_uuid = None
        if sub_uuid is not None:
            row = await db.fetchrow(
                "SELECT id FROM users WHERE keycloak_sub = $1 OR id = $1 LIMIT 1",
                sub_uuid,
            )
            if row:
                return row["id"]

    email = user.get("email")
    if email:
        row = await db.fetchrow(
            "SELECT id FROM users WHERE email = $1", email,
        )
        if row:
            return row["id"]

    return None


async def resolve_canonical_tenant_id(user: dict, db) -> Optional[uuid.UUID]:
    """Return the AMINRA `users.tenant_id` UUID for the authenticated principal.

    Owners are their own tenant root, so an owner row with `tenant_id = NULL`
    falls back to `id`. The Keycloak `tenant_id` claim is intentionally NOT
    trusted here — it may be a slug from the user-attribute mapper rather than
    the DB UUID, and the canonical source of truth is the PG row.
    """
    row = await db.fetchrow(
        "SELECT id, tenant_id, is_owner FROM users WHERE email = $1",
        user.get("email"),
    )
    if not row:
        return None
    if row["is_owner"]:
        return row["tenant_id"] or row["id"]
    return row["tenant_id"]
