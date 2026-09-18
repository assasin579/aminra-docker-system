#!/usr/bin/env python3
"""Sync AMINRA user projection identity status from Keycloak.

Safe default: dry-run. `--apply` only updates projection status fields; it never
deletes AMINRA `users` rows or Keycloak identities.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import asyncpg

VALID_STATUSES = {"linked", "missing_in_keycloak", "disabled_in_keycloak", "unknown"}


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


def _http_get_json_or_status(url: str, token: str) -> tuple[int, Any | None]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec: ops script, URL from env
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 404, None
        raise


def _keycloak_config() -> dict[str, str] | None:
    base = _env("KC_ADMIN_URL", "KEYCLOAK_ADMIN_URL", "KEYCLOAK_ADMIN_BASE_URL", "KEYCLOAK_URL")
    realm = _env("KC_REALM", "KEYCLOAK_REALM")
    client_id = _env("KC_ADMIN_CLIENT_ID", "KEYCLOAK_ADMIN_CLIENT_ID", "KEYCLOAK_ADMIN_CLI_CLIENT_ID") or "admin-cli"
    client_secret = _env("KC_ADMIN_CLIENT_SECRET", "KEYCLOAK_ADMIN_CLIENT_SECRET", "KEYCLOAK_ADMIN_CLI_SECRET")
    username = _env("KC_ADMIN_USERNAME", "KEYCLOAK_ADMIN_USERNAME", "KEYCLOAK_ADMIN")
    password = _env("KC_ADMIN_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD")
    if not base or not realm:
        return None
    if client_secret:
        return {"base": base.rstrip("/"), "realm": realm, "client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"}
    if username and password:
        return {"base": base.rstrip("/"), "realm": realm, "client_id": client_id, "username": username, "password": password, "grant_type": "password"}
    return None


def _token(cfg: dict[str, str]) -> str:
    base = cfg["base"]
    if cfg["grant_type"] == "client_credentials":
        return _http_post_form(
            f"{base}/realms/{cfg['realm']}/protocol/openid-connect/token",
            {"grant_type": "client_credentials", "client_id": cfg["client_id"], "client_secret": cfg["client_secret"]},
        )["access_token"]
    return _http_post_form(
        f"{base}/realms/master/protocol/openid-connect/token",
        {"grant_type": "password", "client_id": cfg["client_id"], "username": cfg["username"], "password": cfg["password"]},
    )["access_token"]


def _desired_status(kc_status: int, kc_user: dict[str, Any] | None) -> str:
    if kc_status == 404:
        return "missing_in_keycloak"
    if kc_status == 200 and kc_user and kc_user.get("enabled") is False:
        return "disabled_in_keycloak"
    if kc_status == 200:
        return "linked"
    return "unknown"


async def run(database_url: str, apply: bool = False) -> dict[str, Any]:
    cfg = _keycloak_config()
    if not cfg:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "skipped",
            "reason": "missing Keycloak admin env",
            "apply": apply,
        }
    token = _token(cfg)
    admin_base = f"{cfg['base']}/admin/realms/{cfg['realm']}"

    conn = await asyncpg.connect(database_url)
    changes: list[dict[str, Any]] = []
    try:
        rows = await conn.fetch(
            """
            SELECT id::text, email, keycloak_sub::text,
                   COALESCE(identity_status, 'linked') AS identity_status
              FROM users
             WHERE keycloak_sub IS NOT NULL
             ORDER BY created_at DESC
            """
        )
        for row in rows:
            kc_status, kc_user = _http_get_json_or_status(f"{admin_base}/users/{row['keycloak_sub']}", token)
            desired = _desired_status(kc_status, kc_user)
            if desired not in VALID_STATUSES:
                desired = "unknown"
            if desired != row["identity_status"]:
                change = {
                    "user_id": row["id"],
                    "email": row["email"],
                    "keycloak_sub": row["keycloak_sub"],
                    "from": row["identity_status"],
                    "to": desired,
                }
                changes.append(change)
                if apply:
                    await conn.execute(
                        """
                        UPDATE users
                           SET identity_status = $2,
                               keycloak_deleted_at = CASE
                                   WHEN $2 = 'missing_in_keycloak' THEN COALESCE(keycloak_deleted_at, NOW())
                                   WHEN $2 = 'linked' THEN NULL
                                   ELSE keycloak_deleted_at
                               END,
                               updated_at = NOW()
                         WHERE id = $1
                        """,
                        row["id"],
                        desired,
                    )
    finally:
        await conn.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "changed" if changes else "pass",
        "apply": apply,
        "changed_count": len(changes),
        "changes": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--apply", action="store_true", help="Update identity_status/keycloak_deleted_at; never deletes rows")
    args = parser.parse_args()
    if not args.database_url:
        print("DATABASE_URL or --database-url is required", file=sys.stderr)
        return 2
    report = asyncio.run(run(args.database_url, apply=args.apply))
    print(json.dumps(report, default=str, ensure_ascii=False, indent=2))
    if report["status"] == "skipped":
        return 2
    return 1 if report.get("changed_count", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
