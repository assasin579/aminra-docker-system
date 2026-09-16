#!/usr/bin/env bash
set -euo pipefail

# AMINRA modularization phase gate + local deploy automation.
# Scope: verifies the current modular-monolith changes, commits them locally,
# applies DB migration, rebuilds/recreates local production containers, and
# performs post-deploy stability smoke checks. It is intentionally bounded: it
# does not keep coding forever and it stops on the first failed gate.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="${LOG_DIR:-$ROOT/docs/qa/$TS-modularization-phase-gate}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run.log"
exec > >(tee -a "$LOG_FILE") 2>&1

COMMIT_MESSAGE="${COMMIT_MESSAGE:-feat(modules): add tenant module registry and guarded rollout}"
SKIP_COMMIT="${SKIP_COMMIT:-false}"
SKIP_DEPLOY="${SKIP_DEPLOY:-false}"
STABILITY_SAMPLES="${STABILITY_SAMPLES:-12}"
STABILITY_INTERVAL_SECONDS="${STABILITY_INTERVAL_SECONDS:-5}"

BACKEND_FILES=(
  backend/alembic/versions/041_module_registry.py
  backend/auth/module_router.py
  backend/auth/module_service.py
  backend/auth/module_guard.py
  backend/auth/industry_schema_router.py
  backend/app.py
  backend/supply_chain/material_router.py
  backend/supply_chain/process_router.py
  backend/tests/test_module_registry_migration.py
  backend/tests/test_module_route_contract.py
  backend/tests/test_module_service.py
  backend/tests/test_module_guard.py
  backend/tests/test_supply_chain_module_guards.py
)

FRONTEND_TESTS=(
  sidebar-module-navigation-contract.test.tsx
  sidebar-admin-navigation-contract.test.tsx
)

STAGE_PATHS=(
  .hermes/plans/2026-09-16_141009-aminra-modular-monolith-transition-plan.md
  docs/architecture/module-map.md
  backend/alembic/versions/041_module_registry.py
  backend/auth/module_router.py
  backend/auth/module_service.py
  backend/auth/module_guard.py
  backend/auth/industry_schema_router.py
  backend/app.py
  backend/supply_chain/material_router.py
  backend/supply_chain/process_router.py
  backend/tests/test_module_registry_migration.py
  backend/tests/test_module_route_contract.py
  backend/tests/test_module_service.py
  backend/tests/test_module_guard.py
  backend/tests/test_supply_chain_module_guards.py
  frontend/aminra-web/components/Sidebar.tsx
  frontend/aminra-web/__tests__/sidebar-module-navigation-contract.test.tsx
  scripts/automation/modularization-phase-gate.sh
)

section() { printf '\n\n==> %s\n' "$*"; }
run() { section "$*"; "$@"; }

compose_exec() {
  docker compose exec -T "$@"
}

backend_container_id() {
  docker compose ps -q aminra-backend
}

sync_backend_files_into_container() {
  local cid
  cid="$(backend_container_id)"
  if [[ -z "$cid" ]]; then
    echo "ERROR: aminra-backend container is not running; cannot run in-container backend tests" >&2
    exit 70
  fi
  for path in "${BACKEND_FILES[@]}"; do
    if [[ -f "$path" ]]; then
      docker cp "$path" "$cid:/app/${path#backend/}"
    fi
  done
  # Ensure pytest config is present in older running containers.
  docker cp backend/pytest.ini "$cid:/app/pytest.ini"
}

secret_scan_staged() {
  section "Secret/generated-artifact scan for staged files"
  local suspicious_paths
  suspicious_paths="$(git diff --cached --name-only | grep -Ei '(\.env|secret|password|payload\.db|\.sqlite|\.tar|\.zip|node_modules|\.next|media/|\.mp4$|\.webm$|credentials|token)' || true)"
  if [[ -n "$suspicious_paths" ]]; then
    echo "ERROR: suspicious staged paths:" >&2
    echo "$suspicious_paths" >&2
    exit 71
  fi

  local secret_hits
  # Scan only newly added staged lines for value-like secrets. Generic env var
  # names such as OPENROUTER_API_KEY are allowed; actual assigned values are not.
  secret_hits="$(git diff --cached -U0 -- ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.webp' ':!*.gif' ':!*.pdf' \
    | grep '^+' \
    | grep -Ev '^\+\+\+' \
    | grep -Ei '(BEGIN [A-Z ]*PRIVATE KEY|Authorization: Bearer [A-Za-z0-9._-]{12,}|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|(API_KEY|SECRET|PASSWORD|passwd)[[:space:]]*=[[:space:]]*["'"'"']?[^[:space:]"'"'"'\$][^[:space:]"'"'"']{7,})' || true)"
  if [[ -n "$secret_hits" ]]; then
    echo "ERROR: potential secret-like content in staged diff; inspect manually:" >&2
    echo "$secret_hits" >&2
    exit 72
  fi
}

health_check_once() {
  curl -fsS http://127.0.0.1:8100/health >/tmp/aminra-backend-health.json
  curl -fsS -o /tmp/aminra-frontend-health.html -w 'HTTP %{http_code}\n' http://127.0.0.1:3100 | tee /tmp/aminra-frontend-health.txt
}

