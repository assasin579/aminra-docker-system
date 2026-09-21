#!/usr/bin/env bash
set -euo pipefail

# AMINRA modularization/release phase gate.
#
# Modes:
#   verify-only       run static/backend/frontend gates only; no commit/migrate/deploy
#   build-only        build heavyweight backend base + backend/frontend images; no deploy
#   hot-restart-local sync backend files into the running container and restart; no image claim
#   immutable-deploy  verify, optionally commit, build fresh images, migrate, recreate services, smoke
#
# The script is intentionally bounded. It never loops into new feature work and
# exits on first failed gate so AMINRA runtime stability is preserved.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="${LOG_DIR:-$ROOT/docs/qa/$TS-modularization-phase-gate}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run.log"
exec > >(tee -a "$LOG_FILE") 2>&1

MODE="${1:-${MODE:-immutable-deploy}}"
if [[ "$#" -gt 1 ]]; then
  echo "ERROR: expected at most one mode argument; got $#" >&2
  echo "Run: $0 --help" >&2
  exit 64
fi
case "$MODE" in
  verify-only|build-only|hot-restart-local|immutable-deploy) ;;
  -h|--help|help)
    cat <<'EOF'
Usage: scripts/automation/modularization-phase-gate.sh [verify-only|build-only|hot-restart-local|immutable-deploy]

Modes:
  verify-only       run static/backend/frontend gates only; no commit/migrate/deploy/build
  build-only        build heavyweight backend base + backend/frontend images; no deploy
  hot-restart-local verify, sync backend files into running container, restart backend, smoke
  immutable-deploy  verify, optionally commit, build fresh images, migrate, recreate services, smoke

If no positional mode is provided, MODE env var is used; default remains immutable-deploy.
Set REBUILD_BACKEND_BASE=true when backend/Dockerfile.base, requirements.txt,
OS/Python dependencies, Playwright install behavior, or model preload inputs change.
EOF
    exit 0
    ;;
  *)
    echo "ERROR: unknown MODE=$MODE" >&2
    echo "Run: $0 --help" >&2
    exit 64
    ;;
esac
COMMIT_MESSAGE="${COMMIT_MESSAGE:-feat(modules): add tenant module registry and guarded rollout}"
SKIP_COMMIT="${SKIP_COMMIT:-false}"
STABILITY_SAMPLES="${STABILITY_SAMPLES:-12}"
STABILITY_INTERVAL_SECONDS="${STABILITY_INTERVAL_SECONDS:-5}"
STAGE_TIMEOUT_SECONDS="${STAGE_TIMEOUT_SECONDS:-600}"
BUILD_TIMEOUT_SECONDS="${BUILD_TIMEOUT_SECONDS:-1800}"
BUILD_RETRIES="${BUILD_RETRIES:-3}"
REBUILD_BACKEND_BASE="${REBUILD_BACKEND_BASE:-auto}"
BACKEND_BASE_IMAGE="${BACKEND_BASE_IMAGE:-aminra-backend-base:local}"
BACKEND_APP_IMAGE="${BACKEND_APP_IMAGE:-aminra-docker-system-aminra-backend:latest}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-aminra-docker-system-aminra-frontend:latest}"

if ! [[ "$BUILD_RETRIES" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: BUILD_RETRIES must be a positive integer; got '$BUILD_RETRIES'" >&2
  exit 64
fi

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
  admin-module-manager-contract.test.tsx
  my-modules-customer-experience.test.tsx
)

STAGE_PATHS=(
  .hermes/plans/2026-09-16_141009-aminra-modular-monolith-transition-plan.md
  docs/architecture/module-map.md
  docker-compose.yml
  backend/.dockerignore
  backend/Dockerfile
  backend/Dockerfile.base
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
  frontend/aminra-web/components/AdminModuleManager.tsx
  frontend/aminra-web/components/MyModulesPanel.tsx
  frontend/aminra-web/app/modules/page.tsx
  frontend/aminra-web/__tests__/sidebar-module-navigation-contract.test.tsx
  frontend/aminra-web/__tests__/admin-module-manager-contract.test.tsx
  frontend/aminra-web/__tests__/my-modules-customer-experience.test.tsx
  scripts/automation/modularization-phase-gate.sh
)

section() { printf '\n\n==> %s\n' "$*"; }

run_timeout() {
  local seconds="$1"; shift
  section "$*"
  timeout --preserve-status --kill-after=30s "$seconds" "$@"
}

run_timeout_retry() {
  local seconds="$1"; shift
  local attempt=1
  while true; do
    if run_timeout "$seconds" "$@"; then
      return 0
    fi
    if [[ "$attempt" -ge "$BUILD_RETRIES" ]]; then
      echo "ERROR: command failed after $attempt attempt(s): $*" >&2
      return 1
    fi
    echo "WARN: command failed on attempt $attempt/$BUILD_RETRIES; retrying after 10s: $*" >&2
    attempt=$((attempt + 1))
    sleep 10
  done
}

compose_exec() {
  docker compose exec -T "$@"
}

backend_container_id() {
  docker compose ps -q aminra-backend
}

image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
}

