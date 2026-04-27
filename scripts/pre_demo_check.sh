#!/usr/bin/env bash
# Pre-demo smoke verifier — go/no-go gate.
#
# Runs a fast suite of automated checks against a running AMINRA stack to
# determine whether all 20 demo flows are likely to work. Exit code 0 = SAFE
# TO DEMO. Exit 1 = blocker found, investigate before going live.
#
# Usage:
#   bash scripts/pre_demo_check.sh           # check localhost
#   BASE_URL=https://staging.aminra.vn bash scripts/pre_demo_check.sh

set -uo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8100}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3100}"
DEMO_PW="${DEMO_PW:-DemoP@ss2026}"

# ── Colors ──────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
else
  GREEN=''; RED=''; YELLOW=''; BLUE=''; NC=''
fi

PASS=0
FAIL=0
WARN=0
FAILURES=()

ok()   { printf "  ${GREEN}✓${NC} %s\n" "$1"; PASS=$((PASS+1)); }
fail() { printf "  ${RED}✗${NC} %s\n" "$1"; FAIL=$((FAIL+1)); FAILURES+=("$1"); }
warn() { printf "  ${YELLOW}⚠${NC} %s\n" "$1"; WARN=$((WARN+1)); }
section() { printf "\n${BLUE}▶ %s${NC}\n" "$1"; }

# ── Tier 0 — Container health ──────────────────────────────────────────────
section "Tier 0 — Infrastructure"

# Backend reachable
if curl -sf "${BACKEND_URL}/health" > /dev/null 2>&1; then
  ok "Backend /health reachable at ${BACKEND_URL}"
else
  fail "Backend NOT reachable at ${BACKEND_URL}"
fi

# Frontend reachable
if curl -sf "${FRONTEND_URL}" > /dev/null 2>&1; then
  ok "Frontend reachable at ${FRONTEND_URL}"
else
  fail "Frontend NOT reachable at ${FRONTEND_URL}"
fi

# DB connectivity (via backend)
DB_OK=$(curl -s "${BACKEND_URL}/health" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('database','?'))" 2>/dev/null)
if [ "$DB_OK" = "connected" ]; then
  ok "Database connected"
else
  fail "Database NOT connected (got: $DB_OK)"
fi

# Qdrant connectivity
QDRANT_OK=$(curl -s "${BACKEND_URL}/health" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('qdrant','?'))" 2>/dev/null)
if [ "$QDRANT_OK" = "connected" ]; then
  ok "Qdrant connected"
else
  warn "Qdrant status: $QDRANT_OK (RAG flow may degrade)"
fi

# ── Tier 1 — Public flows ──────────────────────────────────────────────────
section "Tier 1 — Public flows (1-5)"

# Flow 1: Public verify cert
RESP=$(curl -s -w "%{http_code}" "${BACKEND_URL}/api/submissions/certificates/public/HALAL-2026-DEMO" -o /tmp/cert_verify.json)
if [ "$RESP" = "200" ]; then
  IS_VALID=$(python3 -c "import json; print(json.load(open('/tmp/cert_verify.json')).get('valid'))" 2>/dev/null)
  if [ "$IS_VALID" = "True" ]; then
    ok "Flow 1: Public verify HALAL-2026-DEMO → valid=true"
  else
    fail "Flow 1: HALAL-2026-DEMO exists but valid=false (status=$IS_VALID)"
  fi
else
  fail "Flow 1: HALAL-2026-DEMO returned HTTP $RESP (run seed_demo_data.py)"
fi

# Flow 2: RAG /topics endpoint (full chat too slow for smoke; just verify endpoint live)
if curl -sf "${BACKEND_URL}/topics" > /dev/null 2>&1; then
  ok "Flow 2: RAG /topics reachable"
else
  warn "Flow 2: RAG /topics not reachable — chat may fail"
fi

