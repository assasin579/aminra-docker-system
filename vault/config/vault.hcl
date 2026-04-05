# ── Vault Server Configuration ─────────────────────────────────────────────────
# Docker Compose: file storage (single node)
# K8s migration:  switch to "raft" integrated storage for HA

ui            = true
disable_mlock = true   # Required for Docker; production K8s can enable mlock

api_addr = "http://vault-server:8200"

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1   # Internal Docker network only; K8s should use TLS
}

# Max lease TTL
max_lease_ttl = "768h"    # 32 days
default_lease_ttl = "1h"