docker_build_probe() {
  section "Docker BuildKit write probe"
  local probe_dir probe_image
  probe_dir="$(mktemp -d)"
  probe_image="aminra-docker-write-probe:${TS}"
  cleanup_docker_build_probe() {
    rm -rf "$probe_dir"
    docker image rm -f "$probe_image" >/dev/null 2>&1 || true
  }
  trap cleanup_docker_build_probe EXIT

  cat > "$probe_dir/Dockerfile" <<'EOF'
FROM scratch
LABEL org.aminra.phase_gate_probe="true"
EOF

  run_timeout "$STAGE_TIMEOUT_SECONDS" docker build -t "$probe_image" "$probe_dir"
  docker image inspect "$probe_image" >/dev/null
  cleanup_docker_build_probe
  trap - EXIT
  echo "docker-build-probe=PASS" | tee "$LOG_DIR/docker-build-probe.txt"
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
  secret_hits="$(git diff --cached -U0 -- ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.webp' ':!*.gif' ':!*.pdf' \
    | grep '^+' \
    | grep -Ev '^\+\+\+' \
    | grep -Ei '(BEGIN [A-Z ]*PRIVATE KEY|Authorization: Bearer [[:alnum:]_.=-]{20,}|(API_KEY|SECRET|PASSWORD|passwd)[[:space:]]*=[[:space:]]*[^[:space:]]{12,})' || true)"
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

wait_for_local_services() {
  section "Wait for local service health"
  local deadline=$((SECONDS + 120))
  local backend_status frontend_status
  while (( SECONDS < deadline )); do
    backend_status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${COMPOSE_PROJECT_NAME:-aminra-docker-system}-aminra-backend-1" 2>/dev/null || true)"
    frontend_status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${COMPOSE_PROJECT_NAME:-aminra-docker-system}-aminra-frontend-1" 2>/dev/null || true)"
    printf 'backend=%s frontend=%s\n' "${backend_status:-missing}" "${frontend_status:-missing}"
    if [[ "$backend_status" == "healthy" && "$frontend_status" == "healthy" ]]; then
      return 0
    fi
    sleep 3
  done
  echo "ERROR: services did not become healthy before local smoke" >&2
  docker compose ps aminra-backend aminra-frontend >&2 || true
  exit 76
}

public_smoke() {
  section "Public URL smoke"
  curl -fsS -o /tmp/aminra-public-home.html -w 'aminra.org HTTP %{http_code}\n' https://aminra.org | tee "$LOG_DIR/public-home.txt"
  curl -fsS -o /tmp/aminra-public-login.html -w 'business login HTTP %{http_code}\n' https://aminra.org/business/login | tee "$LOG_DIR/public-login-business.txt"
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

verify_gates() {
  section "Static gates"
  PYTHONPYCACHEPREFIX=/tmp/aminra-pycache python3 -m py_compile "${BACKEND_FILES[@]}"
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
}

stage_and_commit() {
  section "Stage intended paths"
  git add -- "${STAGE_PATHS[@]}"
  git diff --cached --stat | tee "$LOG_DIR/staged-stat.txt"
  git diff --cached --check
  secret_scan_staged

  if [[ "$SKIP_COMMIT" == "true" ]]; then
    echo "SKIP_COMMIT=true; leaving changes staged."
    return
  fi

  section "Commit local checkpoint"
  if git diff --cached --quiet; then
    echo "No staged changes; skipping commit."
  else
    git commit -m "$COMMIT_MESSAGE" -m "- Add cache-aware backend base/app Docker split
- Harden modularization phase gate with bounded modes/timeouts
- Preserve verify/build/deploy separation for safer AMINRA runtime operations

Verified: backend focused pytest, frontend focused vitest, frontend lint, py_compile, alembic head smoke, git diff --check" | tee "$LOG_DIR/git-commit.txt"
  fi
}

build_images() {
  docker_build_probe

  section "Image IDs before build"
  printf 'backend-base-before=%s\n' "$(image_id "$BACKEND_BASE_IMAGE")" | tee "$LOG_DIR/image-before.txt"
  printf 'backend-app-before=%s\n' "$(image_id "$BACKEND_APP_IMAGE")" | tee -a "$LOG_DIR/image-before.txt"
  printf 'frontend-before=%s\n' "$(image_id "$FRONTEND_IMAGE")" | tee -a "$LOG_DIR/image-before.txt"

  case "$REBUILD_BACKEND_BASE" in
    true)
      run_timeout_retry "$BUILD_TIMEOUT_SECONDS" docker build \
        -f backend/Dockerfile.base \
        -t "$BACKEND_BASE_IMAGE" \
        backend
      ;;
    false)
      if [[ -z "$(image_id "$BACKEND_BASE_IMAGE")" ]]; then
        echo "ERROR: REBUILD_BACKEND_BASE=false but $BACKEND_BASE_IMAGE is missing" >&2
        exit 75
      fi
      echo "REBUILD_BACKEND_BASE=false; reusing existing $BACKEND_BASE_IMAGE" | tee "$LOG_DIR/backend-base-build-skip.txt"
      ;;
    auto)
      if [[ -n "$(image_id "$BACKEND_BASE_IMAGE")" ]]; then
        echo "REBUILD_BACKEND_BASE=auto and $BACKEND_BASE_IMAGE exists; reusing existing base image" | tee "$LOG_DIR/backend-base-build-skip.txt"
      else
        run_timeout_retry "$BUILD_TIMEOUT_SECONDS" docker build \
          -f backend/Dockerfile.base \
          -t "$BACKEND_BASE_IMAGE" \
          backend
      fi
      ;;
    *)
      echo "ERROR: REBUILD_BACKEND_BASE must be one of: auto, true, false" >&2
      exit 64
      ;;
  esac

  run_timeout_retry "$BUILD_TIMEOUT_SECONDS" docker compose build aminra-backend aminra-frontend

  section "Image IDs after build"
  printf 'backend-base-after=%s\n' "$(image_id "$BACKEND_BASE_IMAGE")" | tee "$LOG_DIR/image-after.txt"
  printf 'backend-app-after=%s\n' "$(image_id "$BACKEND_APP_IMAGE")" | tee -a "$LOG_DIR/image-after.txt"
  printf 'frontend-after=%s\n' "$(image_id "$FRONTEND_IMAGE")" | tee -a "$LOG_DIR/image-after.txt"
}

