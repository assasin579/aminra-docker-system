#!/usr/bin/env bash
# Run credentialed API UAT for AMINRA document management flow without printing secrets.
# Acceptance lanes:
# - anonymous document list is blocked
# - provider upload is forbidden
# - business can upload/list/detail/download/delete a document with a real Keycloak token
set -euo pipefail

ROOT="${AMINRA_ROOT:-/home/user/Documents/aminra-docker-system}"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${OUT_DIR:-$ROOT/docs/qa/${STAMP}-document-management-live-uat}"
EVIDENCE_DIR="$OUT_DIR/evidence"
TERMINAL_DIR="$EVIDENCE_DIR/terminal"
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

source_if_exists "$ROOT/.env"
source_if_exists "$ROOT/.qa/aminra-demo-credentials.env"

if [[ -z "${PW_PROVIDER_PASSWORD:-${PROVIDER_DEMO_PW:-${DEMO_PW:-}}}" || -z "${PW_BIZ_PASSWORD:-${DEMO_PW:-}}" ]]; then
  echo "[document-uat] QA credentials missing; repairing demo accounts without secrets" | tee "$TERMINAL_DIR/credential-repair.txt"
  scripts/qa/repair-demo-accounts.sh >> "$TERMINAL_DIR/credential-repair.txt" 2>&1
  source_if_exists "$ROOT/.qa/aminra-demo-credentials.env"
fi

missing=()
[[ -n "${PW_PROVIDER_PASSWORD:-${PROVIDER_DEMO_PW:-${DEMO_PW:-}}}" ]] || missing+=(PW_PROVIDER_PASSWORD)
[[ -n "${PW_BIZ_PASSWORD:-${DEMO_PW:-}}" ]] || missing+=(PW_BIZ_PASSWORD)
if (( ${#missing[@]} > 0 )); then
  append_status "CREDENTIALS" "BLOCKED" "Missing required keys: ${missing[*]}"
  cat > "$REPORT" <<MD
# AMINRA Document Management — Credentialed Live API UAT

Verdict: **BLOCKED**

Missing required QA credential keys: ${missing[*]}.

No secret values were printed. For local sandbox, run:

scripts/qa/repair-demo-accounts.sh
MD
  echo "BLOCKED: missing required QA credential keys; report=$REPORT" >&2
  exit 2
fi
append_status "CREDENTIALS" "PASS" "Loaded gitignored QA credential keys; values REDACTED"

export PW_API_BASE="${PW_API_BASE:-http://localhost:8100}"
export KEYCLOAK_TOKEN_URL="${KEYCLOAK_TOKEN_URL:-http://127.0.0.1:8180/realms/${KEYCLOAK_REALM:-aminra}/protocol/openid-connect/token}"
export KEYCLOAK_PUBLIC_PROTO="${KEYCLOAK_PUBLIC_PROTO:-https}"
export KEYCLOAK_PUBLIC_HOST="${KEYCLOAK_PUBLIC_HOST:-auth.aminra.org}"
export KEYCLOAK_PUBLIC_PORT="${KEYCLOAK_PUBLIC_PORT:-443}"
export PW_PROVIDER_EMAIL="${PW_PROVIDER_EMAIL:-cb-demo@demo.aminra.vn}"
export PW_PROVIDER_PASSWORD="${PW_PROVIDER_PASSWORD:-${PROVIDER_DEMO_PW:-${DEMO_PW:-}}}"
export PW_BIZ_EMAIL="${PW_BIZ_EMAIL:-${DEMO_BUSINESS_EMAIL:-biz-demo-1@demo.aminra.vn}}"
export PW_BIZ_PASSWORD="${PW_BIZ_PASSWORD:-${DEMO_PW:-}}"

{
  echo "PW_API_BASE=$PW_API_BASE"
  echo "KEYCLOAK_TOKEN_URL=REDACTED_URL_SHAPE_PRESENT"
  echo "PW_PROVIDER_EMAIL=$PW_PROVIDER_EMAIL"
  echo "PW_PROVIDER_PASSWORD=REDACTED"
  echo "PW_BIZ_EMAIL=$PW_BIZ_EMAIL"
  echo "PW_BIZ_PASSWORD=REDACTED"
} > "$TERMINAL_DIR/effective-env-redacted.txt"

if curl -fsS "$PW_API_BASE/health" > "$TERMINAL_DIR/backend-health.json"; then
  append_status "RUNTIME-BACKEND" "PASS" "Backend health responded"
else
  append_status "RUNTIME-BACKEND" "FAIL" "Backend health failed"
fi

set +e
(
  cd frontend/aminra-web
  npx playwright test e2e/document-management-live-uat.spec.ts --project=desktop-chromium --reporter=line
) > "$TERMINAL_DIR/playwright-document-management.txt" 2>&1
playwright_rc=$?
set -e

if [[ "$playwright_rc" -eq 0 ]]; then
  append_status "API-UAT" "PASS" "anonymous blocked; provider upload forbidden; business upload/list/detail/download/delete succeeded"
  verdict="GO for local sandbox document-management live API UAT"
else
  append_status "API-UAT" "FAIL" "Playwright API UAT failed; see evidence/terminal/playwright-document-management.txt"
  verdict="NO-GO for document-management live API UAT"
fi

cat > "$REPORT" <<MD
# AMINRA Document Management — Credentialed Live API UAT

Date: $(date -Iseconds)
Repo: $ROOT
Verdict: **$verdict**

## Scope / Acceptance Criteria

- anonymous document list is blocked
- provider upload is forbidden
- business user uploads a real document with Keycloak token
- uploaded document appears in list/detail
- file endpoint returns uploaded content
- delete endpoint cleans up the UAT document
- QA credentials are sourced from gitignored local env only; secret values are never printed

## Evidence

- Status: $STATUS
- Redacted env shape: $TERMINAL_DIR/effective-env-redacted.txt
- Backend health: $TERMINAL_DIR/backend-health.json
- Playwright/API log: $TERMINAL_DIR/playwright-document-management.txt

## Verdict Boundaries

This lane supports **local sandbox document-management flow evidence** for the covered API path. It does **not** imply production/customer-pilot GO; SMTP/customer onboarding, edge/CDN SLO, dependency/security backlog, browser UI polish, mobile/cross-browser coverage, and broader approval/version workflow evidence remain separate gates.
MD

echo "report=$REPORT"
exit "$playwright_rc"
