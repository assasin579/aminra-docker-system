#!/usr/bin/env bash
# Run backend tests inside the running container.
# Tests aren't baked into the production image, so we copy them in first.
#
# Usage:
#   ./run_tests.sh                     # run all tests
#   ./run_tests.sh tests/test_auth.py  # run a specific file
#   ./run_tests.sh --cov               # with coverage report

set -euo pipefail

CONTAINER="aminra-docker-system-aminra-backend-1"
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"

# Sync source + tests into container (overwrites each run).
# `docker cp` nests into existing dirs → remove targets first.
docker exec "$CONTAINER" rm -rf \
    /app/tests /app/services /app/auth /app/contracts \
    /app/templates/emails /app/templates/templates 2>/dev/null
docker exec "$CONTAINER" mkdir -p /app/templates
docker cp "$BACKEND_DIR/tests"            "$CONTAINER:/app/tests"
docker cp "$BACKEND_DIR/services"         "$CONTAINER:/app/services"
docker cp "$BACKEND_DIR/auth"             "$CONTAINER:/app/auth"
docker cp "$BACKEND_DIR/contracts"        "$CONTAINER:/app/contracts"
docker cp "$BACKEND_DIR/templates/emails" "$CONTAINER:/app/templates/emails"
docker cp "$BACKEND_DIR/pytest.ini"       "$CONTAINER:/app/pytest.ini"
docker cp "$BACKEND_DIR/app.py"           "$CONTAINER:/app/app.py"
docker cp "$BACKEND_DIR/Procfile"         "$CONTAINER:/app/Procfile"
docker cp "$BACKEND_DIR/Dockerfile"       "$CONTAINER:/app/Dockerfile"
docker cp "$BACKEND_DIR/env.example"      "$CONTAINER:/app/env.example"

# Default args: run all tests in tests/
ARGS=("${@:-tests/}")

# --cov shortcut → expand to pytest-cov flags
if [[ " ${ARGS[*]} " == *" --cov "* ]]; then
  ARGS=("${ARGS[@]/--cov/}")
  ARGS+=(--cov=. --cov-report=term-missing --cov-report=html --cov-fail-under=80)
fi

# Source Vault-injected env (JWT_SECRET, etc.) before pytest runs.
docker exec "$CONTAINER" sh -c ". /vault/secrets/env.sh 2>/dev/null; pytest $(printf '%q ' "${ARGS[@]}")"