# Flow 3: Forgot password endpoint
RESP=$(curl -s -w "%{http_code}" -X POST "${BACKEND_URL}/auth/request-password-reset" \
       -H "Content-Type: application/json" -d '{"email":"ghost@nowhere.io"}' -o /dev/null)
if [ "$RESP" = "200" ]; then
  ok "Flow 3: Forgot-password endpoint returns 200"
else
  fail "Flow 3: Forgot-password endpoint returned HTTP $RESP"
fi

# Flow 4: Privacy + Terms pages
for path in /privacy /terms; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}${path}")
  if [ "$STATUS" = "200" ]; then
    ok "Flow 4: ${path} returns 200"
  else
    fail "Flow 4: ${path} returned HTTP $STATUS"
  fi
done

# Flow 5: Cert PDF download endpoint requires auth — skip in smoke

# ── Tier 2 — Business flows ────────────────────────────────────────────────
section "Tier 2 — Business flows (6-11)"

# Login biz1
LOGIN=$(curl -s -X POST "${BACKEND_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"biz-demo-1@demo.aminra.vn\",\"password\":\"${DEMO_PW}\"}")
BIZ_TOKEN=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$BIZ_TOKEN" ]; then
  ok "Flow 6: Business login succeeded"
else
  fail "Flow 6: Business login failed (have you run seed_demo_data.py?)"
  BIZ_TOKEN=""
fi

