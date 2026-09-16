from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException

from auth.db import get_db
from auth.jwt_utils import get_current_user

MODULE_GUARDS_ENV = "MODULE_GUARDS_ENABLED"
_ALLOWED_STATUSES = {"enabled", "trial"}


def _guards_enabled() -> bool:
    return os.getenv(MODULE_GUARDS_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return getattr(row, key, default)


def require_module(module_code: str) -> Callable[..., Any]:
    """FastAPI dependency factory for module entitlement enforcement.

    Rollout safety: when MODULE_GUARDS_ENABLED is false, this dependency is
    intentionally fail-open/no-op. This lets us wire guards now and enable them
    route-by-route only after migration and browser UAT are green.
    """

    async def dependency(user=Depends(get_current_user), db=Depends(get_db)) -> None:
        if not _guards_enabled():
            return None

        tenant_id = user.get("tenant_id") if isinstance(user, dict) else None
        if not tenant_id:
            raise HTTPException(status_code=403, detail="TENANT_REQUIRED")

        row = await db.fetchrow(
            """
            SELECT tm.status
            FROM tenant_modules tm
            JOIN modules m ON m.id = tm.module_id
            WHERE tm.tenant_id = $1
              AND m.code = $2
              AND m.enabled = true
            """,
            tenant_id,
            module_code,
        )
        status = _row_get(row, "status")
        if status not in _ALLOWED_STATUSES:
            raise HTTPException(status_code=403, detail=f"MODULE_DISABLED:{module_code}")
        return None

    return dependency
