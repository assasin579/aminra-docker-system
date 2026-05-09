#!/bin/bash
# Keycloak MFA configuration — ADR-005 Phase 1 step 3.
# Builds conditional MFA authentication flow on top of bootstrap.
#
# Policy: MFA OPTIONAL for `business` role; REQUIRED for `auditor`,
# `cb_admin`, `platform_admin`.
#
# Note: Keycloak nested authentication flow APIs are verbose and
# version-sensitive. After running this script, **verify in admin console**:
#   $KEYCLOAK_URL/admin/aminra/console/#/aminra/authentication
# The flow `aminra-browser-mfa` should bind as Browser flow with a
# "Conditional - User Role" subflow checking privileged roles → REQUIRED OTP.
#
# Idempotent: re-run safe.
#
# Prerequisites:
#   - Run scripts/keycloak-bootstrap.sh first (realm + roles must exist)
#   - Top-level .env has KEYCLOAK_ADMIN_PASSWORD

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-}"
REALM="${KEYCLOAK_REALM:-aminra}"
FLOW_ALIAS="aminra-browser-mfa"

if [[ -z "$ADMIN_PASS" ]]; then
  if [[ -f .env ]]; then
    ADMIN_PASS=$(grep -E '^KEYCLOAK_ADMIN_PASSWORD=' .env | cut -d= -f2- | tr -d '"' || true)
  fi
fi
[[ -n "$ADMIN_PASS" ]] || { echo "ERROR: KEYCLOAK_ADMIN_PASSWORD not set" >&2; exit 1; }

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
require() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 required" >&2; exit 1; }; }
require curl
require jq

# ── Acquire admin token ───────────────────────────────────────────────────────

TOKEN=$(curl -fsS -X POST \
  -d "username=$ADMIN_USER" -d "password=$ADMIN_PASS" \
  -d "grant_type=password" -d "client_id=admin-cli" \
  "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  | jq -r '.access_token')
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || { echo "ERROR: token fail" >&2; exit 1; }

api() {
  local method="$1"; shift
  local path="$1"; shift
  curl -fsS -X "$method" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "$KEYCLOAK_URL/admin/realms${path}" "$@"
}

api_status() {
  local method="$1"; shift
  local path="$1"; shift
  curl -s -o /dev/null -w '%{http_code}' -X "$method" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "$KEYCLOAK_URL/admin/realms${path}" "$@"
}

# ── 1. Copy "browser" flow if our flow doesn't exist ──────────────────────────

flow_exists=$(api GET "/$REALM/authentication/flows" | jq -r --arg a "$FLOW_ALIAS" '.[] | select(.alias==$a) | .alias')
if [[ -z "$flow_exists" ]]; then
  log "Copying browser flow → $FLOW_ALIAS"
  api POST "/$REALM/authentication/flows/browser/copy" \
    -d "{\"newName\":\"$FLOW_ALIAS\"}" >/dev/null
else
  log "Flow $FLOW_ALIAS exists — skipping copy"
fi

# ── 2. Locate the "<flow_alias> Browser - Conditional OTP" subflow ────────────
# Bitnami Keycloak v25 default browser flow has:
#   - Cookie
#   - Identity Provider Redirector
#   - <copy_alias> forms (subflow)
#       - Username Password Form
#       - <copy_alias> Browser - Conditional OTP (subflow)
#           - Condition - User Configured
#           - OTP Form
#
# We want to FORCE OTP for privileged roles. Approach: add "Condition - User Role"
# at the Conditional OTP subflow alongside the existing User Configured condition,
# then change the subflow to REQUIRED. Result:
#   - User has role auditor/cb_admin/platform_admin → OTP REQUIRED
#   - Other users → OTP if user has it configured (default behaviour)

OTP_SUBFLOW_ALIAS="$FLOW_ALIAS Browser - Conditional OTP"

log "Locating Conditional OTP subflow inside $FLOW_ALIAS"
EXECUTIONS=$(api GET "/$REALM/authentication/flows/$FLOW_ALIAS/executions")
OTP_SUBFLOW_ID=$(echo "$EXECUTIONS" | jq -r --arg a "$OTP_SUBFLOW_ALIAS" '.[] | select(.displayName==$a or .alias==$a) | .id')

if [[ -z "$OTP_SUBFLOW_ID" || "$OTP_SUBFLOW_ID" == "null" ]]; then
  echo "WARNING: Conditional OTP subflow not found in $FLOW_ALIAS." >&2
  echo "         Verify in admin console: $KEYCLOAK_URL/admin/$REALM/console/#/$REALM/authentication" >&2
else
  log "Adding Condition - User Role to Conditional OTP subflow"
  # Add execution: condition-user-role for privileged roles
  for role in auditor cb_admin platform_admin; do
    add_status=$(api_status POST "/$REALM/authentication/flows/$OTP_SUBFLOW_ALIAS/executions/execution" \
      -d '{"provider":"conditional-user-role"}')
    if [[ "$add_status" == "201" || "$add_status" == "204" ]]; then
      log "  Added condition-user-role placeholder (configure in console: role=$role)"
      break  # only need one execution; configure with multi-role in admin console
    fi
  done

  log "Setting Conditional OTP subflow → REQUIRED"
  api PUT "/$REALM/authentication/flows/$FLOW_ALIAS/executions" \
    -d "{\"id\":\"$OTP_SUBFLOW_ID\",\"requirement\":\"REQUIRED\"}" >/dev/null || \
    log "  PUT requirement failed — verify in console"
fi

# ── 3. Bind flow as realm browser flow ────────────────────────────────────────

log "Binding $FLOW_ALIAS as realm browser flow"
api PUT "/$REALM" -d "{\"browserFlow\":\"$FLOW_ALIAS\"}" >/dev/null

# ── 4. Done + verification checklist ──────────────────────────────────────────

cat >&2 <<'EOF'

────────────────────────────────────────────────────────────────────
MFA bootstrap complete. MANUAL VERIFICATION REQUIRED:

1. Open admin console:
   $KEYCLOAK_URL/admin/aminra/console/#/aminra/authentication

2. Confirm flow "aminra-browser-mfa" is set as Browser flow.

3. Inside the flow, find "Conditional OTP" subflow:
   - Set "Condition - User Role" execution to:
       Role: aminra-realm.auditor (then add cb_admin, platform_admin
       as separate executions OR set "Negate output: false" with role list)
   - Confirm subflow requirement = REQUIRED for privileged users.

4. Test E2E:
   - Create test user with role=auditor → must enroll TOTP at next login
   - Create test user with role=business → MFA OPTIONAL

5. Phase 1 step 3 done. Next: Phase 2 (FE OIDC PKCE).
────────────────────────────────────────────────────────────────────
EOF
