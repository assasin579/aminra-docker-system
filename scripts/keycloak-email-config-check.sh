#!/usr/bin/env bash
# Read-only Keycloak email/verification config check.
# Does not print SMTP password; only reports whether a password is set.

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-}"
REALM="${KEYCLOAK_REALM:-aminra}"

if [[ -z "$ADMIN_PASS" && -f .env ]]; then
  ADMIN_PASS=$(python3 - <<'PY'
from pathlib import Path
key='KEYCLOAK_ADMIN_PASSWORD'
for line in Path('.env').read_text(errors='ignore').splitlines():
    if line.startswith(key+'='):
        print(line.split('=',1)[1].strip().strip('"'))
PY
)
fi
if [[ -z "$ADMIN_PASS" ]]; then
  echo "ERROR: KEYCLOAK_ADMIN_PASSWORD not set (env or .env file)" >&2
  exit 2
fi

command -v curl >/dev/null 2>&1 || { echo "ERROR: curl required" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 required" >&2; exit 2; }

TOKEN_JSON=$(curl -fsS -X POST \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASS" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" \
  "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token")
TOKEN=$(TOKEN_JSON="$TOKEN_JSON" python3 - <<'PY'
import json, os
print(json.loads(os.environ['TOKEN_JSON']).get('access_token',''))
PY
)
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || { echo "ERROR: Failed to get admin token" >&2; exit 2; }

REALM_JSON=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$KEYCLOAK_URL/admin/realms/$REALM")
REALM_JSON="$REALM_JSON" python3 - <<'PY'
import json, os, sys
realm=json.loads(os.environ['REALM_JSON'])
smtp=realm.get('smtpServer') or {}
fail=0

def ok(msg): print('✓ '+msg)
def warn(msg): print('⚠ '+msg)
def bad(msg):
    global fail
    print('✗ '+msg)
    fail += 1

if realm.get('verifyEmail') is True: ok('verifyEmail enabled')
else: bad('verifyEmail is not enabled')
if realm.get('resetPasswordAllowed') is True: ok('resetPasswordAllowed enabled')
else: bad('resetPasswordAllowed is not enabled')

host=smtp.get('host') or ''
from_addr=smtp.get('from') or ''
port=smtp.get('port') or ''
starttls=str(smtp.get('starttls','')).lower()
ssl=str(smtp.get('ssl','')).lower()
auth=str(smtp.get('auth','')).lower()
user=smtp.get('user') or ''
password=smtp.get('password') or ''

if host: ok(f'SMTP host configured: {host}')
else: bad('SMTP host missing')
if from_addr: ok(f'SMTP from configured: {from_addr}')
else: bad('SMTP from missing')
if port: ok(f'SMTP port configured: {port}')
else: warn('SMTP port missing (Keycloak may default unexpectedly)')
if starttls == 'true' or ssl == 'true': ok(f'SMTP transport security enabled (starttls={starttls} ssl={ssl})')
else: bad('SMTP transport security not enabled')
if auth == 'true':
    if user: ok('SMTP auth user configured')
    else: bad('SMTP auth enabled but user missing')
    if password: ok('SMTP auth password is set')
    else: bad('SMTP auth enabled but password missing')
else:
    warn('SMTP auth disabled — acceptable only for trusted internal relay')

if fail == 0:
    print('✅ Keycloak email verification config is production-ready (delivery still depends on provider reachability/SPF/DKIM).')
else:
    print(f'❌ Keycloak email verification config has {fail} blocker(s).')
sys.exit(fail)
PY
