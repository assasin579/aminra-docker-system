#!/usr/bin/env bash
# Run credentialed browser UAT for module activation request flow without secrets.
# Acceptance lanes:
# - business locked-route CTA creates request
# - admin queue shows SLA/notification cues
# - admin rejects QA request for cleanup
set -euo pipefail

ROOT="${AMINRA_ROOT:-/home/user/Documents/aminra-docker-system}"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${OUT_DIR:-$ROOT/docs/qa/${STAMP}-activation-request-browser-uat}"
EVIDENCE_DIR="$OUT_DIR/evidence"
TERMINAL_DIR="$OUT_DIR/evidence/terminal"
mkdir -p "$EVIDENCE_DIR" "$TERMINAL_DIR"
STATUS="$OUT_DIR/status.tsv"
REPORT="$OUT_DIR/report.md"
: > "$STATUS"

append_status() {
  local id="$1" status="$2" note="$3"
  printf '%s\t%s\t%s\n' "$id" "$status" "$note" >> "$STATUS"
}

source_if_exists() {
  local file="$1"
  if [[ -f "$file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
  fi
}

# Load configured secrets locally only; never echo values. Values remain REDACTED in logs/report.
source_if_exists "$ROOT/.env"
source_if_exists "$ROOT/.qa/aminra-demo-credentials.env"

if [[ -z "${PW_BIZ_PASSWORD:-${DEMO_PW:-}}" || -z "${TEST_ADMIN_PASSWORD:-}" ]]; then
  echo "[module-activation-uat] QA credentials missing; repairing demo accounts without secrets" | tee "$TERMINAL_DIR/credential-repair.txt"
  scripts/qa/repair-demo-accounts.sh >> "$TERMINAL_DIR/credential-repair.txt" 2>&1
  source_if_exists "$ROOT/.qa/aminra-demo-credentials.env"
fi

missing=()
[[ -n "${PW_BIZ_PASSWORD:-${DEMO_PW:-}}" ]] || missing+=(PW_BIZ_PASSWORD)
[[ -n "${TEST_ADMIN_EMAIL:-}" ]] || missing+=(TEST_ADMIN_EMAIL)
[[ -n "${TEST_ADMIN_PASSWORD:-}" ]] || missing+=(TEST_ADMIN_PASSWORD)
if (( ${#missing[@]} > 0 )); then
  append_status "CREDENTIALS" "BLOCKED" "Missing required keys: ${missing[*]}"
  cat > "$REPORT" <<MD
# Module Activation Browser UAT

Verdict: **BLOCKED**

Missing required QA credential keys: ${missing[*]}.

No secret values were printed. If this is a local sandbox, run:

scripts/qa/repair-demo-accounts.sh
MD
  echo "BLOCKED: missing required QA credential keys; report=$REPORT" >&2
  exit 2
fi
append_status "CREDENTIALS" "PASS" "Loaded gitignored QA credential keys; values REDACTED"

export PW_BASE_URL="${PW_BASE_URL:-http://localhost:3100}"
export PW_API_BASE="${PW_API_BASE:-http://localhost:8100}"
export KEYCLOAK_TOKEN_URL="${KEYCLOAK_TOKEN_URL:-http://127.0.0.1:8180/realms/${KEYCLOAK_REALM:-aminra}/protocol/openid-connect/token}"
export KEYCLOAK_PUBLIC_PROTO="${KEYCLOAK_PUBLIC_PROTO:-https}"
export KEYCLOAK_PUBLIC_HOST="${KEYCLOAK_PUBLIC_HOST:-auth.aminra.org}"
export KEYCLOAK_PUBLIC_PORT="${KEYCLOAK_PUBLIC_PORT:-443}"
export UAT_EVIDENCE_DIR="$EVIDENCE_DIR"
export PW_BIZ_PASSWORD="${PW_BIZ_PASSWORD:-${DEMO_PW:-}}"
export TEST_ADMIN_PASSWORD="${TEST_ADMIN_PASSWORD:-}"
export TEST_ADMIN_EMAIL="${TEST_ADMIN_EMAIL:-demo-platform-admin@demo.aminra.vn}"

{
  echo "PW_BASE_URL=$PW_BASE_URL"
  echo "PW_API_BASE=$PW_API_BASE"
  echo "KEYCLOAK_TOKEN_URL=REDACTED_URL_SHAPE_PRESENT"
  echo "PW_BIZ_PASSWORD=REDACTED"
  echo "TEST_ADMIN_EMAIL=$TEST_ADMIN_EMAIL"
  echo "TEST_ADMIN_PASSWORD=REDACTED"
} > "$TERMINAL_DIR/effective-env-redacted.txt"

if curl -fsS "$PW_API_BASE/health" > "$TERMINAL_DIR/backend-health.json"; then
  append_status "RUNTIME-BACKEND" "PASS" "Backend health responded"
else
  append_status "RUNTIME-BACKEND" "FAIL" "Backend health failed"
fi
if curl -fsS -o /dev/null -w '%{http_code}\n' "$PW_BASE_URL/health" > "$TERMINAL_DIR/frontend-health.txt"; then
  append_status "RUNTIME-FRONTEND" "PASS" "Frontend health responded"
else
  append_status "RUNTIME-FRONTEND" "FAIL" "Frontend health failed"
fi

set +e
(
  cd frontend/aminra-web
  npx playwright test e2e/module-guard-live-uat.spec.ts --project=desktop-chromium --reporter=line
) > "$TERMINAL_DIR/playwright-module-activation.txt" 2>&1
playwright_rc=$?
set -e

if [[ "$playwright_rc" -eq 0 ]]; then
  append_status "BROWSER-UAT" "PASS" "business locked-route CTA creates request; admin queue shows SLA/notification cues; admin rejects QA request for cleanup"
  verdict="GO for local sandbox credentialed browser UAT"
else
  append_status "BROWSER-UAT" "FAIL" "Playwright failed; see evidence/terminal/playwright-module-activation.txt"
  verdict="NO-GO for credentialed browser UAT"
fi

cat > "$REPORT" <<MD
# AMINRA Module Activation Request — Credentialed Browser UAT

Date: $(date -Iseconds)
Repo: $ROOT
Verdict: **$verdict**

## Scope / Acceptance Criteria

- business locked-route CTA creates request
- admin queue shows SLA/notification cues
- admin rejects QA request for cleanup
- QA credentials are sourced from gitignored local env only; secret values are never printed

## Evidence

- Status: $STATUS
- Redacted env shape: $TERMINAL_DIR/effective-env-redacted.txt
- Playwright log: $TERMINAL_DIR/playwright-module-activation.txt
- Screenshots: $EVIDENCE_DIR/

## Credential Safety

Credential values are intentionally **REDACTED**. The runner sources .env and .qa/aminra-demo-credentials.env; if required QA keys are missing, it runs scripts/qa/repair-demo-accounts.sh which writes mode-600 gitignored credentials.
MD

echo "report=$REPORT"
exit "$playwright_rc"
