#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"
source "$PROJECT_DIR/scripts/deploy/common.sh"

DRY_RUN=false
BASE="HEAD"
RUN_TESTS=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --base) BASE="${2:?--base requires a git ref}"; shift 2 ;;
    --skip-tests) RUN_TESTS=false; shift ;;
    *) fail "unknown argument: $1" ;;
  esac
done

LANE="$($PROJECT_DIR/scripts/deploy/classify-change.sh --base "$BASE")"
[[ "$LANE" == "frontend-only" ]] || fail "frontend-only deploy refused: classified lane=${LANE}"

PROTECTED_SERVICES=(aminra-backend postgres-db qdrant-db keycloak redis)
SNAPSHOT="$(mktemp)"
snapshot_started_at "$SNAPSHOT" "${PROTECTED_SERVICES[@]}"

if [[ "$RUN_TESTS" == true ]]; then
  log "running frontend focused deploy gates"
  (
    cd frontend/aminra-web
    npm test -- root-landing-contract.test.ts auth-oidc.test.ts
    npm run lint
    npm run build
  )
fi

log "selected lane=frontend-only"
log "deploy command: docker compose build aminra-frontend"
log "deploy command: docker compose up -d --no-deps aminra-frontend"

if [[ "$DRY_RUN" == true ]]; then
  log "dry run complete; no container changed"
  exit 0
fi

docker compose build aminra-frontend
docker compose up -d --no-deps aminra-frontend
wait_healthy aminra-frontend 90
assert_unchanged_started_at "$SNAPSHOT" "${PROTECTED_SERVICES[@]}"
smoke_frontend
log "frontend-only deploy PASS"