# Flow 7: Document evaluation endpoint (don't actually evaluate — too expensive)
if [ -n "$BIZ_TOKEN" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $BIZ_TOKEN" \
           "${BACKEND_URL}/api/documents/")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "307" ]; then
    ok "Flow 7: Documents endpoint accessible (auth)"
  else
    warn "Flow 7: Documents endpoint returned HTTP $STATUS"
  fi
fi

# Flow 8: Submissions list
if [ -n "$BIZ_TOKEN" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $BIZ_TOKEN" \
           "${BACKEND_URL}/api/submissions/my-submissions")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "307" ]; then
    ok "Flow 8: my-submissions endpoint accessible"
  else
    fail "Flow 8: my-submissions returned HTTP $STATUS"
  fi
fi

# Flow 9: Self-assessment templates
if [ -n "$BIZ_TOKEN" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $BIZ_TOKEN" \
           "${BACKEND_URL}/api/assessments/templates")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "307" ] || [ "$STATUS" = "401" ]; then
    ok "Flow 9: Self-assessment templates endpoint up"
  else
    warn "Flow 9: Self-assessment endpoint returned HTTP $STATUS"
  fi
fi

# Flow 10: Revisions endpoint (will 404 for fake sub but proves endpoint mounted)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
         "${BACKEND_URL}/api/submissions/00000000-0000-0000-0000-000000000000/revisions")
if [ "$STATUS" = "401" ]; then
  ok "Flow 10: Revisions endpoint mounted (expects auth)"
else
  warn "Flow 10: Revisions endpoint returned HTTP $STATUS"
fi

# ── Tier 3 — Provider flows ────────────────────────────────────────────────
section "Tier 3 — Provider flows (12-16)"

# Flow 12: Provider login
LOGIN=$(curl -s -X POST "${BACKEND_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"cb-demo@demo.aminra.vn\",\"password\":\"${DEMO_PW}\"}")
PROV_TOKEN=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$PROV_TOKEN" ]; then
  ok "Flow 12: Provider login succeeded"
else
  fail "Flow 12: Provider login failed"
  PROV_TOKEN=""
fi

# Flow 13: Received submissions endpoint
if [ -n "$PROV_TOKEN" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $PROV_TOKEN" \
           "${BACKEND_URL}/api/submissions/received")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "307" ]; then
    ok "Flow 13: Provider received-submissions endpoint OK"
  else
    fail "Flow 13: Provider received-submissions returned HTTP $STATUS"
  fi

  # Flow 14: Cert registry (provider view)
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $PROV_TOKEN" \
           "${BACKEND_URL}/api/submissions/certificates/registry")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "307" ] || [ "$STATUS" = "403" ]; then
    ok "Flow 14: Cert registry endpoint OK"
  else
    warn "Flow 14: Cert registry returned HTTP $STATUS"
  fi

  # Flow 16: Revoke endpoint enforces validation (use bogus cert id)
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
           -H "Authorization: Bearer $PROV_TOKEN" \
           -H "Content-Type: application/json" \
           -d '{"status":"revoked","reason":""}' \
           "${BACKEND_URL}/api/submissions/certificates/00000000-0000-0000-0000-000000000000/status")
  if [ "$STATUS" = "400" ] || [ "$STATUS" = "404" ]; then
    ok "Flow 16: Revoke endpoint validates (HTTP $STATUS)"
  else
    warn "Flow 16: Revoke endpoint returned unexpected HTTP $STATUS"
  fi
fi

# ── Tier 4-5 — Admin flows ─────────────────────────────────────────────────
section "Tier 4-5 — Admin flows (17-20)"

# Flow 17: Audit visits endpoint (skip — needs full auditor setup)
if [ -n "$PROV_TOKEN" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $PROV_TOKEN" \
           "${BACKEND_URL}/api/audits/")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "307" ]; then
    ok "Flow 17: Audit visits endpoint OK"
  else
    warn "Flow 17: Audit visits returned HTTP $STATUS"
  fi
fi

# Flow 18-20: Admin endpoints (require admin auth — use admin@aminra.com via password)
ADMIN_LOGIN=$(curl -s -X POST "${BACKEND_URL}/auth/login" \
              -H "Content-Type: application/json" \
              -d "{\"email\":\"admin@aminra.com\",\"password\":\"aminra2026\"}")
ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -n "$ADMIN_TOKEN" ]; then
  # Flow 18: Analytics
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ADMIN_TOKEN" \
           "${BACKEND_URL}/auth/admin/analytics")
  if [ "$STATUS" = "200" ]; then
    ok "Flow 18: Admin analytics endpoint OK"
  else
    warn "Flow 18: Admin analytics returned HTTP $STATUS"
  fi

  # Flow 20: Overdue queue
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ADMIN_TOKEN" \
           "${BACKEND_URL}/auth/admin/overdue-submissions")
  if [ "$STATUS" = "200" ]; then
    ok "Flow 20: Overdue submissions queue OK"
  else
    warn "Flow 20: Overdue queue returned HTTP $STATUS"
  fi
else
  warn "Flow 18-20: Admin login failed (admin@aminra.com / aminra2026 may differ in this env)"
fi

# ── Frontend pages reachable ───────────────────────────────────────────────
section "Frontend pages"

for path in / /business/login /provider/login /forgot-password /privacy /terms /chat /verify/HALAL-2026-DEMO; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}${path}")
  if [ "$STATUS" = "200" ]; then
    ok "FE ${path}"
  else
    fail "FE ${path} returned HTTP $STATUS"
  fi
done

# ── Final verdict ──────────────────────────────────────────────────────────
echo
printf "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n"
printf "${GREEN}  PASS: %d${NC}    ${YELLOW}WARN: %d${NC}    ${RED}FAIL: %d${NC}\n" "$PASS" "$WARN" "$FAIL"
printf "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n"

if [ "$FAIL" -eq 0 ]; then
  printf "${GREEN}  ✅  SAFE TO DEMO${NC}\n"
  if [ "$WARN" -gt 0 ]; then
    printf "${YELLOW}      ($WARN warning(s) — review before stage)${NC}\n"
  fi
  exit 0
else
  printf "${RED}  ❌  DO NOT DEMO — $FAIL blocker(s):${NC}\n"
  for f in "${FAILURES[@]}"; do
    printf "      ${RED}- %s${NC}\n" "$f"
  done
  exit 1
fi
