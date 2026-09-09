#!/usr/bin/env python3
"""AMINRA live CRUD smoke for QA-only users/orgs/editor/company profile.

Safety:
- Uses QA-prefixed emails/keys only.
- Does not print passwords, tokens, cookies, or auth headers.
- Restores seeded business company profile after test.
- Cleans up temporary PG rows and Keycloak users by exact QA email.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests

API_BASE = os.getenv("QA_API_BASE", "http://127.0.0.1:8000").rstrip("/")
KC_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
KC_REALM = os.getenv("KEYCLOAK_REALM", "aminra")
KC_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "aminra-frontend")
DEMO_PW = os.getenv("DEMO_PW", "DemoP@ss2026")
TS = str(int(time.time()))
RUN_ID = f"qa-crud-{TS}"

# Running inside aminra-backend with /app as cwd.
sys.path.insert(0, "/app")
from auth import keycloak_admin  # noqa: E402

@dataclass
class Result:
    name: str
    status: int | str
    ok: bool
    detail: Any = ""

results: list[Result] = []
created_kc_emails: set[str] = set()
created_pg_user_ids: set[str] = set()


def record(name: str, status: int | str, ok: bool, detail: Any = "") -> None:
    results.append(Result(name, status, bool(ok), detail))


def request_json(method: str, path: str, *, token: str | None = None, expected: set[int] | None = None, **kwargs) -> tuple[int, Any, str]:
    headers = kwargs.pop("headers", {}) or {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if "json" in kwargs:
        headers.setdefault("Content-Type", "application/json")
    res = requests.request(method, f"{API_BASE}{path}", headers=headers, timeout=20, **kwargs)
    text = res.text[:500]
    try:
        body = res.json() if res.text else {}
    except Exception:
        body = text
    return res.status_code, body, text


def token_for(email: str, password: str = DEMO_PW) -> str:
    res = requests.post(
        f"{KC_URL}/realms/{KC_REALM}/protocol/openid-connect/token",
        data={"grant_type": "password", "client_id": KC_CLIENT_ID, "username": email, "password": password},
        headers={
            "X-Forwarded-Proto": os.getenv("KEYCLOAK_PUBLIC_PROTO", "https"),
            "X-Forwarded-Host": os.getenv("KEYCLOAK_PUBLIC_HOST", "auth.silvergem.org"),
            "X-Forwarded-Port": os.getenv("KEYCLOAK_PUBLIC_PORT", "443"),
        },
        timeout=20,
    )
    body = res.json() if res.text else {}
    if res.status_code != 200 or not body.get("access_token"):
        raise RuntimeError(f"token failed for {email}: {res.status_code} {body.get('error')}")
    return body["access_token"]


def cleanup_kc_email(email: str) -> None:
    try:
        uid = keycloak_admin.find_user_by_email(email)
        if uid:
            keycloak_admin.delete_user(uid)
    except Exception as exc:
        record(f"cleanup_kc_{email}", "error", False, type(exc).__name__)


def cleanup_pg_email(email: str) -> None:
    # Best-effort direct DB cleanup for QA-only rows if product delete path failed.
    import asyncio
    import asyncpg

    async def _run():
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            return
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("DELETE FROM users WHERE email=$1", email)
            await conn.execute("DELETE FROM member_invites WHERE email=$1", email)
        finally:
            await conn.close()

    try:
        asyncio.run(_run())
    except Exception as exc:
        record(f"cleanup_pg_{email}", "error", False, type(exc).__name__)


admin_email = f"qa-crud-admin-{TS}@qa.aminra.vn"
admin_pw = f"QaCrudAdmin{TS}!"
biz_member_email = f"qa-crud-member-{TS}@qa.aminra.vn"
biz_member_pw = f"QaCrudMember{TS}!"
auditor_email = f"qa-crud-auditor-{TS}@qa.aminra.vn"
auditor_pw = f"QaCrudAud{TS}!"
admin_target_email = f"qa-crud-target-{TS}@qa.aminra.vn"
admin_target_pw = f"QaCrudTarget{TS}!"
placeholder_key = f"qa_crud_placeholder_{TS}"

try:
    # Ephemeral platform_admin token for admin API.
    admin_kc = keycloak_admin.create_user(
        email=admin_email,
        password=admin_pw,
        role="platform_admin",
        tenant_id=None,
        is_owner=True,
        user_status="active",
        company_name=f"QA CRUD Admin {TS}",
        email_verified=True,
    )
    created_kc_emails.add(admin_email)
    admin_token = token_for(admin_email, admin_pw)
    record("admin_temp_platform_admin_token", 200, True)

    biz_token = token_for("biz-demo-1@demo.aminra.vn")
    provider_token = token_for("cb-demo@demo.aminra.vn")
    auditor_token = token_for("auditor-demo@demo.aminra.vn")
    record("seeded_role_tokens_business_provider_auditor", 200, True)

    # Admin user CRUD.
    st, body, text = request_json("POST", "/admin/users", token=admin_token, json={
        "email": admin_target_email,
        "password": admin_target_pw,
        "role": "business",
        "company_name": f"QA CRUD Target {TS}",
        "company_code": f"QA-CRUD-{TS}",
        "status": "active",
    })
    target_id = body.get("id") if isinstance(body, dict) else None
    if target_id:
        created_pg_user_ids.add(str(target_id)); created_kc_emails.add(admin_target_email)
    record("admin_user_create", st, st in {200, 201} and bool(target_id))

    st, body, _ = request_json("GET", f"/admin/users?q={admin_target_email}", token=admin_token)
    record("admin_user_read_search", st, st == 200 and isinstance(body, dict) and body.get("total") == 1, {"total": body.get("total") if isinstance(body, dict) else None})

    if target_id:
        st, body, _ = request_json("PUT", f"/admin/users/{target_id}", token=admin_token, json={"company_name": f"QA CRUD Target Updated {TS}", "status": "suspended"})
        record("admin_user_update", st, st == 200 and isinstance(body, dict) and body.get("status") == "suspended")
        st, body, _ = request_json("POST", f"/admin/users/{target_id}/reset-password", token=admin_token, json={"new_password": f"QaCrudTargetNew{TS}!"})
        record("admin_user_reset_password", st, st == 200)
        st, body, _ = request_json("DELETE", f"/admin/users/{target_id}", token=admin_token)
        record("admin_user_delete", st, st == 200)

    # Editor/template-placeholder CRUD (admin editor module safe QA key).
    st, body, _ = request_json("POST", "/admin/placeholders", token=admin_token, json={"key": placeholder_key, "label": "QA CRUD Placeholder", "description": RUN_ID, "default_value": "v1", "source": "manual"})
    record("editor_placeholder_create", st, st in {200, 201})
    st, body, _ = request_json("GET", "/admin/placeholders", token=admin_token)
    found_placeholder = isinstance(body, dict) and any(p.get("key") == placeholder_key for p in body.get("placeholders", []))
    record("editor_placeholder_read", st, st == 200 and found_placeholder)
    st, body, _ = request_json("PUT", f"/admin/placeholders/{placeholder_key}", token=admin_token, json={"label": "QA CRUD Placeholder Updated", "default_value": "v2"})
    record("editor_placeholder_update", st, st == 200)
    st, body, _ = request_json("DELETE", f"/admin/placeholders/{placeholder_key}", token=admin_token)
    record("editor_placeholder_delete", st, st == 200)

    # Company profile read/update/restore.
    st, original_profile, _ = request_json("GET", "/auth/company-profile", token=biz_token)
    record("company_profile_read", st, st == 200 and isinstance(original_profile, dict))
    if isinstance(original_profile, dict):
        st, body, _ = request_json("PUT", "/auth/company-profile", token=biz_token, json={
            "company_name": f"Demo Foods Co QA CRUD {TS}",
            "representative_name": f"QA Rep {TS}",
            "address": f"QA Address {TS}",
            "phone": "0900000000",
            "email": original_profile.get("email") or "biz-demo-1@demo.aminra.vn",
            "manager_name": f"QA Manager {TS}",
        })
        record("company_profile_update", st, st == 200)
        st, changed, _ = request_json("GET", "/auth/company-profile", token=biz_token)
        record("company_profile_read_after_update", st, st == 200 and isinstance(changed, dict) and changed.get("manager_name") == f"QA Manager {TS}")
        restore_payload = {k: (original_profile.get(k) or "") for k in ["company_name", "representative_name", "address", "phone", "email", "manager_name"]}
        st, body, _ = request_json("PUT", "/auth/company-profile", token=biz_token, json=restore_payload)
        record("company_profile_restore", st, st == 200)

    # Business member CRUD.
    st, body, _ = request_json("POST", "/auth/business/invite", token=biz_token, json={"email": biz_member_email, "password": biz_member_pw, "display_name": f"QA CRUD Member {TS}", "ihc_role": "QA IHC", "department": "QA Dept"})
    member_id = body.get("member_id") if isinstance(body, dict) else None
    if member_id:
        created_kc_emails.add(biz_member_email)
    record("business_member_create", st, st in {200, 201} and bool(member_id), body if st not in {200, 201} else "")
    st, body, _ = request_json("GET", "/auth/business/members", token=biz_token)
    found_member = isinstance(body, dict) and any(m.get("email") == biz_member_email for m in body.get("members", []))
    record("business_member_read_list", st, st == 200 and found_member)
    if member_id:
        st, body, _ = request_json("PUT", f"/auth/business/members/{member_id}", token=biz_token, json={"display_name": f"QA CRUD Member Updated {TS}", "department": "QA Dept Updated"})
        record("business_member_update", st, st == 200)
        st, body, _ = request_json("GET", f"/auth/business/members/{member_id}/permissions", token=biz_token)
        record("business_member_permissions_read", st, st == 200 and isinstance(body, dict) and "permissions" in body)
        st, body, _ = request_json("PUT", f"/auth/business/members/{member_id}/permissions", token=biz_token, json={"documents": True, "submissions": False})
        record("business_member_permissions_update", st, st == 200)
        st, body, _ = request_json("DELETE", f"/auth/business/members/{member_id}", token=biz_token)
        record("business_member_delete", st, st == 204)
        # Security cleanup check: product delete should not leave login-capable KC orphan.
        try:
            token_for(biz_member_email, biz_member_pw)
            record("business_member_kc_removed_after_delete", 200, False, "Deleted member can still authenticate in Keycloak")
        except Exception:
            record("business_member_kc_removed_after_delete", 401, True)

    # Provider/auditor CRUD.
    st, body, _ = request_json("POST", "/auth/provider/auditors", token=provider_token, json={"email": auditor_email, "password": auditor_pw, "display_name": f"QA CRUD Auditor {TS}", "specialty": "QA Specialty"})
    auditor_id = body.get("auditor_id") if isinstance(body, dict) else None
    if auditor_id:
        created_kc_emails.add(auditor_email)
    record("provider_auditor_create", st, st in {200, 201} and bool(auditor_id), body if st not in {200, 201} else "")
    st, body, _ = request_json("GET", "/auth/provider/auditors", token=provider_token)
    found_auditor = isinstance(body, dict) and any(a.get("email") == auditor_email for a in body.get("auditors", []))
    record("provider_auditor_read_list", st, st == 200 and found_auditor)
    if auditor_id:
        st, body, _ = request_json("PUT", f"/auth/provider/auditors/{auditor_id}", token=provider_token, json={"display_name": f"QA CRUD Auditor Updated {TS}", "specialty": "QA Specialty Updated"})
        record("provider_auditor_update", st, st == 200)
        st, body, _ = request_json("DELETE", f"/auth/provider/auditors/{auditor_id}", token=provider_token)
        record("provider_auditor_delete", st, st == 204)
        try:
            token_for(auditor_email, auditor_pw)
            record("provider_auditor_kc_removed_after_delete", 200, False, "Deleted auditor can still authenticate in Keycloak")
        except Exception:
            record("provider_auditor_kc_removed_after_delete", 401, True)

    # Negative role boundaries.
    st, body, _ = request_json("GET", "/admin/users", token=biz_token)
    record("business_denied_admin_users", st, st == 403)
    st, body, _ = request_json("POST", "/auth/provider/auditors", token=biz_token, json={"email": f"forbidden-{TS}@qa.aminra.vn", "password": "Forbidden123!", "display_name": "Forbidden"})
    record("business_denied_provider_auditor_create", st, st == 403)
    st, body, _ = request_json("GET", "/auth/business/members", token=auditor_token)
    record("auditor_denied_business_members", st, st == 403)

finally:
    # Cleanup by exact known QA emails/keys; safe if product path already deleted.
    for email in [admin_target_email, admin_email, biz_member_email, auditor_email]:
        cleanup_kc_email(email)
        cleanup_pg_email(email)
    try:
        request_json("DELETE", f"/admin/placeholders/{placeholder_key}", token=locals().get("admin_token"))
    except Exception:
        pass

summary = {
    "run_id": RUN_ID,
    "api_base": API_BASE,
    "total": len(results),
    "passed": sum(1 for r in results if r.ok),
    "failed": [asdict(r) for r in results if not r.ok],
    "results": [asdict(r) for r in results],
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
if summary["failed"]:
    sys.exit(1)
