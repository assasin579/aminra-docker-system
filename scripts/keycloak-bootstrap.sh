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

env_or_dotenv() {
  local key="$1"
  local current="${!key:-}"
  if [[ -n "$current" ]]; then
    printf '%s' "$current"
    return
  fi
  if [[ -f .env ]]; then
    grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- | sed 's/^"//; s/"$//' || true
  fi
}

bool_env_or_default() {
  local key="$1"
  local default="$2"
  local value
  value="$(env_or_dotenv "$key")"
  if [[ -z "$value" ]]; then
    value="$default"
  fi
  case "${value,,}" in
    true|1|yes|y|on) printf 'true' ;;
    false|0|no|n|off) printf 'false' ;;
    *) printf '%s' "$default" ;;
  esac
}

# ── 0. Ensure postgres has keycloak DB + role (idempotent) ────────────────────
# When the postgres-data volume already existed (common on dev re-run) the
# init script `02-keycloak-init.sh` does NOT execute — postgres only runs
# init scripts on first initdb. Compensate with a manual create step that
# tolerates "already exists".

KC_DB_PW="${KEYCLOAK_DB_PASSWORD:-}"
if [[ -z "$KC_DB_PW" && -f .env ]]; then
  KC_DB_PW=$(grep -E '^KEYCLOAK_DB_PASSWORD=' .env | cut -d= -f2- | tr -d '"' || true)
fi

if [[ -n "$KC_DB_PW" ]]; then
  log "Ensuring postgres has keycloak role + database"
  POSTGRES_CONTAINER=$(docker compose ps -q postgres-db 2>/dev/null || true)
  if [[ -n "$POSTGRES_CONTAINER" ]]; then
    docker compose exec -T postgres-db psql -U aminra_user -d aminra <<SQL >/dev/null 2>&1 || true
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
    CREATE ROLE keycloak WITH LOGIN ENCRYPTED PASSWORD '${KC_DB_PW}';
  END IF;
END
\$\$;
SQL
    if ! docker compose exec -T postgres-db psql -U aminra_user -d aminra -tAc "SELECT 1 FROM pg_database WHERE datname='keycloak'" 2>/dev/null | grep -q 1; then
      docker compose exec -T postgres-db psql -U aminra_user -d aminra -c "CREATE DATABASE keycloak OWNER keycloak;" >/dev/null 2>&1 || true
      docker compose exec -T postgres-db psql -U aminra_user -d aminra -c "GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;" >/dev/null 2>&1 || true
    fi
  else
    log "  WARN: postgres-db container not running — skipping DB pre-create"
  fi
else
  log "  WARN: KEYCLOAK_DB_PASSWORD not set — skipping DB pre-create"
fi

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

# ── 3a. Enable unmanagedAttributePolicy (Keycloak v25 strict profile) ─────────
# Without this, custom user attributes (tenant_id/is_owner/status set by
# admin REST or via mappers) are stripped → "Account is not fully set up"
# error on direct grant + missing claims in JWT. Idempotent PUT.

log "Enabling unmanagedAttributePolicy on user profile"
PROFILE_JSON=$(api GET "/$REALM/users/profile")
PROFILE_PATCHED=$(echo "$PROFILE_JSON" | jq '. + {unmanagedAttributePolicy: "ENABLED"}')
api PUT "/$REALM/users/profile" -d "$PROFILE_PATCHED" >/dev/null

# ── 3b. Configure realm token settings + password policy ──────────────────────

