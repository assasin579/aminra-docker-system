#!/usr/bin/env bash
# AMINRA Gate 1 unsupervised customer onboarding QA runner.
# Generates durable evidence for customer-facing onboarding gates without printing secrets.
set -uo pipefail

ROOT_DIR="${AMINRA_ROOT:-/home/user/Documents/aminra-docker-system}"
cd "$ROOT_DIR" || exit 2

RUN_ID="${RUN_ID:-20260917-gate1-onboarding}"
OUT_DIR="${OUT_DIR:-docs/qa/${RUN_ID}}"
TERM_DIR="$OUT_DIR/evidence/terminal"
RAW_DIR="$OUT_DIR/evidence/raw"
STATUS_FILE="$OUT_DIR/status.tsv"
REPORT_FILE="$OUT_DIR/report.md"
MATRIX_FILE="$OUT_DIR/acceptance-matrix.md"
mkdir -p "$TERM_DIR" "$RAW_DIR"

if [[ ! -f "$STATUS_FILE" ]]; then
  printf 'domain\tstatus\tstep\tevidence\tnote\n' > "$STATUS_FILE"
fi

# Load runtime and QA credential variable names/values for commands that need them.
# Do not echo env values; tracing must stay disabled.
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

export PW_BASE_URL="${PW_BASE_URL:-https://aminra.org}"
export NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED="${NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED:-true}"
export TEST_ADMIN_EMAIL="${TEST_ADMIN_EMAIL:-${ADMIN_DEMO_EMAIL:-demo-platform-admin@demo.aminra.vn}}"
export TEST_ADMIN_PASSWORD="${TEST_ADMIN_PASSWORD:-${ADMIN_DEMO_PW:-}}"

step_no=0
pass_count=0
fail_count=0
warn_count=0
blocked_count=0

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-//; s/-$//'
}

redact_log() {
  sed -E \
    -e 's/(password|PASSWORD|Password)[=:][^[:space:]]+/\1=[REDACTED]/g' \
    -e 's/(token|TOKEN|Token)[=:][^[:space:]]+/\1=[REDACTED]/g' \
    -e 's/(secret|SECRET|Secret)[=:][^[:space:]]+/\1=[REDACTED]/g' \
    -e 's/(Authorization: Bearer )[A-Za-z0-9._~+\/-]+/\1[REDACTED]/g'
}

append_status() {
  local domain="$1" status="$2" step="$3" evidence="$4" note="${5:-}"
  printf '%s\t%s\t%s\t%s\t%s\n' "$domain" "$status" "$step" "$evidence" "$note" >> "$STATUS_FILE"
  case "$status" in
    PASS) pass_count=$((pass_count+1));;
    FAIL) fail_count=$((fail_count+1));;
    WARN) warn_count=$((warn_count+1));;
    BLOCKED|DEFERRED) blocked_count=$((blocked_count+1));;
  esac
}

run_step() {
  local domain="$1" gate="$2" cmd="$3" note="${4:-}"
  step_no=$((step_no+1))
  local log="$TERM_DIR/$(printf '%03d-%s.txt' "$step_no" "$(slugify "$domain-$gate")")"
  {
    echo "# Domain: $domain"
    echo "# Gate: $gate"
    echo "# Started: $(date -Is)"
    echo "# Command: $cmd"
    echo
  } > "$log"
  echo "[$(date +%H:%M:%S)] RUN $domain :: $gate"
  ( eval "$cmd" ) 2>&1 | redact_log >> "$log"
  local ec=${PIPESTATUS[0]}
  {
    echo
    echo "# Finished: $(date -Is)"
    echo "# Exit code: $ec"
  } >> "$log"
  if [[ $ec -eq 0 ]]; then
    append_status "$domain" "PASS" "$gate" "$log" "$note"
  else
    append_status "$domain" "FAIL" "$gate" "$log" "exit_code=$ec ${note}"
  fi
  return 0
}

mark_blocked() {
  local domain="$1" gate="$2" note="$3"
  step_no=$((step_no+1))
  local log="$TERM_DIR/$(printf '%03d-%s-blocked.txt' "$step_no" "$(slugify "$domain-$gate")")"
  { echo "# Domain: $domain"; echo "# Gate: $gate"; echo "# Status: BLOCKED"; echo "$note"; } > "$log"
  append_status "$domain" "BLOCKED" "$gate" "$log" "$note"
}

write_report() {
  cat > "$REPORT_FILE" <<REPORT
# AMINRA Gate 1 — Unsupervised Customer Onboarding Automated QA

Date: $(date -Is)
Public base URL: ${PW_BASE_URL}
Evidence root: ${OUT_DIR}
Acceptance matrix: ${MATRIX_FILE}
Status ledger: ${STATUS_FILE}

## Automated verdict

- PASS rows: ${pass_count}
- FAIL rows: ${fail_count}
- WARN/BLOCKED/DEFERRED rows: $((warn_count + blocked_count))

Final verdict rule:
- PASS only if every required P0/P1 Gate 1 automated row is PASS and full desktop Chromium has 0 failed.
- FAIL/NO-GO if any required Gate 1 row is FAIL.
- BLOCKED if email/credential/external dependency prevents verification.

## Gate mapping

- G1-RUNTIME: runtime health and public login availability.
- G1-EMAIL: live/canonical email verification and password-reset dependency checks.
- G1-SESSION: login, logout, Keycloak/OIDC, account-switch/session isolation.
- G1-BUSINESS: business first-value flow and supply-chain write contracts.
- G1-PROVIDER: provider/CB first-value certificate/authority flow.
- G1-AUDITOR: auditor/role-boundary backend smoke.
- G1-ERROR: invalid input and error UX regressions.
- G1-OUTPUT: public/demo artifact correctness.
- G1-FULL-CHROMIUM: full desktop browser regression matrix.

## Current recommendation

$(if [[ $fail_count -eq 0 && $blocked_count -eq 0 ]]; then echo "PASS candidate — review evidence and skipped tests before customer handoff."; else echo "NO-GO/PARTIAL — inspect FAIL/BLOCKED rows in status.tsv."; fi)
REPORT
}

