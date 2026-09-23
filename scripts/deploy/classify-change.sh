#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy/classify-change.sh [--base <git-ref>]
  scripts/deploy/classify-change.sh --paths <path> [path...]

Outputs exactly one lane:
  docs-only | frontend-only | backend-only | infra-stateful | mixed

Policy:
  - frontend-only/backend-only lanes are safe for --no-deps service deploys.
  - infra-stateful and mixed fail closed in auto-deploy unless explicitly approved.
EOF
}

mode="git"
base="HEAD"
paths=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --paths)
      mode="paths"
      shift
      while [[ $# -gt 0 ]]; do
        paths+=("$1")
        shift
      done
      ;;
    --base)
      base="${2:?--base requires a git ref}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if [[ "$mode" == "git" ]]; then
  mapfile -t paths < <(
    { git diff --name-only "$base" --; git diff --name-only --cached --; git ls-files --others --exclude-standard; } \
      | sed '/^$/d' | sort -u
  )
fi

if [[ ${#paths[@]} -eq 0 ]]; then
  echo "docs-only"
  exit 0
fi

has_docs=false
has_frontend=false
has_backend=false
has_stateful=false
has_other=false

for path in "${paths[@]}"; do
  path="${path#./}"

  case "$path" in
    docker-compose*.yml|compose*.yml|*/docker-compose*.yml|*/compose*.yml|docker-compose.registry.yml)
      has_stateful=true
      continue
      ;;
    .env|.env.*|*/.env|*/.env.*|vault/*|monitoring/*|nginx/*|keycloak/*|keycloak-themes/*|databases/*)
      has_stateful=true
      continue
      ;;
    backend/alembic/*|backend/migrations/*|backend/Dockerfile|backend/entrypoint.sh|backend/docker-compose.yml)
      has_stateful=true
      continue
      ;;
    scripts/deploy/*|scripts/automation/modularization-phase-gate.sh)
      has_stateful=true
      continue
      ;;
  esac

  case "$path" in
    frontend/aminra-web/*)
      has_frontend=true
      ;;
    backend/*)
      has_backend=true
      ;;
    docs/*|README.md|*.md|*.MD|AGENTS.md|CLAUDE.md|tests/*)
      has_docs=true
      ;;
    *)
      has_other=true
      ;;
  esac
done

if [[ "$has_stateful" == true ]]; then
  echo "infra-stateful"
elif [[ "$has_other" == true ]]; then
  echo "mixed"
elif [[ "$has_frontend" == true && "$has_backend" == true ]]; then
  echo "mixed"
elif [[ "$has_frontend" == true ]]; then
  echo "frontend-only"
elif [[ "$has_backend" == true ]]; then
  echo "backend-only"
else
  echo "docs-only"
fi
