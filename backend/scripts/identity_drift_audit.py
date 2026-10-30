#!/usr/bin/env python3
"""AMINRA identity drift audit.

Reports identity projection inconsistencies between AMINRA `users` rows and the
Keycloak-owned identity model. Safe to run in CI/ops: read-only, JSON output,
non-zero exit when critical drift is detected.

Checks:
- duplicate active lower(email)
- duplicate non-null keycloak_sub
- active users missing keycloak_sub
- Keycloak subjects linked to more than one app row
- owner invariant violations: is_owner=true but tenant_id is NULL/not self
- tenant member rows whose tenant_id does not point to an owner row
- optional Keycloak Admin comparison when KC_ADMIN_URL/KC_REALM/KC_ADMIN_* envs exist
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import asyncpg


async def _fetch(conn, name: str, sql: str) -> dict[str, Any]:
    rows = await conn.fetch(sql)
    return {"name": name, "count": len(rows), "rows": [dict(r) for r in rows]}


async def _db_checks(conn) -> list[dict[str, Any]]:
    checks = [
        (
            "duplicate_active_email",
            """
            SELECT lower(email) AS email, COUNT(*) AS count, array_agg(id::text ORDER BY created_at) AS user_ids
              FROM users
             WHERE email IS NOT NULL AND status::text <> 'deleted'
             GROUP BY lower(email)
            HAVING COUNT(*) > 1
            """,
        ),
        (
            "duplicate_keycloak_sub",
            """
            SELECT keycloak_sub::text AS keycloak_sub, COUNT(*) AS count, array_agg(id::text ORDER BY created_at) AS user_ids
              FROM users
             WHERE keycloak_sub IS NOT NULL AND status::text <> 'deleted'
             GROUP BY keycloak_sub
            HAVING COUNT(*) > 1
            """,
        ),
        (
            "active_user_missing_keycloak_sub",
            """
            SELECT id::text, email, role, status
              FROM users
             WHERE keycloak_sub IS NULL
               AND status::text IN ('active', 'pending', 'approved')
             ORDER BY created_at DESC
            """,
        ),
        (
            "owner_tenant_invariant_violation",
            """
            SELECT id::text, email, role, tenant_id::text, is_owner
              FROM users
             WHERE is_owner = true
               AND status::text <> 'deleted'
               AND (tenant_id IS NULL OR tenant_id <> id)
            """,
        ),
        (
            "member_tenant_without_owner",
            """
            SELECT u.id::text, u.email, u.role, u.tenant_id::text
              FROM users u
              LEFT JOIN users owner ON owner.id = u.tenant_id AND owner.is_owner = true AND owner.status::text <> 'deleted'
             WHERE u.is_owner = false
               AND u.tenant_id IS NOT NULL
               AND u.status::text <> 'deleted'
               AND owner.id IS NULL
            """,
        ),
    ]
    return [await _fetch(conn, name, sql) for name, sql in checks]


def _env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _http_post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # nosec: ops script, URL from env
        return json.loads(resp.read().decode())


def _http_get_json(url: str, token: str) -> Any:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # nosec: ops script, URL from env
        return json.loads(resp.read().decode())


async def _optional_keycloak_check(conn) -> dict[str, Any] | None:
    base = _env("KC_ADMIN_URL", "KEYCLOAK_ADMIN_URL", "KEYCLOAK_URL")
    realm = _env("KC_REALM", "KEYCLOAK_REALM")
    username = _env("KC_ADMIN_USERNAME", "KEYCLOAK_ADMIN_USERNAME")
    password = _env("KC_ADMIN_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD")
    client_id = _env("KC_ADMIN_CLIENT_ID", "KEYCLOAK_ADMIN_CLIENT_ID") or "admin-cli"
    if not base or not realm or not username or not password:
        return {"name": "keycloak_live_projection", "skipped": True, "reason": "missing Keycloak admin env"}

    base = base.rstrip("/")
    token_url = f"{base}/realms/master/protocol/openid-connect/token"
    admin_base = f"{base}/admin/realms/{realm}"
    token = _http_post_form(
        token_url,
        {"grant_type": "password", "client_id": client_id, "username": username, "password": password},
    )["access_token"]
    kc_users = _http_get_json(f"{admin_base}/users?max=10000", token)
    kc_ids = {u.get("id") for u in kc_users if u.get("id")}
    app_rows = await conn.fetch("SELECT id::text, email, keycloak_sub::text FROM users WHERE status::text <> 'deleted'")
    missing_in_kc = [dict(r) for r in app_rows if r["keycloak_sub"] and r["keycloak_sub"] not in kc_ids]
    return {"name": "keycloak_live_projection", "count": len(missing_in_kc), "rows": missing_in_kc}


async def run(database_url: str) -> dict[str, Any]:
    conn = await asyncpg.connect(database_url)
    try:
        checks = await _db_checks(conn)
        kc = await _optional_keycloak_check(conn)
        if kc:
            checks.append(kc)
    finally:
        await conn.close()
    critical = [c for c in checks if not c.get("skipped") and c.get("count", 0) > 0]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if critical else "pass",
        "critical_count": len(critical),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        print("DATABASE_URL or --database-url is required", file=sys.stderr)
        return 2
    report = asyncio.run(run(args.database_url))
    print(json.dumps(report, default=str, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
