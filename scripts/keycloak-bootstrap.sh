#!/bin/bash
# Keycloak realm + clients + roles bootstrap — ADR-005 Phase 1.
# Idempotent: safe to re-run. Checks before create.
#
# Prerequisites:
#   - Keycloak service healthy (docker compose ps keycloak)
#   - Top-level .env has KEYCLOAK_ADMIN_PASSWORD
#
# Usage:
#   bash scripts/keycloak-bootstrap.sh
#
# What it does:
#   1. Acquire admin token from master realm
#   2. Create realm "aminra" if missing
#   3. Configure realm token expiry + password policy
#   4. Create 2 clients: aminra-frontend (SPA PKCE) + aminra-backend (resource server)
#   5. Create 4 realm roles: business, auditor, cb_admin, platform_admin
#   6. Configure required actions: VERIFY_EMAIL, CONFIGURE_TOTP (for privileged roles)

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-}"
REALM="${KEYCLOAK_REALM:-aminra}"

if [[ -z "$ADMIN_PASS" ]]; then
  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    ADMIN_PASS=$(grep -E '^KEYCLOAK_ADMIN_PASSWORD=' .env | cut -d= -f2- | tr -d '"' || true)
  fi
fi
if [[ -z "$ADMIN_PASS" ]]; then
  echo "ERROR: KEYCLOAK_ADMIN_PASSWORD not set (env or .env file)" >&2
  exit 1
fi

# ── Helpers ────────────────────────────────────────────────────────────────────

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

require() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 required" >&2; exit 1; }; }
require curl
require jq

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

# ── 1. Wait for Keycloak ready + acquire token ────────────────────────────────

log "Waiting for Keycloak at $KEYCLOAK_URL..."
for _ in $(seq 1 60); do
  if curl -fsS "$KEYCLOAK_URL/realms/master" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

