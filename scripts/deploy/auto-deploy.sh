#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"
source "$PROJECT_DIR/scripts/deploy/common.sh"

BASE="HEAD"
DRY_RUN=false
SKIP_TESTS=false
STATEFUL_APPROVED=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="${2:?--base requires a git ref}"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --skip-tests) SKIP_TESTS=true; shift ;;
    --stateful-approved) STATEFUL_APPROVED=true; shift ;;
    *) fail "unknown argument: $1" ;;
  esac
done

LANE="$($PROJECT_DIR/scripts/deploy/classify-change.sh --base "$BASE")"
log "classified lane=${LANE}"

common_args=(--base "$BASE")
if [[ "$DRY_RUN" == true ]]; then
  common_args+=(--dry-run)
fi
if [[ "$SKIP_TESTS" == true ]]; then
  common_args+=(--skip-tests)
fi

case "$LANE" in
  docs-only)
    log "docs-only change: no application deploy required"
    exit 0
    ;;
  frontend-only)
    exec "$PROJECT_DIR/scripts/deploy/frontend-only.sh" "${common_args[@]}"
    ;;
  backend-only)
    exec "$PROJECT_DIR/scripts/deploy/backend-only.sh" "${common_args[@]}"
    ;;
  infra-stateful)
    if [[ "$STATEFUL_APPROVED" != true ]]; then
      fail "infra-stateful lane requires --stateful-approved plus a backup/maintenance plan; auto-deploy intentionally fails closed"
    fi
    fail "infra-stateful implementation intentionally not automated yet; use scripts/automation/modularization-phase-gate.sh with explicit maintenance plan"
    ;;
  mixed)
    fail "mixed lane requires human plan; split frontend/backend/infra changes or use explicit release procedure"
    ;;
  *)
    fail "unknown lane: ${LANE}"
    ;;
esac
