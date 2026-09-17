#!/usr/bin/env bash
# Configure a local QA SMTP relay for Keycloak and prove email delivery by
# triggering execute-actions-email for VERIFY_EMAIL.
#
# Safety invariant: user-facing action links must be generated through a public
# HTTPS Keycloak base URL. Private/local bases (localhost, keycloak:8080, :8180)
# are blocked unless QA_ALLOW_PRIVATE_ACTION_URL=1 is explicitly set for capture-only QA.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -f .qa/aminra-demo-credentials.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .qa/aminra-demo-credentials.env
  set +a
fi

KEYCLOAK_ADMIN_BASE_URL="${KEYCLOAK_ADMIN_BASE_URL:-http://127.0.0.1:8180}"
KEYCLOAK_EMAIL_ACTION_BASE_URL="${KEYCLOAK_EMAIL_ACTION_BASE_URL:-${KEYCLOAK_PUBLIC_URL:-https://auth.aminra.org}}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-aminra}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-}"
SMTP_HOST="${QA_SMTP_HOST:-aminra-qa-smtp}"
SMTP_PORT="${QA_SMTP_PORT:-2525}"
SMTP_FROM="${QA_SMTP_FROM:-qa-no-reply@aminra.local}"
TEST_EMAIL="${SMTP_LIVE_TEST_EMAIL:-${TEST_ADMIN_EMAIL:-demo-platform-admin@demo.aminra.vn}}"

[[ -n "$KEYCLOAK_ADMIN_PASSWORD" ]] || { echo "ERROR: KEYCLOAK_ADMIN_PASSWORD missing" >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo "ERROR: curl required" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 required" >&2; exit 2; }

validate_action_base() {
  ACTION_BASE="$KEYCLOAK_EMAIL_ACTION_BASE_URL" python3 - <<'PY'
import os
from urllib.parse import urlparse
url = os.environ["ACTION_BASE"].rstrip("/")
parsed = urlparse(url)
host = (parsed.hostname or "").lower()
private_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "keycloak"}
private = parsed.scheme != "https" or parsed.port == 8180 or host in private_hosts or host.endswith(".local")
if private:
    raise SystemExit(f"private-action-base:{url}")
PY
}

if ! validate_action_base; then
  if [[ "${QA_ALLOW_PRIVATE_ACTION_URL:-0}" != "1" ]]; then
    echo "ERROR: refusing to generate VERIFY_EMAIL links from non-public action base: $KEYCLOAK_EMAIL_ACTION_BASE_URL" >&2
    echo "Set KEYCLOAK_EMAIL_ACTION_BASE_URL=https://auth.aminra.org or, for capture-only QA, QA_ALLOW_PRIVATE_ACTION_URL=1." >&2
    exit 2
  fi
  echo "WARN: QA_ALLOW_PRIVATE_ACTION_URL=1 — generated links may be inaccessible outside this machine" >&2
fi

admin_token_json=$(curl -fsS -X POST \
  -d "username=$KEYCLOAK_ADMIN_USER" \
  -d "password=$KEYCLOAK_ADMIN_PASSWORD" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" \
  "$KEYCLOAK_ADMIN_BASE_URL/realms/master/protocol/openid-connect/token")
ADMIN_TOKEN=$(ADMIN_TOKEN_JSON="$admin_token_json" python3 - <<'PY'
import json, os
print(json.loads(os.environ['ADMIN_TOKEN_JSON']).get('access_token',''))
PY
)
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || { echo "ERROR: failed to obtain admin token" >&2; exit 2; }
AUTH_SCHEME="Bearer"
AUTH_HEADER="Authorization: ${AUTH_SCHEME} ${ADMIN_TOKEN}"

echo "[qa-email] admin token obtained: yes"
echo "[qa-email] action_base=$KEYCLOAK_EMAIL_ACTION_BASE_URL"
echo "[qa-email] configuring realm=$KEYCLOAK_REALM smtp_host=$SMTP_HOST smtp_port=$SMTP_PORT from=$SMTP_FROM"

realm_json=$(curl -fsS -H "$AUTH_HEADER" "$KEYCLOAK_ADMIN_BASE_URL/admin/realms/$KEYCLOAK_REALM")
restore_file=$(mktemp)
printf '%s' "$realm_json" > "$restore_file"
cleanup() {
  local exit_code=$?
  if [[ "${QA_KEEP_SMTP_CONFIG:-0}" != "1" && -s "$restore_file" ]]; then
    curl -fsS -X PUT \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      --data @"$restore_file" \
      "$KEYCLOAK_ADMIN_BASE_URL/admin/realms/$KEYCLOAK_REALM" >/dev/null || \
      echo "WARN: failed to restore pre-test Keycloak SMTP config" >&2
    echo "[qa-email] restored pre-test Keycloak SMTP config"
  fi
  rm -f "$restore_file"
  exit "$exit_code"
}
trap cleanup EXIT

updated_realm=$(REALM_JSON="$realm_json" SMTP_HOST="$SMTP_HOST" SMTP_PORT="$SMTP_PORT" SMTP_FROM="$SMTP_FROM" python3 - <<'PY'
import json, os
realm=json.loads(os.environ['REALM_JSON'])
realm['verifyEmail']=True
realm['resetPasswordAllowed']=True
realm['smtpServer']={
    'host': os.environ['SMTP_HOST'],
    'port': os.environ['SMTP_PORT'],
    'from': os.environ['SMTP_FROM'],
    'auth': 'false',
    'ssl': 'false',
    'starttls': 'false',
}
print(json.dumps(realm))
PY
)

curl -fsS -X PUT \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  --data "$updated_realm" \
  "$KEYCLOAK_ADMIN_BASE_URL/admin/realms/$KEYCLOAK_REALM" >/dev/null

echo "[qa-email] realm SMTP configured"

encoded_email=$(TEST_EMAIL="$TEST_EMAIL" python3 - <<'PY'
import os, urllib.parse
print(urllib.parse.quote(os.environ['TEST_EMAIL']))
PY
)
users_json=$(curl -fsS -H "$AUTH_HEADER" "$KEYCLOAK_ADMIN_BASE_URL/admin/realms/$KEYCLOAK_REALM/users?username=$encoded_email&exact=true")
USER_ID=$(USERS_JSON="$users_json" python3 - <<'PY'
import json, os
users=json.loads(os.environ['USERS_JSON'])
print(users[0]['id'] if users else '')
PY
)
[[ -n "$USER_ID" ]] || { echo "ERROR: test user not found: $TEST_EMAIL" >&2; exit 2; }

echo "[qa-email] found test user: $TEST_EMAIL"
echo "[qa-email] triggering VERIFY_EMAIL execute-actions-email"

curl -fsS -X PUT \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  --data '["VERIFY_EMAIL"]' \
  "$KEYCLOAK_EMAIL_ACTION_BASE_URL/admin/realms/$KEYCLOAK_REALM/users/$USER_ID/execute-actions-email" >/dev/null

echo "[qa-email] VERIFY_EMAIL execute-actions-email accepted by Keycloak"
echo "[qa-email] live-send gate complete; inspect SMTP capture logs for SMTP_CAPTURE_BEGIN/END"