migrate_db() {
  section "Apply DB migration"
  ./scripts/db-migrate.sh current | tee "$LOG_DIR/alembic-current-before.txt" || true
  ./scripts/db-migrate.sh upgrade head | tee "$LOG_DIR/alembic-upgrade.txt"
  ./scripts/db-migrate.sh current | tee "$LOG_DIR/alembic-current-after.txt"
}

deploy_images() {
  section "Recreate local production containers from built images"
  docker compose up -d --no-deps aminra-backend aminra-frontend | tee "$LOG_DIR/docker-compose-up.txt"
  docker compose ps aminra-backend aminra-frontend | tee "$LOG_DIR/docker-ps-after.txt"
}

hot_restart_local() {
  section "Hot restart local backend after source sync"
  sync_backend_files_into_container
  docker compose restart aminra-backend | tee "$LOG_DIR/hot-restart-backend.txt"
  docker compose ps aminra-backend aminra-frontend | tee "$LOG_DIR/docker-ps-after-hot-restart.txt"
}

post_deploy_checks() {
  wait_for_local_services

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
}

section "Preflight status"
echo "MODE=$MODE" | tee "$LOG_DIR/mode.txt"
printf 'BUILD_RETRIES=%s\nREBUILD_BACKEND_BASE=%s\n' "$BUILD_RETRIES" "$REBUILD_BACKEND_BASE" | tee "$LOG_DIR/build-policy.txt"
git branch --show-current | tee "$LOG_DIR/git-branch.txt"
git status --short | tee "$LOG_DIR/git-status-before.txt"
docker compose ps | tee "$LOG_DIR/docker-ps-before.txt"
docker system df | tee "$LOG_DIR/docker-system-df-before.txt"

case "$MODE" in
  verify-only)
    verify_gates
    ;;
  build-only)
    build_images
    ;;
  hot-restart-local)
    verify_gates
    hot_restart_local
    post_deploy_checks
    ;;
  immutable-deploy)
    verify_gates
    stage_and_commit
    build_images
    migrate_db
    deploy_images
    post_deploy_checks
    ;;
  *)
    echo "ERROR: unknown MODE=$MODE" >&2
    exit 64
    ;;
esac

section "DONE"
git --no-pager log --oneline -1 | tee "$LOG_DIR/final-commit.txt"
docker system df | tee "$LOG_DIR/docker-system-df-after.txt"
echo "Evidence: $LOG_DIR"
