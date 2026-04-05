#!/bin/bash
set -euo pipefail

# ── Auto-unseal convenience script ────────────────────────────────────────────
# For dev/staging only. Production should use KMS auto-unseal.
# Usage: bash vault/scripts/unseal.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="$(dirname "$SCRIPT_DIR")"
INIT_KEYS_FILE="$VAULT_DIR/approle/init-keys.json"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

if [ ! -f "$INIT_KEYS_FILE" ]; then
    echo "ERROR: $INIT_KEYS_FILE not found. Cannot auto-unseal."
    exit 1
fi

echo "==> Waiting for Vault at $VAULT_ADDR ..."
until curl -sf "$VAULT_ADDR/v1/sys/seal-status" -o /dev/null 2>&1; do
    sleep 2
done

if vault status 2>&1 | grep -q "Sealed.*true"; then
    UNSEAL_KEY=$(jq -r '.unseal_keys_b64[0]' "$INIT_KEYS_FILE")
    vault operator unseal "$UNSEAL_KEY" > /dev/null
    echo "==> Vault unsealed"
else
    echo "==> Vault already unsealed"
fi