log "Acquiring admin token..."
TOKEN=$(curl -fsS -X POST \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASS" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" \
  "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  | jq -r '.access_token')

[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || { echo "ERROR: Failed to get admin token" >&2; exit 1; }

# ── 2. Create realm if missing ────────────────────────────────────────────────

REALM_STATUS=$(api_status GET "/$REALM")
if [[ "$REALM_STATUS" == "404" ]]; then
  log "Creating realm: $REALM"
  api POST "" -d @- <<EOF
{
  "realm": "$REALM",
  "enabled": true,
  "displayName": "AMINRA",
  "displayNameHtml": "<b>AMINRA</b>",
  "registrationAllowed": false,
  "loginWithEmailAllowed": true,
  "duplicateEmailsAllowed": false,
  "resetPasswordAllowed": true,
  "verifyEmail": true,
  "loginTheme": "keycloak",
  "internationalizationEnabled": true,
  "supportedLocales": ["vi", "en"],
  "defaultLocale": "vi"
}
EOF
elif [[ "$REALM_STATUS" == "200" ]]; then
  log "Realm $REALM already exists — skipping create"
else
  echo "ERROR: Unexpected realm status: $REALM_STATUS" >&2
  exit 1
fi

# ── 3. Configure realm token settings + password policy ───────────────────────

log "Updating realm token expiry + password policy"
api PUT "/$REALM" -d @- <<'EOF'
{
  "accessTokenLifespan": 900,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 28800,
  "offlineSessionIdleTimeout": 604800,
  "passwordPolicy": "length(12) and digits(1) and upperCase(1) and lowerCase(1) and specialChars(1) and notUsername(undefined) and notEmail(undefined) and passwordHistory(5) and forceExpiredPasswordChange(180) and hashIterations(210000)",
  "bruteForceProtected": true,
  "permanentLockout": false,
  "maxFailureWaitSeconds": 900,
  "minimumQuickLoginWaitSeconds": 60,
  "waitIncrementSeconds": 60,
  "quickLoginCheckMilliSeconds": 1000,
  "maxDeltaTimeSeconds": 43200,
  "failureFactor": 5,
  "otpPolicyType": "totp",
  "otpPolicyAlgorithm": "HmacSHA256",
  "otpPolicyDigits": 6,
  "otpPolicyPeriod": 30,
  "webAuthnPolicyRpEntityName": "AMINRA",
  "webAuthnPolicySignatureAlgorithms": ["ES256", "RS256"],
  "webAuthnPolicyUserVerificationRequirement": "preferred"
}
EOF

# ── 4. Create clients if missing ──────────────────────────────────────────────

create_client_if_missing() {
  local client_id="$1"
  local payload_file="$2"
  local existing
  existing=$(api GET "/$REALM/clients?clientId=$client_id" | jq -r '.[0].id // empty')
  if [[ -z "$existing" ]]; then
    log "Creating client: $client_id"
    api POST "/$REALM/clients" -d @"$payload_file"
  else
    log "Client $client_id exists ($existing) — skipping create"
  fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/aminra-frontend.json" <<'EOF'
{
  "clientId": "aminra-frontend",
  "name": "AMINRA Frontend (Next.js SPA)",
  "enabled": true,
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "implicitFlowEnabled": false,
  "serviceAccountsEnabled": false,
  "rootUrl": "https://fe.silvergem.org",
  "redirectUris": [
    "http://localhost:3100/*",
    "http://localhost:3000/*",
    "https://dev-web.silvergem.org/*",
    "https://fe.silvergem.org/*",
    "https://mukjizat.silvergem.org/*"
  ],
  "webOrigins": [
    "http://localhost:3100",
    "http://localhost:3000",
    "https://dev-web.silvergem.org",
    "https://fe.silvergem.org",
    "https://mukjizat.silvergem.org"
  ],
  "attributes": {
    "pkce.code.challenge.method": "S256",
    "post.logout.redirect.uris": "+",
    "access.token.lifespan": "900"
  },
  "fullScopeAllowed": false
}
EOF

cat > "$TMP/aminra-backend.json" <<'EOF'
{
  "clientId": "aminra-backend",
  "name": "AMINRA Backend (FastAPI resource server)",
  "enabled": true,
  "publicClient": false,
  "bearerOnly": true,
  "standardFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "implicitFlowEnabled": false,
  "serviceAccountsEnabled": false,
  "fullScopeAllowed": false
}
EOF

create_client_if_missing aminra-frontend "$TMP/aminra-frontend.json"
create_client_if_missing aminra-backend "$TMP/aminra-backend.json"

# ── 5. Create realm roles ─────────────────────────────────────────────────────

create_role_if_missing() {
  local role="$1"
  local description="$2"
  local existing
  existing=$(api_status GET "/$REALM/roles/$role")
  if [[ "$existing" == "404" ]]; then
    log "Creating role: $role"
    api POST "/$REALM/roles" -d "{\"name\":\"$role\",\"description\":\"$description\"}"
  else
    log "Role $role exists — skipping create"
  fi
}

create_role_if_missing business        "Doanh Nghiệp — submit Halal cert request"
create_role_if_missing auditor         "CB Auditor — execute audit on assigned submissions"
create_role_if_missing cb_admin        "CB Admin — manage auditors + ra quyết định cert"
create_role_if_missing platform_admin  "AMINRA Platform Admin — quản lý nền tảng"

# ── 6. Required actions: enable VERIFY_EMAIL + CONFIGURE_TOTP ─────────────────

log "Enabling required action: VERIFY_EMAIL"
api PUT "/$REALM/authentication/required-actions/VERIFY_EMAIL" -d '{"alias":"VERIFY_EMAIL","name":"Verify Email","providerId":"VERIFY_EMAIL","enabled":true,"defaultAction":true,"priority":50,"config":{}}'

log "Enabling required action: CONFIGURE_TOTP"
api PUT "/$REALM/authentication/required-actions/CONFIGURE_TOTP" -d '{"alias":"CONFIGURE_TOTP","name":"Configure OTP","providerId":"CONFIGURE_TOTP","enabled":true,"defaultAction":false,"priority":10,"config":{}}'

log "Bootstrap complete. Realm: $REALM | Admin console: $KEYCLOAK_URL/admin/$REALM/console/"
log ""
log "Next steps (Phase 1 step 3 — separate script keycloak-configure-mfa.sh):"
log "  - Configure MFA REQUIRED authentication flow for auditor/cb_admin/platform_admin"
log "  - Phase 2: FE PKCE OIDC integration"
log "  - Phase 3: BE JWKs JWT validation"
