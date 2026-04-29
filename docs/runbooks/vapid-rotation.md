# Runbook — VAPID (Web Push) Key Rotation

**Trigger:** Suspected key leak, scheduled rotation (recommended ≥1×/year), departing engineer offboarding.

**Approver:** Bạn (single-approver). For team scale, designate ≥2 approvers and document.

**Impact:**
- All existing browser push subscriptions become invalid.
- Frontend service worker auto-resubscribes on next page load (no user action needed).
- Brief gap in push notifications until SW re-syncs (~minutes).

---

## Procedure

### 1. Pre-rotation
- [ ] Notify CB+business stakeholders of brief push outage.
- [ ] Verify `vault-server` + `vault-agent` healthy: `docker ps | grep vault`
- [ ] Verify backend healthy: `curl -sf http://localhost:8100/health`

### 2. Rotate
```bash
bash vault/scripts/rotate-secrets.sh web-push
```

What it does:
1. Generates new VAPID P-256 keypair via `py_vapid` in throwaway python container
2. Stores in Vault KV at `secret/aminra/web-push` (preserves contact_email)
3. Vault-agent re-renders `/vault/secrets/env.sh` within ≤5 minutes (auto)

### 3. Apply
```bash
docker restart vault-agent              # force immediate re-render
docker compose restart aminra-backend   # pick up new env
```

### 4. Verify
```bash
# Public key should equal NEW one printed by rotation script
curl -s http://localhost:8100/api/notifications/push-public-key | jq -r .key

# Backend health
curl -sf http://localhost:8100/health

# Vault-agent rendered without errors
docker logs --tail 20 vault-agent | grep -E "rendered|error"
```

### 5. Post-rotation
- [ ] Verify push-public-key endpoint returns new key
- [ ] Trigger a test notification end-to-end (login as biz user, perform action that fires push)
- [ ] Update incident log if rotation was triggered by suspected leak

---

## Rollback (if rotation fails)

If new keypair causes issues, revert to previous version in Vault:

```bash
# Vault KV v2 keeps version history (default 10 versions)
VAULT_TOKEN=$(grep -oP '"root_token":\s*"\K[^"]+' vault/approle/init-keys.json)
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="$VAULT_TOKEN" \
  vault-server vault kv rollback -version=N secret/aminra/web-push

docker restart vault-agent
docker compose restart aminra-backend
```

Replace `N` with previous version number (`vault kv metadata get secret/aminra/web-push` to list).

---

## History

| Date | Trigger | Old key (first 16 chars) | New key (first 16 chars) | Approver |
|---|---|---|---|---|
| 2026-04-29 | gitleaks finding in `docker-compose.yml:95` (committed plaintext) | `BEXej9buEL1puCJ8` | `BPVmpwmAt0OD795g` | (initial setup) |
