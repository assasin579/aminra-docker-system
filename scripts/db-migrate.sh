#!/usr/bin/env bash
# db-migrate.sh — Alembic migration wrapper for AMINRA Docker System
#
# Usage:
#   ./scripts/db-migrate.sh current              # show current revision
#   ./scripts/db-migrate.sh upgrade              # upgrade to head
#   ./scripts/db-migrate.sh downgrade -1         # downgrade one revision
#   ./scripts/db-migrate.sh stamp                # stamp existing DB as head (baseline)
#   ./scripts/db-migrate.sh new "description"    # create a new migration
#   ./scripts/db-migrate.sh history              # show migration history

set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
BACKEND_SERVICE="aminra-backend"

# Resolve docker compose command
if docker compose version &>/dev/null; then
    DC="docker compose -f $COMPOSE_FILE"
else
    DC="docker-compose -f $COMPOSE_FILE"
fi

run_alembic() {
    $DC exec -w /app "$BACKEND_SERVICE" sh -c '. /vault/secrets/env.sh 2>/dev/null; alembic '"$*"
}

case "${1:-help}" in
    current)
        run_alembic current
        ;;
    upgrade)
        run_alembic upgrade "${2:-head}"
        ;;
    downgrade)
        if [[ -z "${2:-}" ]]; then
            echo "Error: downgrade requires a target (e.g. -1)" >&2
            exit 1
        fi
        run_alembic downgrade "$2"
        ;;
    stamp)
        run_alembic stamp "${2:-head}"
        echo "Database stamped. Alembic now tracks this DB at revision: ${2:-head}"
        ;;
    new)
        if [[ -z "${2:-}" ]]; then
            echo "Error: provide a migration description" >&2
            echo "  Usage: $0 new \"add user preferences table\"" >&2
            exit 1
        fi
        run_alembic revision -m "$2"
        echo "New migration created in backend/alembic/versions/"
        ;;
    history)
        run_alembic history --verbose
        ;;
    help|--help|-h)
        cat <<'USAGE'
AMINRA Database Migration Tool

Usage: ./scripts/db-migrate.sh <command> [args]

Commands:
  current              Show current migration revision
  upgrade [target]     Upgrade database (default: head)
  downgrade <target>   Downgrade database (e.g. -1)
  stamp [target]       Stamp DB at revision without running migrations (default: head)
  new "description"    Create a new empty migration file
  history              Show full migration history

First-time setup for an EXISTING database:
  ./scripts/db-migrate.sh stamp     # marks DB as already at baseline

New database setup:
  ./scripts/db-migrate.sh upgrade   # runs all migrations from scratch
USAGE
        ;;
    *)
        echo "Unknown command: $1 — run '$0 help' for usage" >&2
        exit 1
        ;;
esac
