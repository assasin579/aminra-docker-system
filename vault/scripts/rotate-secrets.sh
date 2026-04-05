#!/bin/bash
set -euo pipefail

# ── Secret Rotation Script ────────────────────────────────────────────────────
# Usage:
#   bash vault/scripts/rotate-secrets.sh api-keys     # rotate API keys
#   bash vault/scripts/rotate-secrets.sh database      # rotate DB password
#   bash vault/scripts/rotate-secrets.sh auth           # rotate JWT + admin creds
#   bash vault/scripts/rotate-secrets.sh all            # rotate everything

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="$(dirname "$SCRIPT_DIR")"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
INIT_KEYS_FILE="$VAULT_DIR/approle/init-keys.json"

if [ -f "$INIT_KEYS_FILE" ]; then
    export VAULT_TOKEN="${VAULT_TOKEN:-$(jq -r '.root_token' "$INIT_KEYS_FILE")}"
fi

GROUP="${1:-}"
if [ -z "$GROUP" ]; then
    echo "Usage: $0 {api-keys|database|auth|all}"
    exit 1
fi

rotate_api_keys() {
    echo "==> Rotating API keys ..."
    read -rp "  New OPENROUTER_API_KEY: " NEW_OR_KEY
    read -rp "  New DEEPSEEK_API_KEY:   " NEW_DS_KEY
    vault kv put secret/aminra/api-keys \
        openrouter_api_key="$NEW_OR_KEY" \
        deepseek_api_key="$NEW_DS_KEY"
    echo "==> API keys updated. Vault Agent will re-render in ~5 minutes."
    echo "    Or restart backend now: docker compose restart aminra-backend"
}

rotate_database() {
    echo "==> Rotating database password ..."
    NEW_DB_PASS=$(openssl rand -base64 24 | tr -d '/+=')
    echo "    Generated new password: $NEW_DB_PASS"

    # Update Vault
    vault kv put secret/aminra/database \
        postgres_password="$NEW_DB_PASS"

    # Update PostgreSQL directly
    echo "==> Updating PostgreSQL password ..."
    docker exec -i postgres-db psql -U aminra_user -d aminra -c \
        "ALTER USER aminra_user WITH PASSWORD '$NEW_DB_PASS';" 2>/dev/null \
    && echo "==> PostgreSQL password updated" \
    || echo "WARNING: Could not update PostgreSQL. Run manually:"
    echo "    ALTER USER aminra_user WITH PASSWORD '$NEW_DB_PASS';"

    echo "==> Restart backend to pick up new password:"
    echo "    docker compose restart aminra-backend"
}

rotate_auth() {
    echo "==> Rotating auth secrets ..."
    NEW_JWT=$(openssl rand -hex 32)
    NEW_ADMIN_PASS=$(openssl rand -base64 18)
    NEW_ADMIN_SECRET=$(openssl rand -hex 32)

    # Preserve admin_username
    CURRENT_USERNAME=$(vault kv get -format=json secret/aminra/auth \
        | jq -r '.data.data.admin_username // "admin"')

    vault kv put secret/aminra/auth \
        jwt_secret="$NEW_JWT" \
        admin_username="$CURRENT_USERNAME" \
        admin_password="$NEW_ADMIN_PASS" \
        admin_secret="$NEW_ADMIN_SECRET"

    echo "==> Auth secrets rotated."
    echo "    New admin password: $NEW_ADMIN_PASS"
    echo "    WARNING: All existing JWT tokens are now INVALID."
    echo "    Restart backend: docker compose restart aminra-backend"
}

case "$GROUP" in
    api-keys)  rotate_api_keys ;;
    database)  rotate_database ;;
    auth)      rotate_auth ;;
    all)
        rotate_api_keys
        rotate_database
        rotate_auth
        ;;
    *)
        echo "Unknown group: $GROUP"
        echo "Usage: $0 {api-keys|database|auth|all}"
        exit 1
        ;;
esac
