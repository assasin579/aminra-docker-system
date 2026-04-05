#!/bin/sh

# ── 1. Vault Agent secrets (preferred) ───────────────────────────────────────
VAULT_SECRETS="/vault/secrets/env.sh"
if [ -f "$VAULT_SECRETS" ]; then
    echo "[entrypoint] Loading secrets from Vault Agent..."
    . "$VAULT_SECRETS"
fi

# ── 2. Docker secret files (fallback for non-Vault environments) ─────────────
if [ -f "$OPENROUTER_API_KEY_FILE" ]; then
    export OPENROUTER_API_KEY=$(cat "$OPENROUTER_API_KEY_FILE")
fi
if [ -f "$DEEPSEEK_API_KEY_FILE" ]; then
    export DEEPSEEK_API_KEY=$(cat "$DEEPSEEK_API_KEY_FILE")
fi
if [ -f "$POSTGRES_PASSWORD_FILE" ]; then
    export POSTGRES_PASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
fi

exec "$@"
