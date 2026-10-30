"""Preflight database deletion before removing a team's Keycloak identity."""

from uuid import UUID

import asyncpg
from fastapi import HTTPException

from auth import keycloak_admin


class _RollbackProbe(Exception):
    """Roll back a successful deletion probe, including all cascading changes."""


async def remove_team_account(
    db: asyncpg.Connection,
    *,
    user_id: UUID,
    tenant_id: UUID,
    provider_only: bool = False,
) -> None:
    """Keep both identities intact when history or database references block deletion.

    The parent row lock prevents new foreign-key references between the probe
    and deletion. The savepoint always rolls back the probe and its cascades.
    Keycloak errors roll back the outer transaction without deleting app data.
    """
    async with db.transaction():
        row = await db.fetchrow(
            "SELECT id, keycloak_sub FROM users "
            "WHERE id = $1 AND tenant_id = $2 AND is_owner = false "
            "AND (NOT $3::boolean OR role = 'provider') FOR UPDATE",
            user_id,
            tenant_id,
            provider_only,
        )
        if not row:
            raise HTTPException(404, "Team member not found")

        try:
            async with db.transaction():
                await db.execute("DELETE FROM users WHERE id = $1", row["id"])
                raise _RollbackProbe()
        except _RollbackProbe:
            pass
        except asyncpg.PostgresError as exc:
            sqlstate = getattr(exc, "sqlstate", "") or ""
            if sqlstate.startswith("23") or sqlstate == "P0001":
                raise HTTPException(
                    409,
                    "Không thể xoá tài khoản có lịch sử hoặc dữ liệu liên quan. "
                    "Giữ tài khoản để bảo toàn lịch sử.",
                ) from exc
            raise

        if row["keycloak_sub"]:
            keycloak_admin.delete_user(str(row["keycloak_sub"]))
        await db.execute("DELETE FROM users WHERE id = $1", row["id"])
