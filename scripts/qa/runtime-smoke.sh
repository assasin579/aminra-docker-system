#!/usr/bin/env bash
# AMINRA read-only runtime smoke.
# Purpose: catch deploy/config drift without mutating DB or restarting services.
# Exit 0 = no FAIL checks. WARN still needs human review before demo.

set -uo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8100}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3100}"
KEYCLOAK_URL="${KEYCLOAK_URL:-https://auth.silvergem.org}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-aminra}"
PUBLIC_URLS="${AMINRA_SMOKE_PUBLIC_URLS:-https://dev-web.silvergem.org}"
# Canonical public sandbox demo URL is dev-web.silvergem.org. Do not add
# fe.silvergem.org to defaults while it is a known legacy/hostname-drift path;
# pass it explicitly via AMINRA_SMOKE_PUBLIC_URLS only when testing drift.
LOG_SCAN_MINUTES="${LOG_SCAN_MINUTES:-30}"

PASS=0; WARN=0; FAIL=0
FAILURES=()
WARNINGS=()
TMP_PREFIX="/tmp/aminra-smoke-$$"
trap 'rm -f "${TMP_PREFIX}"*' EXIT

ok() { printf '✓ %s\n' "$1"; PASS=$((PASS+1)); }
warn() { printf '⚠ %s\n' "$1"; WARN=$((WARN+1)); WARNINGS+=("$1"); }
fail() { printf '✗ %s\n' "$1"; FAIL=$((FAIL+1)); FAILURES+=("$1"); }
section() { printf '\n## %s\n' "$1"; }
http_code() { curl -k -L -sS --max-time 12 -o "${TMP_PREFIX}-body" -w '%{http_code}' "$1" 2>"${TMP_PREFIX}-curl"; }

section 'Environment'
printf 'backend: %s\nfrontend: %s\nkeycloak: %s/realms/%s\npublic urls: %s\n' "$BACKEND_URL" "$FRONTEND_URL" "$KEYCLOAK_URL" "$KEYCLOAK_REALM" "$PUBLIC_URLS"

section 'Docker service state'
if command -v docker >/dev/null 2>&1 && docker compose ps >"${TMP_PREFIX}-compose" 2>"${TMP_PREFIX}-compose-err"; then
  if grep -E 'aminra-backend|aminra-frontend|keycloak|postgres' "${TMP_PREFIX}-compose" >/dev/null; then
    ok 'docker compose service list is readable and AMINRA services are present'
  else
    warn 'docker compose readable, but expected AMINRA service names were not found in output'
  fi
else
  warn 'docker compose ps unavailable from this shell; skipping container state check'
fi

section 'Backend capability'
code=$(http_code "$BACKEND_URL/health")
if [ "$code" = '200' ]; then
  ok "backend /health returns 200"
  health_status=$(python3 - "${TMP_PREFIX}-body" <<'PY'
import json, sys
p=sys.argv[1]
try:
    d=json.load(open(p))
except Exception as e:
    print(f'WARN_HEALTH_JSON={e}')
    raise SystemExit(0)
for key in ('database','qdrant'):
    print(f'HEALTH_{key.upper()}={d.get(key)}')
PY
)
  printf '%s\n' "$health_status"
  db_status=$(printf '%s\n' "$health_status" | awk -F= '/^HEALTH_DATABASE=/{print $2}')
  qdrant_status=$(printf '%s\n' "$health_status" | awk -F= '/^HEALTH_QDRANT=/{print $2}')
  if [ "$db_status" = 'connected' ]; then
    ok 'backend reports database=connected'
  else
    fail "backend database health is '${db_status:-unknown}'"
  fi
  if [ "$qdrant_status" = 'connected' ]; then
    ok 'backend reports qdrant=connected'
  else
    warn "backend qdrant health is '${qdrant_status:-unknown}' — RAG may degrade"
  fi
else
  fail "backend /health returned HTTP $code"
fi

section 'Frontend local/public pages'
for url in "$FRONTEND_URL" "$FRONTEND_URL/landing" "$FRONTEND_URL/privacy" "$FRONTEND_URL/terms"; do
  code=$(http_code "$url")
  case "$code" in
    200) ok "$url returns 200" ;;
    30*) warn "$url redirects with HTTP $code" ;;
    *) fail "$url returned HTTP $code" ;;
  esac
done

section 'Public hostnames'
for base in $PUBLIC_URLS; do
  code=$(http_code "$base")
  if [ "$code" = '200' ]; then
    ok "$base returns 200"
  elif [ "$code" = '502' ]; then
    fail "$base returns 502 (public tunnel/hostname drift or origin unavailable)"
  else
    warn "$base returned HTTP $code"
  fi
done

section 'Keycloak OIDC discovery'
discovery="$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/.well-known/openid-configuration"
code=$(http_code "$discovery")
if [ "$code" = '200' ]; then
  ok 'Keycloak OIDC discovery returns 200'
else
  fail "Keycloak OIDC discovery returned HTTP $code"
fi

section 'Landing CTA auth redirect contract'
code=$(curl -k -sS --max-time 12 -o "${TMP_PREFIX}-landing" -w '%{http_code}' "$FRONTEND_URL/landing" 2>"${TMP_PREFIX}-curl" || true)
if [ "$code" = '200' ]; then
  if grep -E 'business/register|keycloak|openid|oidc|auth/callback' "${TMP_PREFIX}-landing" >/dev/null; then
    ok 'landing page contains auth/registration contract markers'
  else
    warn 'landing page 200 but no obvious auth/registration marker in HTML; client bundle may still work, browser smoke needed'
  fi
else
  fail "landing page unavailable for CTA contract check (HTTP $code)"
fi

section 'Fresh log scan'
if command -v docker >/dev/null 2>&1; then
  if docker compose logs --since "${LOG_SCAN_MINUTES}m" aminra-backend aminra-frontend keycloak >"${TMP_PREFIX}-logs" 2>"${TMP_PREFIX}-logs-err"; then
    if grep -Ei 'SEND_VERIFY_EMAIL_ERROR|invalid_redirect_uri|Traceback|Unhandled Runtime Error|ECONNREFUSED|permission denied|foreignkeyviolation|cross.?tenant' "${TMP_PREFIX}-logs" >"${TMP_PREFIX}-log-hits"; then
      warn 'fresh logs contain suspicious errors; rerun with LOG_SCAN_MINUTES set and inspect docker compose logs'
    else
      ok "no high-signal error patterns in last ${LOG_SCAN_MINUTES}m logs"
    fi
  else
    warn 'docker compose logs unavailable; skipping fresh log scan'
  fi
else
  warn 'docker command unavailable; skipping fresh log scan'
fi

section 'Summary'
printf 'PASS=%d WARN=%d FAIL=%d\n' "$PASS" "$WARN" "$FAIL"
if [ "$WARN" -gt 0 ]; then
  printf '\nWarnings:\n'
  for w in "${WARNINGS[@]}"; do printf -- '- %s\n' "$w"; done
fi
if [ "$FAIL" -gt 0 ]; then
  printf '\nFailures:\n'
  for f in "${FAILURES[@]}"; do printf -- '- %s\n' "$f"; done
  exit 1
fi
exit 0
