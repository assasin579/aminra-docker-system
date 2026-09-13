#!/usr/bin/env bash
# Apply a Cloudflare cache rule for AMINRA public sealed trace JSON.
# Requires explicit credentials and should be run only against the intended zone.
set -euo pipefail

: "${CLOUDFLARE_API_TOKEN:?Set CLOUDFLARE_API_TOKEN with Zone Rulesets edit permission}"
: "${CLOUDFLARE_ZONE_ID:?Set CLOUDFLARE_ZONE_ID for silvergem.org}"

RULE_DESCRIPTION="AMINRA public sealed trace cache"
RULE_EXPR='(http.request.method eq "GET" and http.host eq "dev-web.silvergem.org" and starts_with(http.request.uri.path, "/api/api/supply-chain/batches/trace/"))'
API="https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/rulesets"

command -v curl >/dev/null 2>&1 || { echo "ERROR: curl required" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 required" >&2; exit 2; }

headers=(
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"
  -H "Content-Type: application/json"
)

existing=$(curl -fsS "${headers[@]}" "$API")
zone_ruleset_id=$(EXISTING="$existing" python3 - <<'PY'
import json, os
payload=json.loads(os.environ['EXISTING'])
for rs in payload.get('result', []):
    if rs.get('phase') == 'http_request_cache_settings' and rs.get('kind') == 'zone':
        print(rs.get('id',''))
        break
PY
)

new_rule=$(RULE_DESCRIPTION="$RULE_DESCRIPTION" RULE_EXPR="$RULE_EXPR" python3 - <<'PY'
import json, os
print(json.dumps({
  "description": os.environ["RULE_DESCRIPTION"],
  "expression": os.environ["RULE_EXPR"],
  "action": "set_cache_settings",
  "action_parameters": {
    "cache": True,
    "edge_ttl": {"mode": "override_origin", "default": 60},
    "browser_ttl": {"mode": "override_origin", "default": 5},
    "serve_stale": {"disable_stale_while_updating": False},
  },
  "enabled": True,
}))
PY
)

if [[ -n "$zone_ruleset_id" ]]; then
  current=$(curl -fsS "${headers[@]}" "$API/$zone_ruleset_id")
  updated=$(CURRENT="$current" NEW_RULE="$new_rule" RULE_DESCRIPTION="$RULE_DESCRIPTION" python3 - <<'PY'
import json, os
payload=json.loads(os.environ['CURRENT'])['result']
rules=[r for r in payload.get('rules', []) if r.get('description') != os.environ['RULE_DESCRIPTION']]
rules.insert(0, json.loads(os.environ['NEW_RULE']))
print(json.dumps({
  "name": payload.get("name") or "default",
  "description": payload.get("description") or "Zone cache settings ruleset",
  "kind": "zone",
  "phase": "http_request_cache_settings",
  "rules": rules,
}))
PY
)
  curl -fsS -X PUT "${headers[@]}" --data "$updated" "$API/$zone_ruleset_id" >/dev/null
  echo "updated_cache_ruleset=$zone_ruleset_id"
else
  body=$(NEW_RULE="$new_rule" python3 - <<'PY'
import json, os
print(json.dumps({
  "name": "default",
  "description": "Zone cache settings ruleset",
  "kind": "zone",
  "phase": "http_request_cache_settings",
  "rules": [json.loads(os.environ['NEW_RULE'])],
}))
PY
)
  created=$(curl -fsS -X POST "${headers[@]}" --data "$body" "$API")
  CREATED="$created" python3 - <<'PY'
import json, os
print('created_cache_ruleset=' + json.loads(os.environ['CREATED'])['result']['id'])
PY
fi

echo "Cloudflare cache rule applied: $RULE_DESCRIPTION"
