#!/usr/bin/env python3
"""AMINRA runtime login/account-type matrix smoke.

Safety: read-only except password-grant login attempts; never prints tokens or passwords.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8100").rstrip("/")
KC_URL = os.getenv("KEYCLOAK_URL", "https://auth.silvergem.org").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "aminra")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "aminra-frontend")
DEMO_PW = os.getenv("DEMO_PW", "DemoP@ss2026")
ADMIN_PW = os.getenv("ADMIN_DEMO_PW", DEMO_PW)

APP_ROLES = {"business", "auditor", "cb_admin", "platform_admin"}
OUT = Path(__file__).with_name("runtime-login-matrix-results.json")

@dataclass(frozen=True)
class Account:
    label: str
    username: str
    password: str
    expected_app_role: str | None
    expected_realm_role: str
    can_login: bool = True

ACCOUNTS = [
    Account("platform_admin_username", "admin", ADMIN_PW, None, "platform_admin"),
    Account("platform_admin_email", "admin@aminra.com", ADMIN_PW, None, "platform_admin"),
    Account("cb_provider", "cb-demo@demo.aminra.vn", DEMO_PW, "provider", "cb_admin"),
    Account("business", "biz-demo-1@demo.aminra.vn", DEMO_PW, "business", "business"),
    Account("auditor", "auditor-demo@demo.aminra.vn", DEMO_PW, "auditor", "auditor"),
    Account("disabled_surplus_business_negative", "biz-demo-2@demo.aminra.vn", DEMO_PW, None, "business", can_login=False),
]

ADMIN_READ = ["/auth/admin/analytics", "/auth/admin/feature-flags", "/auth/admin/pending-providers", "/auth/admin/overdue-submissions"]
PROVIDER_READ = ["/api/submissions/received", "/api/submissions/cb-stats", "/api/submissions/certificates/registry", "/api/audits/"]
BUSINESS_READ = ["/auth/me", "/api/submissions/my-submissions", "/dossiers", "/api/supply-chain/suppliers", "/api/supply-chain/materials", "/api/supply-chain/processes", "/api/supply-chain/batches"]
AUDITOR_READ = ["/api/audits/"]


def post_form(url: str, data: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        headers={
            "X-Forwarded-Proto": os.getenv("KEYCLOAK_PUBLIC_PROTO", "https"),
            "X-Forwarded-Host": os.getenv("KEYCLOAK_PUBLIC_HOST", "auth.silvergem.org"),
            "X-Forwarded-Port": os.getenv("KEYCLOAK_PUBLIC_PORT", "443"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 controlled URL
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            body = {"raw": raw[:300]}
        return exc.code, body


def request_json(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BACKEND_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 controlled URL
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw or "{}")
            except json.JSONDecodeError:
                return resp.status, raw[:300]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, raw[:300]


def token(username: str, password: str) -> tuple[int, str | None, dict]:
    status, body = post_form(
        f"{KC_URL}/realms/{REALM}/protocol/openid-connect/token",
        {"grant_type": "password", "client_id": CLIENT_ID, "username": username, "password": password},
    )
    tok = body.get("access_token") if isinstance(body, dict) else None
    safe_error = {k: body.get(k) for k in ("error", "error_description") if isinstance(body, dict) and k in body}
    return status, tok, safe_error


def decode_payload(tok: str) -> dict:
    payload = tok.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode()))


def allowed_for(label: str, path: str) -> bool:
    if label.startswith("platform_admin"):
        return path in set(ADMIN_READ + ["/auth/me"])
    if label == "cb_provider":
        return path in set(PROVIDER_READ + ["/auth/me", "/dossiers"])  # CB/provider surfaces only; no business supply-chain tenant data
    if label == "business":
        return path in set(BUSINESS_READ)
    if label == "auditor":
        return path in set(AUDITOR_READ + ["/auth/me"])
    return False


def main() -> int:
    results = {"started_at": datetime.now(timezone.utc).isoformat(), "backend_url": BACKEND_URL, "kc_url": KC_URL, "accounts": []}
    failures: list[str] = []
    all_paths = sorted(set(ADMIN_READ + PROVIDER_READ + BUSINESS_READ + AUDITOR_READ))

    # Baseline public health
    health_status, health_body = request_json("GET", "/health")
    results["health"] = {"status": health_status, "database": health_body.get("database") if isinstance(health_body, dict) else None}
    if health_status != 200:
        failures.append(f"health expected 200 got {health_status}")

    for acct in ACCOUNTS:
        row = {"label": acct.label, "username": acct.username, "expected_login": acct.can_login, "login_status": None, "realm_roles": [], "auth_me": None, "routes": []}
        status, tok, safe_error = token(acct.username, acct.password)
        row["login_status"] = status
        if safe_error:
            row["login_error"] = safe_error
        if acct.can_login and not tok:
            failures.append(f"{acct.label} login expected success got HTTP {status} {safe_error}")
            results["accounts"].append(row)
            continue
        if not acct.can_login:
            if tok:
                failures.append(f"{acct.label} expected disabled/rejected but login succeeded")
            else:
                row["negative_passed"] = status in (400, 401, 403)
                if not row["negative_passed"]:
                    failures.append(f"{acct.label} expected 400/401/403 got {status}")
            results["accounts"].append(row)
            continue

        claims = decode_payload(tok)
        realm_roles = claims.get("realm_access", {}).get("roles", [])
        app_roles = sorted(set(realm_roles).intersection(APP_ROLES))
        row["realm_roles"] = app_roles
        if acct.expected_realm_role not in app_roles:
            failures.append(f"{acct.label} missing realm role {acct.expected_realm_role}; got {app_roles}")

        me_status, me_body = request_json("GET", "/auth/me", tok)
        row["auth_me"] = {"status": me_status}
        if isinstance(me_body, dict):
            row["auth_me"].update({k: me_body.get(k) for k in ["email", "role", "status", "is_owner"] if k in me_body})
        if me_status != 200:
            failures.append(f"{acct.label} /auth/me expected 200 got {me_status}")
        elif acct.expected_app_role and isinstance(me_body, dict) and me_body.get("role") != acct.expected_app_role:
            failures.append(f"{acct.label} /auth/me role expected {acct.expected_app_role} got {me_body.get('role')}")

        for path in all_paths:
            method = "GET"
            st, _ = request_json(method, path, tok)
            expect_allowed = allowed_for(acct.label, path)
            row["routes"].append({"path": path, "status": st, "expected": "allow" if expect_allowed else "deny"})
            if expect_allowed and st not in (200, 307):
                failures.append(f"{acct.label} expected allow {path}, got {st}")
            if not expect_allowed and st not in (401, 403, 404, 405):
                failures.append(f"{acct.label} expected deny/non-surface {path}, got {st}")
        results["accounts"].append(row)

    # Wrong password negatives for enabled humans.
    results["wrong_password_negatives"] = []
    for acct in ACCOUNTS[:5]:
        st, tok_bad, err = token(acct.username, "DefinitelyWrong-Login-QA-2026!")
        ok = (tok_bad is None and st in (400, 401, 403))
        results["wrong_password_negatives"].append({"label": acct.label, "status": st, "passed": ok, "error": err})
        if not ok:
            failures.append(f"{acct.label} wrong password expected reject got {st}")

    results["failures"] = failures
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT}")
    print(f"PASS={len(failures)==0} failures={len(failures)}")
    for f in failures[:50]:
        print(f"FAIL: {f}")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
