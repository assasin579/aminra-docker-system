# ── Vault Agent Configuration ──────────────────────────────────────────────────
# Authenticates via AppRole → fetches secrets → renders env.sh template
# K8s migration: replace auto_auth with Vault Injector annotations

vault {
  address = "http://vault-server:8200"
}

auto_auth {
  method "approle" {
    config = {
      role_id_file_path   = "/vault/approle/role-id"
      secret_id_file_path = "/vault/approle/secret-id"
    }
  }

  sink "file" {
    config = {
      path = "/vault/secrets/.vault-token"
      mode = 0640
    }
  }
}

template_config {
  static_secret_render_interval = "5m"
  exit_on_retry_failure         = true
}

template {
  source      = "/vault/templates/env.tpl"
  destination = "/vault/secrets/env.sh"
  perms       = "0640"
  error_on_missing_key = true
}