public_smoke() {
  section "Public URL smoke"
  curl -fsS -o /tmp/aminra-public-home.html -w 'aminra.org HTTP %{http_code}\n' https://aminra.org | tee "$LOG_DIR/public-home.txt"
  curl -fsS -o /tmp/aminra-public-login.html -w 'business login HTTP %{http_code}\n' https://aminra.org/login/business | tee "$LOG_DIR/public-login-business.txt"
}

stability_loop() {
  section "Post-deploy stability loop (${STABILITY_SAMPLES} samples x ${STABILITY_INTERVAL_SECONDS}s)"
  local failures=0
  for i in $(seq 1 "$STABILITY_SAMPLES"); do
    printf 'sample %02d/%02d: ' "$i" "$STABILITY_SAMPLES"
    if health_check_once >/dev/null; then
      echo "healthy"
    else
      echo "FAILED"
      failures=$((failures + 1))
    fi
    sleep "$STABILITY_INTERVAL_SECONDS"
  done
  if [[ "$failures" -ne 0 ]]; then
    echo "ERROR: stability loop had $failures failed sample(s)" >&2
    exit 73
  fi
}

section "Preflight status"
git branch --show-current | tee "$LOG_DIR/git-branch.txt"
git status --short | tee "$LOG_DIR/git-status-before.txt"
docker compose ps | tee "$LOG_DIR/docker-ps-before.txt"

section "Static gates"
PYTHONPYCACHEPREFIX=/tmp/aminra-pycache python -m py_compile "${BACKEND_FILES[@]}"
git diff --check

section "Backend focused gates in running container"
sync_backend_files_into_container
compose_exec aminra-backend pytest \
  tests/test_module_registry_migration.py \
  tests/test_module_service.py \
  tests/test_module_route_contract.py \
  tests/test_module_guard.py \
  tests/test_supply_chain_module_guards.py \
  -q | tee "$LOG_DIR/backend-focused-tests.txt"

section "Frontend focused gates"
(
  cd frontend/aminra-web
  npm run test -- "${FRONTEND_TESTS[@]}" | tee "$LOG_DIR/frontend-focused-tests.txt"
  npm run lint -- --quiet | tee "$LOG_DIR/frontend-lint.txt"
)

section "Alembic graph smoke"
compose_exec aminra-backend alembic heads --verbose | tee "$LOG_DIR/alembic-heads.txt"

section "Stage intended paths"
git add -- "${STAGE_PATHS[@]}"
git diff --cached --stat | tee "$LOG_DIR/staged-stat.txt"
git diff --cached --check
secret_scan_staged

if [[ "$SKIP_COMMIT" != "true" ]]; then
  section "Commit local checkpoint"
  if git diff --cached --quiet; then
    echo "No staged changes; skipping commit."
  else
    git commit -m "$COMMIT_MESSAGE" -m "- Add module registry migration and default bundles
- Add read-only tenant module API and onboarding provisioning
- Add default-off module guards for first supply-chain surfaces
- Add module-aware business sidebar rendering

Verified: backend focused pytest, frontend focused vitest, frontend lint, py_compile, alembic head smoke, git diff --check" | tee "$LOG_DIR/git-commit.txt"
  fi
else
  echo "SKIP_COMMIT=true; leaving changes staged."
fi

git status --short | tee "$LOG_DIR/git-status-after-commit.txt"

if [[ "$SKIP_DEPLOY" == "true" ]]; then
  section "SKIP_DEPLOY=true; stopping before migration/deploy"
  exit 0
fi

section "Apply DB migration"
./scripts/db-migrate.sh current | tee "$LOG_DIR/alembic-current-before.txt" || true
./scripts/db-migrate.sh upgrade head | tee "$LOG_DIR/alembic-upgrade.txt"
./scripts/db-migrate.sh current | tee "$LOG_DIR/alembic-current-after.txt"

section "Rebuild/recreate local production containers"
docker compose up -d --build aminra-backend aminra-frontend | tee "$LOG_DIR/docker-compose-up.txt"

docker compose ps | tee "$LOG_DIR/docker-ps-after.txt"

section "Immediate local health smoke"
health_check_once | tee "$LOG_DIR/local-health.txt"

public_smoke || {
  echo "WARN: public smoke failed; local health passed. Continuing to stability loop but final status is degraded." | tee "$LOG_DIR/public-smoke-warning.txt"
}

stability_loop

section "Recent service logs scan"
docker compose logs --since=3m aminra-backend aminra-frontend > "$LOG_DIR/recent-service-logs.txt" || true
if grep -Ei 'traceback|uncaught|fatal|panic|segmentation fault' "$LOG_DIR/recent-service-logs.txt"; then
  echo "ERROR: fatal pattern found in recent service logs" >&2
  exit 74
fi

section "DONE"
git --no-pager log --oneline -1 | tee "$LOG_DIR/final-commit.txt"
echo "Evidence: $LOG_DIR"
