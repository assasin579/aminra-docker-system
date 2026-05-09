#!/bin/bash
# Keycloak database bootstrap — runs once on fresh postgres data dir.
# Creates dedicated `keycloak` database + role per ADR-005 Phase 1.
# Idempotent for already-existing role/db (init scripts only run on empty data dir,
# but DO {} block makes manual re-run safe).
set -euo pipefail

if [ -z "${KEYCLOAK_DB_PASSWORD:-}" ]; then
  echo "ERROR: KEYCLOAK_DB_PASSWORD env var not set on postgres container" >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  DO \$\$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
      CREATE ROLE keycloak WITH LOGIN ENCRYPTED PASSWORD '${KEYCLOAK_DB_PASSWORD}';
    END IF;
  END
  \$\$;
EOSQL

if ! psql --username "$POSTGRES_USER" -tAc "SELECT 1 FROM pg_database WHERE datname='keycloak'" | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -c "CREATE DATABASE keycloak OWNER keycloak;"
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -c "GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;"