log "Updating realm token expiry + password policy"
api PUT "/$REALM" -d @- <<'EOF'
{
  "accessTokenLifespan": 900,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 28800,
  "offlineSessionIdleTimeout": 604800,
  "passwordPolicy": "length(12) and digits(1) and upperCase(1) and lowerCase(1) and specialChars(1) and notUsername(undefined) and notEmail(undefined) and passwordHistory(5) and forceExpiredPasswordChange(180) and hashIterations(210000)",
  "resetPasswordAllowed": true,
  "verifyEmail": true,
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

# ── 3c. Configure SMTP + email-verification delivery (production-safe) ─────────
# Keycloak verifyEmail/resetPassword need a realm SMTP server. Configure only
# when host + from address are explicitly supplied; never bake SMTP secrets into
# the repo or logs. Supported env/.env keys:
#   KEYCLOAK_SMTP_HOST, KEYCLOAK_SMTP_PORT, KEYCLOAK_SMTP_FROM,
#   KEYCLOAK_SMTP_FROM_DISPLAY_NAME, KEYCLOAK_SMTP_REPLY_TO,
#   KEYCLOAK_SMTP_USER, KEYCLOAK_SMTP_PASSWORD,
#   KEYCLOAK_SMTP_SSL, KEYCLOAK_SMTP_STARTTLS, KEYCLOAK_SMTP_AUTH
SMTP_HOST="$(env_or_dotenv KEYCLOAK_SMTP_HOST)"
SMTP_PORT="$(env_or_dotenv KEYCLOAK_SMTP_PORT)"
SMTP_FROM="$(env_or_dotenv KEYCLOAK_SMTP_FROM)"
SMTP_FROM_DISPLAY_NAME="$(env_or_dotenv KEYCLOAK_SMTP_FROM_DISPLAY_NAME)"
SMTP_REPLY_TO="$(env_or_dotenv KEYCLOAK_SMTP_REPLY_TO)"
SMTP_USER="$(env_or_dotenv KEYCLOAK_SMTP_USER)"
SMTP_PASS="$(env_or_dotenv KEYCLOAK_SMTP_PASSWORD)"
SMTP_SSL="$(bool_env_or_default KEYCLOAK_SMTP_SSL false)"
SMTP_STARTTLS="$(bool_env_or_default KEYCLOAK_SMTP_STARTTLS true)"
SMTP_AUTH="$(bool_env_or_default KEYCLOAK_SMTP_AUTH true)"
SMTP_PORT="${SMTP_PORT:-587}"

if [[ -n "$SMTP_HOST" && -n "$SMTP_FROM" ]]; then
  log "Configuring realm SMTP server for verify-email/reset-password delivery (host=$SMTP_HOST port=$SMTP_PORT from=$SMTP_FROM)"
  SMTP_JSON=$(jq -n \
    --arg host "$SMTP_HOST" \
    --arg port "$SMTP_PORT" \
    --arg from "$SMTP_FROM" \
    --arg fromDisplayName "$SMTP_FROM_DISPLAY_NAME" \
    --arg replyTo "$SMTP_REPLY_TO" \
    --arg user "$SMTP_USER" \
    --arg password "$SMTP_PASS" \
    --arg ssl "$SMTP_SSL" \
    --arg starttls "$SMTP_STARTTLS" \
    --arg auth "$SMTP_AUTH" \
    '{smtpServer:{host:$host, port:$port, from:$from, ssl:$ssl, starttls:$starttls, auth:$auth}}
     | if $fromDisplayName != "" then .smtpServer.fromDisplayName=$fromDisplayName else . end
     | if $replyTo != "" then .smtpServer.replyTo=$replyTo else . end
     | if $user != "" then .smtpServer.user=$user else . end
     | if $password != "" then .smtpServer.password=$password else . end')
  api PUT "/$REALM" -d "$SMTP_JSON" >/dev/null
else
  log "WARN: Keycloak SMTP not configured — set KEYCLOAK_SMTP_HOST + KEYCLOAK_SMTP_FROM (+ credentials) before production email verification"
fi

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
  "directAccessGrantsEnabled": true,
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
  "fullScopeAllowed": true
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

cat > "$TMP/aminra-admin-cli.json" <<'EOF'
{
  "clientId": "aminra-admin-cli",
  "name": "AMINRA Admin CLI (BE service account for user mgmt)",
  "enabled": true,
  "publicClient": false,
  "bearerOnly": false,
  "standardFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "implicitFlowEnabled": false,
  "serviceAccountsEnabled": true,
  "fullScopeAllowed": true
}
EOF

create_client_if_missing aminra-frontend "$TMP/aminra-frontend.json"
create_client_if_missing aminra-backend "$TMP/aminra-backend.json"
create_client_if_missing aminra-admin-cli "$TMP/aminra-admin-cli.json"

# Ensure existing aminra-frontend has the dev-test-friendly settings even
# on re-runs (create-if-missing doesn't update existing clients).
FE_UUID=$(api GET "/$REALM/clients?clientId=aminra-frontend" | jq -r '.[0].id // empty')
if [[ -n "$FE_UUID" ]]; then
  log "Patching aminra-frontend: directAccessGrantsEnabled + fullScopeAllowed"
  api PUT "/$REALM/clients/$FE_UUID" \
    -d '{"directAccessGrantsEnabled":true,"fullScopeAllowed":true}' >/dev/null
fi

# Phase 4c-2: enforce fullScopeAllowed=true on aminra-admin-cli even when the
# client was created by an older bootstrap run (default was `false`). Without
# this, realm-management client roles granted to the service account user are
# stripped from the client_credentials access token and `create_user` 403s.
ADMIN_CLI_UUID_FORCE=$(api GET "/$REALM/clients?clientId=aminra-admin-cli" | jq -r '.[0].id // empty')
if [[ -n "$ADMIN_CLI_UUID_FORCE" ]]; then
  api PUT "/$REALM/clients/$ADMIN_CLI_UUID_FORCE" \
    -d '{"fullScopeAllowed":true}' >/dev/null
fi

# ── 4b. Add protocol-mappers to aminra-frontend (Phase 3b) ────────────────────
# Maps user attributes (tenant_id, is_owner, status) into JWT claims so the
# backend can skip the DB enrichment lookup. User attributes are set at
# user creation time by the registration flow (Phase 4).

ensure_mapper() {
  local client_uuid="$1"
  local mapper_name="$2"
  local user_attr="$3"
  local json_type="$4"  # String | boolean | int | long
  local existing
  existing=$(api GET "/$REALM/clients/$client_uuid/protocol-mappers/models" \
    | jq -r --arg n "$mapper_name" '.[] | select(.name==$n) | .id')
  if [[ -n "$existing" ]]; then
    log "Mapper $mapper_name exists on client — skipping"
    return
  fi
  log "Adding mapper $mapper_name → claim $user_attr ($json_type)"
  api POST "/$REALM/clients/$client_uuid/protocol-mappers/models" -d @- <<EOF
{
  "name": "$mapper_name",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-usermodel-attribute-mapper",
  "consentRequired": false,
  "config": {
    "user.attribute": "$user_attr",
    "claim.name": "$user_attr",
    "jsonType.label": "$json_type",
    "id.token.claim": "true",
    "access.token.claim": "true",
    "userinfo.token.claim": "true",
    "multivalued": "false"
  }
}
EOF
}

ensure_audience_mapper() {
  local client_uuid="$1"
  local audience="$2"
  local existing
  existing=$(api GET "/$REALM/clients/$client_uuid/protocol-mappers/models" \
    | jq -r --arg a "aud-$audience" '.[] | select(.name==$a) | .id')
  if [[ -n "$existing" ]]; then
    log "Audience mapper for $audience exists — skipping"
    return
  fi
  log "Adding audience mapper → $audience"
  api POST "/$REALM/clients/$client_uuid/protocol-mappers/models" -d @- <<EOF
{
  "name": "aud-$audience",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-audience-mapper",
  "consentRequired": false,
  "config": {
    "included.client.audience": "$audience",
    "id.token.claim": "false",
    "access.token.claim": "true"
  }
}
EOF
}

FE_CLIENT_UUID=$(api GET "/$REALM/clients?clientId=aminra-frontend" | jq -r '.[0].id // empty')
if [[ -n "$FE_CLIENT_UUID" ]]; then
  ensure_mapper "$FE_CLIENT_UUID" "tenant_id-mapper" "tenant_id" "String"
  ensure_mapper "$FE_CLIENT_UUID" "is_owner-mapper"  "is_owner"  "boolean"
  ensure_mapper "$FE_CLIENT_UUID" "status-mapper"    "status"    "String"
  ensure_audience_mapper "$FE_CLIENT_UUID" "aminra-backend"
else
  log "WARNING: aminra-frontend client UUID not found — skipping mapper setup"
fi

# ── 4c. Grant realm-management roles to aminra-admin-cli (Phase 4) ────────────
# Lets BE call admin REST API via client_credentials grant (no master pw).

ADMIN_CLI_UUID=$(api GET "/$REALM/clients?clientId=aminra-admin-cli" | jq -r '.[0].id // empty')
if [[ -z "$ADMIN_CLI_UUID" ]]; then
  log "WARNING: aminra-admin-cli client UUID not found — skipping role grant"
else
  RM_CLIENT_UUID=$(api GET "/$REALM/clients?clientId=realm-management" | jq -r '.[0].id // empty')
  SVC_USER_ID=$(api GET "/$REALM/clients/$ADMIN_CLI_UUID/service-account-user" | jq -r '.id // empty')
  if [[ -z "$RM_CLIENT_UUID" || -z "$SVC_USER_ID" ]]; then
    log "WARNING: realm-management client or service-account user missing — skip"
  else
    ROLES_JSON=$(api GET "/$REALM/clients/$RM_CLIENT_UUID/roles")
    # Phase 4c-2: view-realm added so create_user can call GET /admin/realms/{realm}/roles/{role}
    GRANT_PAYLOAD=$(echo "$ROLES_JSON" | jq '[.[] | select(.name=="manage-users" or .name=="query-users" or .name=="view-users" or .name=="view-realm") | {id, name}]')
    if [[ "$(echo "$GRANT_PAYLOAD" | jq 'length')" -ge 4 ]]; then
      log "Granting manage-users + query-users + view-users + view-realm to aminra-admin-cli service account"
      api POST "/$REALM/users/$SVC_USER_ID/role-mappings/clients/$RM_CLIENT_UUID" -d "$GRANT_PAYLOAD" || \
        log "  Grant returned non-201 — likely already granted"
    else
      log "WARNING: realm-management role payload has fewer than 4 expected roles"
    fi
  fi

  # Surface client secret so founder can paste into .env (KEYCLOAK_ADMIN_CLI_SECRET).
  CLI_SECRET=$(api GET "/$REALM/clients/$ADMIN_CLI_UUID/client-secret" | jq -r '.value // empty')
  if [[ -n "$CLI_SECRET" ]]; then
    cat >&2 <<EOF

────────────────────────────────────────────────────────────────────
SECRET — DO NOT COMMIT.
Add to top-level .env (or Vault: secret/aminra/keycloak/admin_cli_secret):

  KEYCLOAK_ADMIN_CLI_SECRET=$CLI_SECRET

────────────────────────────────────────────────────────────────────
EOF
  fi
fi

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

log "Enabling required action: VERIFY_EMAIL (defaultAction=false)"
# Action stays enabled (FE registration flow can still trigger it explicitly
# when needed), but defaultAction=false so admin-REST-created users with
# emailVerified=true can authenticate without "Account is not fully set up".
api PUT "/$REALM/authentication/required-actions/VERIFY_EMAIL" -d '{"alias":"VERIFY_EMAIL","name":"Verify Email","providerId":"VERIFY_EMAIL","enabled":true,"defaultAction":false,"priority":50,"config":{}}'

log "Enabling required action: CONFIGURE_TOTP"
api PUT "/$REALM/authentication/required-actions/CONFIGURE_TOTP" -d '{"alias":"CONFIGURE_TOTP","name":"Configure OTP","providerId":"CONFIGURE_TOTP","enabled":true,"defaultAction":false,"priority":10,"config":{}}'

log "Bootstrap complete. Realm: $REALM | Admin console: $KEYCLOAK_URL/admin/$REALM/console/"
log ""
log "Next steps (Phase 1 step 3 — separate script keycloak-configure-mfa.sh):"
log "  - Configure MFA REQUIRED authentication flow for auditor/cb_admin/platform_admin"
log "  - Phase 2: FE PKCE OIDC integration"
log "  - Phase 3: BE JWKs JWT validation"
