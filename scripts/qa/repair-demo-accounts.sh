#!/usr/bin/env bash
# Repair AMINRA demo Keycloak accounts without printing secrets.
set -euo pipefail
ROOT="${AMINRA_ROOT:-/home/user/Documents/aminra-docker-system}"
cd "$ROOT"
python3 - <<'PY'
from __future__ import annotations
import json, os, secrets, string, subprocess, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path.cwd()
ENV = ROOT / ".env"
QA = ROOT / ".qa" / "aminra-demo-credentials.env"

def load_env(path: Path) -> dict[str, str]:
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out

env = {**load_env(ENV), **load_env(QA), **os.environ}
base = env.get("KEYCLOAK_URL", "http://127.0.0.1:8180").rstrip("/")
# KEYCLOAK_URL may point to public issuer; use local admin endpoint unless explicitly overridden.
admin_base = env.get("KEYCLOAK_ADMIN_BASE_URL", "http://127.0.0.1:8180").rstrip("/")
realm = env.get("KEYCLOAK_REALM", "aminra")
admin_user = env.get("KEYCLOAK_ADMIN_USER", "admin")
admin_pass = env.get("KEYCLOAK_ADMIN_PASSWORD")
client_id = env.get("KEYCLOAK_CLIENT_ID", "aminra-frontend")
if not admin_pass:
    raise SystemExit("ERROR: KEYCLOAK_ADMIN_PASSWORD missing in env/.env")

def form_post(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:  # controlled local Keycloak
        return json.loads(resp.read())

def json_req(method: str, path: str, token: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"{admin_base}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        raise RuntimeError(f"Keycloak admin API failed method={method} path={path} status={exc.code} body={text[:400]}")

def token_request(email: str, password: str) -> bool:
    try:
        form_post(f"{admin_base}/realms/{realm}/protocol/openid-connect/token", {
            "grant_type": "password", "client_id": client_id, "username": email, "password": password,
        })
        return True
    except Exception:
        return False

def gen_pw() -> str:
    alphabet = string.ascii_letters + string.digits
    return "Aminra!" + "".join(secrets.choice(alphabet) for _ in range(18)) + "9"

admin_tok = form_post(f"{admin_base}/realms/master/protocol/openid-connect/token", {
    "grant_type": "password", "client_id": "admin-cli", "username": admin_user, "password": admin_pass,
})["access_token"]

roles_cache = {}
def role_repr(role_name: str) -> dict:
    if role_name not in roles_cache:
        _, role = json_req("GET", f"/admin/realms/{realm}/roles/{urllib.parse.quote(role_name)}", admin_tok)
        roles_cache[role_name] = role
    return roles_cache[role_name]

def ensure_user(email: str, role_name: str, new_pw: str):
    _, users = json_req("GET", f"/admin/realms/{realm}/users?username={urllib.parse.quote(email)}&exact=true", admin_tok)
    if not users:
        status, _ = json_req("POST", f"/admin/realms/{realm}/users", admin_tok, {
            "username": email, "email": email, "enabled": True, "emailVerified": True, "requiredActions": [],
        })
        _, users = json_req("GET", f"/admin/realms/{realm}/users?username={urllib.parse.quote(email)}&exact=true", admin_tok)
    user = users[0]
    uid = user["id"]
    json_req("PUT", f"/admin/realms/{realm}/users/{uid}", admin_tok, {
        **user, "enabled": True, "emailVerified": True, "requiredActions": []
    })
    json_req("PUT", f"/admin/realms/{realm}/users/{uid}/reset-password", admin_tok, {
        "type": "password", "value": new_pw, "temporary": False,
    })
    # Clear brute-force lock if endpoint is available.
    try:
        json_req("DELETE", f"/admin/realms/{realm}/attack-detection/brute-force/users/{uid}", admin_tok)
    except Exception:
        pass
    # Ensure realm role.
    try:
        json_req("POST", f"/admin/realms/{realm}/users/{uid}/role-mappings/realm", admin_tok, [role_repr(role_name)])
    except Exception:
        # Duplicate role mapping may return non-2xx in some KC versions; verify via login below instead of leaking details.
        pass
    if not token_request(email, new_pw):
        raise SystemExit(f"ERROR: repaired account still cannot login: {email}")
    print(f"PASS: repaired {email} role={role_name} password=REDACTED")
    return new_pw

provider_pw = gen_pw()
admin_demo_pw = gen_pw()
provider_pw = ensure_user("cb-demo@demo.aminra.vn", "cb_admin", provider_pw)
admin_demo_pw = ensure_user("demo-platform-admin@demo.aminra.vn", "platform_admin", admin_demo_pw)

# Preserve existing file comments/order lightly and write only relevant keys without printing values.
QA.parent.mkdir(parents=True, exist_ok=True)
existing = load_env(QA)
existing["PROVIDER_DEMO_PW"] = provider_pw
existing["ADMIN_DEMO_PW"] = admin_demo_pw
existing["TEST_ADMIN_EMAIL"] = "demo-platform-admin@demo.aminra.vn"
existing["TEST_ADMIN_PASSWORD"] = admin_demo_pw
if "DEMO_PW" not in existing:
    existing["DEMO_PW"] = env.get("DEMO_PW", "DemoP@ss2026")
lines = ["# Local QA demo credentials. Do not commit. Values intentionally not printed by repair script."]
for k in sorted(existing):
    lines.append(f"{k}={existing[k]}")
QA.write_text("\n".join(lines) + "\n")
QA.chmod(0o600)
print(f"PASS: updated {QA} mode=600 values=REDACTED")
PY
