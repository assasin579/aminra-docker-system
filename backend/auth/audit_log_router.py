"""Admin endpoint to query audit_logs.

Append-only at the DB level — there is no DELETE/UPDATE endpoint by design.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException, Query

from auth.db import get_db
from auth.jwt_utils import require_admin
from services.audit_log import build_filter_query

log = logging.getLogger("aminra.audit_log_router")
router = APIRouter()


def _serialize(row) -> dict:
    return {
        "id":          str(row["id"]),
        "user_id":     str(row["user_id"]) if row["user_id"] else None,
        "user_email":  row["user_email"],
        "user_role":   row["user_role"],
        "tenant_id":   str(row["tenant_id"]) if row["tenant_id"] else None,
        "action":      row["action"],
        "entity_type": row["entity_type"],
        "entity_id":   str(row["entity_id"]) if row["entity_id"] else None,
        "changes":     json.loads(row["changes"]) if row["changes"] else None,
        "metadata":    json.loads(row["metadata"]) if row["metadata"] else {},
        "created_at":  row["created_at"].isoformat(),
    }


@router.get("/admin/audit-logs")
async def list_audit_logs(
    user_id:     Optional[str] = Query(None),
    tenant_id:   Optional[str] = Query(None),
    action:      Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id:   Optional[str] = Query(None),
    from_date:   Optional[str] = Query(None, description="ISO timestamp, inclusive"),
    to_date:     Optional[str] = Query(None, description="ISO timestamp, exclusive"),
    page:        int = Query(1, ge=1),
    limit:       int = Query(50, ge=1, le=200),
    sort:        str = Query("created_at"),
    order:       str = Query("desc"),
    admin:       dict = Depends(require_admin),
    db:          Connection = Depends(get_db),
):
    """List audit log entries. Admin-only. Filterable by who/what/when."""
    filters = {
        "user_id":     user_id,
        "tenant_id":   tenant_id,
        "action":      action,
        "entity_type": entity_type,
        "entity_id":   entity_id,
        "from_date":   from_date,
        "to_date":     to_date,
    }
    try:
        sql, params = build_filter_query(filters, page=page, limit=limit, sort=sort, order=order)
    except ValueError as e:
        raise HTTPException(400, str(e))

    rows = await db.fetch(sql, *params)
    total = await db.fetchval(_count_sql_from(sql), *params)

    return {
        "logs": [_serialize(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total or 0,
    }


def _count_sql_from(select_sql: str) -> str:
    """Strip ORDER BY / LIMIT from the listing SQL → wrap into a COUNT(*)."""
    head = select_sql.split(" ORDER BY ")[0]
    return head.replace("SELECT * FROM", "SELECT COUNT(*) FROM", 1)
