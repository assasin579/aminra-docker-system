# ── AMINRA Backend Policy ──────────────────────────────────────────────────────
# Read-only access to application secrets. No list/write/delete.

path "secret/data/aminra/api-keys" {
  capabilities = ["read"]
}

path "secret/data/aminra/database" {
  capabilities = ["read"]
}

path "secret/data/aminra/auth" {
  capabilities = ["read"]
}

path "secret/data/aminra/qdrant" {
  capabilities = ["read"]
}
