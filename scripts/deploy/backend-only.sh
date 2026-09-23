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
[[ "$LANE" == "backend-only" ]] || fail "backend-only deploy refused: classified lane=${LANE}"

PROTECTED_SERVICES=(postgres-db qdrant-db redis keycloak aminra-frontend)
SNAPSHOT="$(mktemp)"
snapshot_started_at "$SNAPSHOT" "${PROTECTED_SERVICES[@]}"

if [[ "$RUN_TESTS" == true ]]; then
  log "running backend focused deploy gates"
  if docker compose ps -q aminra-backend >/dev/null 2>&1; then
    docker compose exec -T aminra-backend python -m pytest tests -q
  else
    fail "aminra-backend container not available for tests"
  fi
fi

log "selected lane=backend-only"
log "deploy command: docker compose build aminra-backend"
log "deploy command: docker compose up -d --no-deps aminra-backend"

if [[ "$DRY_RUN" == true ]]; then
  log "dry run complete; no container changed"
  exit 0
fi

docker compose build aminra-backend
docker compose up -d --no-deps aminra-backend
wait_healthy aminra-backend 90
assert_unchanged_started_at "$SNAPSHOT" "${PROTECTED_SERVICES[@]}"
smoke_backend
log "backend-only deploy PASS"
