#!/bin/bash
set -euo pipefail

# ── AMINRA Vault Bootstrap ────────────────────────────────────────────────────
# Run ONCE after: docker compose -f vault/docker-compose.vault.yml up -d vault-server
# Usage: bash vault/scripts/init-vault.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$VAULT_DIR")"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
INIT_KEYS_FILE="$VAULT_DIR/approle/init-keys.json"

echo "==> Waiting for Vault at $VAULT_ADDR ..."
until curl -sf "$VAULT_ADDR/v1/sys/health" -o /dev/null 2>&1 || \
      curl -sf "$VAULT_ADDR/v1/sys/seal-status" -o /dev/null 2>&1; do
    sleep 2
    echo "    still waiting..."
done
echo "==> Vault is reachable"

# ── Step 1: Initialize (first time only) ─────────────────────────────────────
if vault status 2>&1 | grep -q "Initialized.*false"; then
    echo "==> Initializing Vault (key-shares=1, threshold=1) ..."
    vault operator init \
        -key-shares=1 \
        -key-threshold=1 \
        -format=json > "$INIT_KEYS_FILE"
    chmod 600 "$INIT_KEYS_FILE"
    echo "==> Init keys saved to $INIT_KEYS_FILE (KEEP THIS SAFE!)"
else
    echo "==> Vault already initialized"
fi

# ── Step 2: Unseal ────────────────────────────────────────────────────────────
if vault status 2>&1 | grep -q "Sealed.*true"; then
    if [ ! -f "$INIT_KEYS_FILE" ]; then
        echo "ERROR: Vault is sealed but $INIT_KEYS_FILE not found."
        echo "       Provide unseal key manually: vault operator unseal"
        exit 1
    fi
    UNSEAL_KEY=$(jq -r '.unseal_keys_b64[0]' "$INIT_KEYS_FILE")
    echo "==> Unsealing Vault ..."
    vault operator unseal "$UNSEAL_KEY" > /dev/null
    echo "==> Vault unsealed"
else
    echo "==> Vault already unsealed"
fi

# ── Step 3: Authenticate ─────────────────────────────────────────────────────
if [ -f "$INIT_KEYS_FILE" ]; then
    export VAULT_TOKEN=$(jq -r '.root_token' "$INIT_KEYS_FILE")
else
    echo "ERROR: Cannot find root token. Set VAULT_TOKEN manually."
    exit 1
fi

# ── Step 4: Enable KV v2 secrets engine ───────────────────────────────────────
if ! vault secrets list -format=json | jq -e '."secret/"' > /dev/null 2>&1; then
    echo "==> Enabling KV v2 at secret/"
    vault secrets enable -path=secret -version=2 kv
else
    echo "==> KV v2 already enabled at secret/"
fi

# ── Step 5: Load secrets from current .env ────────────────────────────────────
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "==> Loading secrets from $ENV_FILE"
    source "$ENV_FILE"
else
    echo "WARNING: .env not found at $ENV_FILE"
    echo "         You'll need to provide secret values manually."
fi

# Generate fresh values for secrets that should be rotated
NEW_JWT_SECRET=$(openssl rand -hex 32)
NEW_ADMIN_SECRET=$(openssl rand -hex 32)
NEW_ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -base64 18)}"

echo "==> Writing secrets to Vault ..."

vault kv put secret/aminra/api-keys \
    openrouter_api_key="${OPENROUTER_API_KEY:-REPLACE_ME}" \
    deepseek_api_key="${DEEPSEEK_API_KEY:-REPLACE_ME}"

vault kv put secret/aminra/database \
    postgres_password="${POSTGRES_PASSWORD:-REPLACE_ME}"

vault kv put secret/aminra/auth \
    jwt_secret="$NEW_JWT_SECRET" \
    admin_username="${ADMIN_USERNAME:-admin}" \
    admin_password="$NEW_ADMIN_PASSWORD" \
    admin_secret="$NEW_ADMIN_SECRET"

echo "==> Secrets written"

# ── Step 6: Create policy ────────────────────────────────────────────────────
echo "==> Writing policy: aminra-backend"
vault policy write aminra-backend "$VAULT_DIR/policies/aminra-backend.hcl"

# ── Step 7: Enable AppRole auth ──────────────────────────────────────────────
if ! vault auth list -format=json | jq -e '."approle/"' > /dev/null 2>&1; then
    echo "==> Enabling AppRole auth"
    vault auth enable approle
else
    echo "==> AppRole already enabled"
fi

echo "==> Creating role: aminra-backend"
vault write auth/approle/role/aminra-backend \
    token_policies="aminra-backend" \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_ttl=0

# ── Step 8: Extract role-id and secret-id ─────────────────────────────────────
echo "==> Generating AppRole credentials ..."

vault read -format=json auth/approle/role/aminra-backend/role-id \
    | jq -r '.data.role_id' > "$VAULT_DIR/approle/role-id"

vault write -format=json -f auth/approle/role/aminra-backend/secret-id \
    | jq -r '.data.secret_id' > "$VAULT_DIR/approle/secret-id"

chmod 600 "$VAULT_DIR/approle/role-id" "$VAULT_DIR/approle/secret-id"

echo ""
echo "============================================"
echo "  Vault initialized successfully!"
echo "============================================"
echo ""
echo "  Vault UI:     $VAULT_ADDR/ui"
echo "  Root token:   $(jq -r '.root_token' "$INIT_KEYS_FILE")"
echo "  Role ID:      $(cat "$VAULT_DIR/approle/role-id")"
echo ""
echo "  Next steps:"
echo "  1. Start Vault Agent:"
echo "     docker compose -f vault/docker-compose.vault.yml up -d vault-agent"
echo "  2. Verify secrets rendered:"
echo "     docker exec vault-agent cat /vault/secrets/env.sh"
echo "  3. Restart app stack:"
echo "     docker compose up -d"
echo ""
echo "  IMPORTANT: Rotate your API keys since old values were in git!"
echo ""
