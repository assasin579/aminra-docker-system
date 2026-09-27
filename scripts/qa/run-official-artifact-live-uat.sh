#!/usr/bin/env bash
# Run credentialed API UAT for AMINRA document approval -> official artifact flow without printing secrets.
# Acceptance lanes:
# - business uploads a real document with Keycloak token
# - business submits and approves the document
# - approval creates an immutable official artifact
# - official artifact can be listed and downloaded
# - deleting the source document is blocked once the official artifact exists
set -euo pipefail

ROOT="${AMINRA_ROOT:-/home/user/Documents/aminra-docker-system}"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${OUT_DIR:-$ROOT/docs/qa/${STAMP}-official-artifact-live-uat}"
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

if [[ -z "${PW_BIZ_PASSWORD:-${DEMO_PW:-}}" ]]; then
  echo "[official-artifact-uat] QA credentials missing; repairing demo accounts without secrets" | tee "$TERMINAL_DIR/credential-repair.txt"
  scripts/qa/repair-demo-accounts.sh >> "$TERMINAL_DIR/credential-repair.txt" 2>&1
  source_if_exists "$ROOT/.qa/aminra-demo-credentials.env"
fi

export PW_API_BASE="${PW_API_BASE:-http://localhost:8100}"
export KEYCLOAK_TOKEN_URL="${KEYCLOAK_TOKEN_URL:-http://127.0.0.1:8180/realms/${KEYCLOAK_REALM:-aminra}/protocol/openid-connect/token}"
export KEYCLOAK_PUBLIC_PROTO="${KEYCLOAK_PUBLIC_PROTO:-https}"
export KEYCLOAK_PUBLIC_HOST="${KEYCLOAK_PUBLIC_HOST:-auth.aminra.org}"
export KEYCLOAK_PUBLIC_PORT="${KEYCLOAK_PUBLIC_PORT:-443}"
export PW_BIZ_EMAIL="${PW_BIZ_EMAIL:-${DEMO_BUSINESS_EMAIL:-biz-demo-1@demo.aminra.vn}}"
export PW_BIZ_PASSWORD="${PW_BIZ_PASSWORD:-${DEMO_PW:-}}"

missing=()
[[ -n "${PW_BIZ_PASSWORD:-${DEMO_PW:-}}" ]] || missing+=(PW_BIZ_PASSWORD)
if (( ${#missing[@]} > 0 )); then
  append_status "CREDENTIALS" "BLOCKED" "Missing required keys: ${missing[*]}"
  cat > "$REPORT" <<MD
# AMINRA Official Artifact — Credentialed Live API UAT

Verdict: **BLOCKED**

Missing required QA credential keys: ${missing[*]}.

No secret values were printed. For local sandbox, run:

scripts/qa/repair-demo-accounts.sh
MD
  echo "BLOCKED: missing required QA credential keys; report=$REPORT" >&2
  exit 2
fi
append_status "CREDENTIALS" "PASS" "Loaded gitignored QA credential keys; values REDACTED"

# The approval/versioning endpoints intentionally 404 unless document_versioning_v1
# is enabled for the tenant. For local sandbox UAT, enable only the canonical QA
# business tenant selected by PW_BIZ_EMAIL; do not print secrets or blanket-enable
# the feature for every tenant.
if docker compose ps postgres-db >/dev/null 2>&1; then
  if docker compose exec -T postgres-db psql -U "${POSTGRES_USER:-aminra_user}" -d "${POSTGRES_DB:-aminra}" -v ON_ERROR_STOP=1 -v business_email="$PW_BIZ_EMAIL" <<'SQL' > "$TERMINAL_DIR/feature-flag-enable.txt" 2>&1
INSERT INTO tenant_feature_overrides (tenant_id, feature_name, enabled, override_reason)
SELECT tenant_id, 'document_versioning_v1', TRUE, 'official-artifact live UAT sandbox prerequisite'
  FROM users
 WHERE email = :'business_email'
   AND tenant_id IS NOT NULL
ON CONFLICT (tenant_id, feature_name) DO UPDATE
   SET enabled = EXCLUDED.enabled,
       override_reason = EXCLUDED.override_reason,
       updated_at = NOW();
SQL
  then
    if grep -q "INSERT 0 0" "$TERMINAL_DIR/feature-flag-enable.txt"; then
      append_status "FEATURE-FLAG" "FAIL" "No QA business tenant matched PW_BIZ_EMAIL; see evidence/terminal/feature-flag-enable.txt"
    else
      append_status "FEATURE-FLAG" "PASS" "document_versioning_v1 enabled for QA business tenant only"
    fi
  else
    append_status "FEATURE-FLAG" "FAIL" "Could not enable document_versioning_v1; see evidence/terminal/feature-flag-enable.txt"
  fi
else
  append_status "FEATURE-FLAG" "BLOCKED" "docker compose postgres-db unavailable; document_versioning_v1 must already be enabled"
fi

export UAT_EVIDENCE_DIR="$EVIDENCE_DIR"

{
  echo "PW_API_BASE=$PW_API_BASE"
  echo "KEYCLOAK_TOKEN_URL=REDACTED_URL_SHAPE_PRESENT"
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
  npx playwright test e2e/document-official-artifact-live-uat.spec.ts --project=desktop-chromium --reporter=line
) > "$TERMINAL_DIR/playwright-official-artifact-live-uat.txt" 2>&1
playwright_rc=$?
set -e

if [[ "$playwright_rc" -eq 0 ]]; then
  append_status "OFFICIAL-ARTIFACT-UAT" "PASS" "approval created artifact; list/download succeeded; source delete returned 409"
  verdict="GO for local sandbox official-artifact live API UAT"
else
  append_status "OFFICIAL-ARTIFACT-UAT" "FAIL" "Playwright API UAT failed; see evidence/terminal/playwright-official-artifact-live-uat.txt"
  verdict="NO-GO for official-artifact live API UAT"
fi

cat > "$REPORT" <<MD
# AMINRA Official Artifact — Credentialed Live API UAT

Date: $(date -Iseconds)
Repo: $ROOT
Verdict: **$verdict**

## Scope / Acceptance Criteria

- business user uploads a real document with Keycloak token
- business user submits the document for approval
- business user approves the document
- approval creates one immutable official artifact row/file
- official artifact list returns the artifact by source_document_id
- official artifact file endpoint returns the approved bytes
- source document delete is blocked with 409 once official artifact exists
- QA credentials are sourced from gitignored local env only; secret values are never printed

## Evidence

- Status: $STATUS
- Redacted env shape: $TERMINAL_DIR/effective-env-redacted.txt
- Backend health: $TERMINAL_DIR/backend-health.json
- Playwright/API log: $TERMINAL_DIR/playwright-official-artifact-live-uat.txt

## Verdict Boundaries

This lane supports **local sandbox document approval -> official artifact live API evidence**. It does **not** imply production/customer-pilot GO; production readiness still requires secrets/infra review, monitoring alert wiring in the deployed environment, rollback rehearsal, and customer-pilot acceptance.
MD

echo "report=$REPORT"
exit "$playwright_rc"