# Ensure local QA SMTP capture is available for Keycloak live-send proof.
if ! docker ps --format '{{.Names}}' | grep -qx 'aminra-qa-smtp'; then
  docker rm -f aminra-qa-smtp >/dev/null 2>&1 || true
  docker run -d --name aminra-qa-smtp --network aminra-docker-system_app-network \
    -v "$ROOT_DIR/scripts/qa/capture_smtp.py:/capture_smtp.py:ro" \
    aminra-docker-system-aminra-backend python /capture_smtp.py >/dev/null
fi

# Ensure artifacts exist.
if [[ ! -f "$MATRIX_FILE" ]]; then
  mark_blocked "inventory" "G1-INVENTORY acceptance matrix" "acceptance-matrix.md missing; run inventory extraction first"
fi

run_step "runtime" "G1-RUNTIME health public login" \
  "docker compose ps aminra-backend aminra-frontend postgres-db qdrant-db redis keycloak && curl -fsS http://127.0.0.1:8100/health && curl -fsS -o /dev/null -w 'public_business_login=%{http_code}\\n' '${PW_BASE_URL}/business/login'"

# Email is mandatory for unsupervised onboarding. Run when helper is available; otherwise block clearly.
if [[ -x scripts/qa/keycloak-email-live-send-check.sh ]]; then
  run_step "email" "G1-EMAIL verify-email live-send" "bash scripts/qa/keycloak-email-live-send-check.sh" "must prove canonical verification email path"
else
  mark_blocked "email" "G1-EMAIL verify-email live-send" "scripts/qa/keycloak-email-live-send-check.sh missing or not executable"
fi

run_step "session" "G1-SESSION login oidc account isolation" \
  "cd frontend/aminra-web && npx playwright test e2e/keycloak/02-login-ui-flow.spec.ts e2e/22-token-isolation.spec.ts e2e/23-cross-context-logout.spec.ts --project=desktop-chromium --reporter=line"

run_step "business" "G1-BUSINESS first value and supply chain contracts" \
  "cd frontend/aminra-web && npx playwright test e2e/03-business-flow.spec.ts e2e/10-supply-chain.spec.ts e2e/40-supply-chain-create-contracts.spec.ts --project=desktop-chromium --reporter=line"

run_step "provider" "G1-PROVIDER certificate lifecycle provider flow" \
  "cd frontend/aminra-web && npx playwright test e2e/04-provider-flow.spec.ts e2e/14-cuj-cert-lifecycle.spec.ts e2e/18-mvp-demo-provider-admin.spec.ts --project=desktop-chromium --reporter=line"

run_step "auditor" "G1-AUDITOR live role boundary smoke" \
  "cid=\$(docker compose ps -q aminra-backend); docker cp backend/tests/. \"\$cid\":/app/tests; docker cp .qa/aminra-demo-credentials.env \"\$cid\":/tmp/aminra-demo-credentials.env; docker compose exec -T aminra-backend sh -lc 'set -a; . /tmp/aminra-demo-credentials.env; set +a; pytest tests/test_role_boundaries_live_smoke.py tests/test_unauth_route_boundaries.py -q'"

run_step "error" "G1-ERROR invalid input and error UX" \
  "cd frontend/aminra-web && npx playwright test e2e/26-register-validation.spec.ts e2e/36-batch6-parse-api-error.spec.ts --project=desktop-chromium --reporter=line"

run_step "output" "G1-OUTPUT public artifact correctness" \
  "cd frontend/aminra-web && npx playwright test e2e/17-mvp-demo-public.spec.ts e2e/38-demo-spine-keycloak.spec.ts --project=desktop-chromium --reporter=line"

run_step "frontend" "G1-FRONTEND lint build contracts" \
  "cd frontend/aminra-web && npm run lint && npm run build && npm test -- --run"

# The full browser matrix is long and includes destructive/negative auth specs.
# Reset canonical demo accounts immediately before it so the customer-facing
# demo-spine tests do not inherit credential drift from earlier focused lanes.
if [[ -x scripts/qa/repair-demo-accounts.sh ]]; then
  run_step "accounts" "G1-ACCOUNTS repair before full browser matrix" \
    "bash scripts/qa/repair-demo-accounts.sh"
  if [[ -f .qa/aminra-demo-credentials.env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .qa/aminra-demo-credentials.env
    set +a
  fi
fi

run_step "browser" "G1-FULL-CHROMIUM full desktop matrix" \
  "cd frontend/aminra-web && npx playwright test --project=desktop-chromium --reporter=line"

write_report

if [[ $fail_count -gt 0 || $blocked_count -gt 0 ]]; then
  exit 1
fi
exit 0
