#!/bin/bash
# Run integration tests against running backend
# Usage: ./scripts/test.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export TEST_BACKEND_URL="${TEST_BACKEND_URL:-http://localhost:8100}"

echo "Running tests against $TEST_BACKEND_URL ..."

# Run from host using pytest (needs: pip install pytest httpx)
cd "$PROJECT_DIR/backend"
python -m pytest tests/ -v --tb=short "$@"
