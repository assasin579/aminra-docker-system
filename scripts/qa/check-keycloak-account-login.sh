#!/usr/bin/env bash
# Verify one or more Keycloak demo/customer-pilot accounts can exchange their
# current password for a token and (optionally) carry the expected realm role.
#
# Credentials are supplied at runtime via JSON, never committed:
#   DEMO_LOGIN_SMOKE_ACCOUNTS_JSON='[{"email":"abc@demo.com","password":"...","expected_role":"business"}]' \
#     bash scripts/qa/check-keycloak-account-login.sh
# or pipe JSON on stdin:
#   printf '%s' '[{"email":"abc@demo.com","password":"..."}]' | bash ...
#
# Use --dry-run to validate parsing/redaction only; no network call is made.

set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

KEYCLOAK_URL="${KEYCLOAK_URL:-http://127.0.0.1:8180}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-aminra}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-aminra-frontend}"

if [[ -n "${DEMO_LOGIN_SMOKE_ACCOUNTS_JSON:-}" ]]; then
  ACCOUNTS_JSON="$DEMO_LOGIN_SMOKE_ACCOUNTS_JSON"
else
  ACCOUNTS_JSON="$(cat)"
fi

if [[ -z "$ACCOUNTS_JSON" ]]; then
  echo "ERROR: provide DEMO_LOGIN_SMOKE_ACCOUNTS_JSON or JSON on stdin" >&2
  exit 2
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aminra-login-smoke.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT
ACCOUNTS_FILE="$TMP_DIR/accounts.json"
printf '%s' "$ACCOUNTS_JSON" >"$ACCOUNTS_FILE"

python3 - "$ACCOUNTS_FILE" "$DRY_RUN" "$KEYCLOAK_URL" "$KEYCLOAK_REALM" "$KEYCLOAK_CLIENT_ID" <<'PY'
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

accounts_path = Path(sys.argv[1])
dry_run = sys.argv[2] == "1"
keycloak_url = sys.argv[3].rstrip("/")
realm = sys.argv[4]
client_id = sys.argv[5]

try:
    accounts = json.loads(accounts_path.read_text())
except json.JSONDecodeError as exc:
    print(f"ERROR: invalid DEMO_LOGIN_SMOKE_ACCOUNTS_JSON: {exc}", file=sys.stderr)
    raise SystemExit(2)

if not isinstance(accounts, list) or not accounts:
    print("ERROR: accounts JSON must be a non-empty list", file=sys.stderr)
    raise SystemExit(2)

failures: list[str] = []

def decode_jwt_payload(token: str) -> dict:
    try:
        payload = token.split(".", 2)[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()))
    except Exception:
        return {}

for idx, acct in enumerate(accounts, start=1):
    if not isinstance(acct, dict):
        failures.append(f"account[{idx}] is not an object")
        continue
    email = str(acct.get("email") or "").strip()
    password = acct.get("password")
    expected_role = acct.get("expected_role")
    if not email or not isinstance(password, str) or not password:
        failures.append(f"account[{idx}] missing email/password")
        continue

    if dry_run:
        print(f"DRY-RUN ok: {email} password=REDACTED expected_role={expected_role or '-'}")
        continue

    cmd = [
        "curl", "-sS", "-X", "POST",
        f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token",
        "-H", "Content-Type: application/x-www-form-urlencoded",
        "--data-urlencode", "grant_type=password",
        "--data-urlencode", f"client_id={client_id}",
        "--data-urlencode", f"username={email}",
        "--data-urlencode", f"password={password}",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    if proc.returncode != 0:
        failures.append(f"{email}: token request failed rc={proc.returncode}: {proc.stderr.strip()}")
        continue
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError:
        failures.append(f"{email}: token response was not JSON")
        continue
    token = body.get("access_token")
    if not token:
        err = body.get("error") or "unknown_error"
        desc = body.get("error_description") or ""
        failures.append(f"{email}: login failed: {err} {desc}".strip())
        continue
    if expected_role:
        claims = decode_jwt_payload(token)
        roles = set((claims.get("realm_access") or {}).get("roles") or [])
        role = claims.get("role")
        if expected_role not in roles and expected_role != role:
            failures.append(f"{email}: expected_role={expected_role} missing from token roles")
            continue
    print(f"PASS: {email} login ok password=REDACTED expected_role={expected_role or '-'}")

if failures:
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    raise SystemExit(1)
PY
