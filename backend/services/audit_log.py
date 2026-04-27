"""Audit log service — append-only record of who-changed-what.

Design principles:
- **Never block the parent request.** A failed audit-log INSERT must not
  surface as a 5xx to the user. We swallow + log the exception.
- **Denormalized user fields** so logs remain readable after user deletion.
- **Diff via `compute_diff`** keeps changes succinct (only changed keys).
- **Caller must specify entity_type + action** as strings — no implicit
  inference from payload, so logs are explicit and queryable.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Optional

log = logging.getLogger("aminra.audit_log")


# ── Diff helper ─────────────────────────────────────────────────────────────

def compute_diff(before: dict, after: dict, ignore: Iterable[str] = ()) -> dict:
    """Return only the keys whose value changed, as {key: [before, after]}.

    Useful when logging UPDATE actions: we don't want to write the entire row
    in the log, only what actually changed.
    """
    skip = set(ignore)
    diff: dict[str, list] = {}
    for key in set(before) | set(after):
        if key in skip:
            continue
        if before.get(key) != after.get(key):
            diff[key] = [before.get(key), after.get(key)]
    return diff


# ── Logger ──────────────────────────────────────────────────────────────────

async def log_audit(
    db,
    *,
    action: str,
    entity_type: str,
    user: Optional[dict] = None,
    entity_id: Optional[str] = None,
    changes: Optional[dict] = None,
    metadata: Optional[dict] = None,
    request: Optional[Any] = None,
) -> None:
    """Append one row to audit_logs. Never raises.

    `user` is the JWT payload (sub, email, role, tenant_id) — pass None for
    anonymous events (failed login, public verify, …).

    `request` is an optional FastAPI Request — when given, ip + user_agent
    are extracted into metadata.
    """
    if not action or not entity_type:
        log.warning("[audit_log] refused: action and entity_type are required")
        return

    user = user or {}
    user_id = user.get("sub")
    user_email = user.get("email")
    user_role = user.get("role")
    tenant_id = user.get("tenant_id")

    enriched_metadata = dict(metadata or {})
    if request is not None:
        client = getattr(request, "client", None)
        if client and getattr(client, "host", None):
            enriched_metadata.setdefault("ip", client.host)
        ua = request.headers.get("user-agent") if hasattr(request, "headers") else None
        if ua:
            enriched_metadata.setdefault("user_agent", ua)

    try:
        await db.execute(
            """
            INSERT INTO audit_logs
                (user_id, user_email, user_role, tenant_id,
                 action, entity_type, entity_id, changes, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb)
            """,
            user_id,
            user_email,
            user_role,
            tenant_id,
            action,
            entity_type,
            entity_id,
            json.dumps(changes) if changes is not None else None,
            json.dumps(enriched_metadata),
        )
    except Exception as e:
        # Never propagate — audit failure must not break the parent request.
        log.exception(
            "[audit_log] insert failed action=%s entity=%s/%s err=%s",
            action, entity_type, entity_id, e,
        )


# ── Filter query builder (used by admin endpoint) ───────────────────────────

ALLOWED_FILTER_FIELDS = {
    "user_id":     "user_id",
    "tenant_id":   "tenant_id",
    "action":      "action",
    "entity_type": "entity_type",
    "entity_id":   "entity_id",
}

VALID_SORT = {"created_at", "action", "entity_type"}


def build_filter_query(
    filters: dict,
    *,
    page: int = 1,
    limit: int = 50,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[str, list]:
    """Return (sql, params) for SELECT-from-audit_logs with safe filters.

    Raises ValueError on unknown filter keys or invalid sort/order — the
    caller is responsible for translating that to a 400 response.
    """
    if sort not in VALID_SORT:
        raise ValueError(f"Invalid sort field: {sort}")
    if order.lower() not in ("asc", "desc"):
        raise ValueError(f"Invalid order: {order}")
    if page < 1:
        raise ValueError("page must be >= 1")
    if not (1 <= limit <= 200):
        raise ValueError("limit must be 1..200")

    SPECIAL = {"from_date", "to_date"}

    where_clauses: list[str] = []
    params: list = []
    idx = 1
    for key, value in filters.items():
        if value is None or value == "":
            continue
        if key in SPECIAL:
            continue  # handled below
        if key not in ALLOWED_FILTER_FIELDS:
            raise ValueError(f"Unknown filter field: {key}")
        column = ALLOWED_FILTER_FIELDS[key]
        where_clauses.append(f"{column} = ${idx}")
        params.append(value)
        idx += 1

    if filters.get("from_date"):
        where_clauses.append(f"created_at >= ${idx}")
        params.append(filters["from_date"])
        idx += 1
    if filters.get("to_date"):
        where_clauses.append(f"created_at < ${idx}")
        params.append(filters["to_date"])
        idx += 1

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    offset = (page - 1) * limit
    sql = (
        f"SELECT * FROM audit_logs {where_sql} "
        f"ORDER BY {sort} {order.upper()} "
        f"LIMIT {limit} OFFSET {offset}"
    )
    return sql, params
