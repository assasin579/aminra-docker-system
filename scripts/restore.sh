#!/bin/bash
# =============================================================================
# AMINRA Docker System - Restore Script
# Restores PostgreSQL, Qdrant, and Docker volume data from a backup directory.
# =============================================================================

set -euo pipefail

# ── Project root ─────────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_PROJECT="aminra-docker-system"

# ── Container / DB settings ──────────────────────────────────────────────────
PG_CONTAINER="${COMPOSE_PROJECT}-postgres-db-1"
PG_USER="aminra_user"
PG_DB="aminra"

QDRANT_CONTAINER="${COMPOSE_PROJECT}-qdrant-db-1"
QDRANT_HOST_PORT=6433
QDRANT_COLLECTION="halal_kb"
QDRANT_API_KEY="${QDRANT_API_KEY:-$(grep '^QDRANT_API_KEY=' "${PROJECT_DIR}/.env" 2>/dev/null | cut -d= -f2)}"

VOLUME_LIST=("upload-data" "review-data" "template-data")

# ── Defaults ─────────────────────────────────────────────────────────────────
DO_DB=true
DO_QDRANT=true
DO_VOLUMES=true
AUTO_YES=false
BACKUP_DIR=""

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-only)
            DO_QDRANT=false; DO_VOLUMES=false; shift ;;
        --qdrant-only)
            DO_DB=false; DO_VOLUMES=false; shift ;;
        --volumes-only)
            DO_DB=false; DO_QDRANT=false; shift ;;
        --yes|-y)
            AUTO_YES=true; shift ;;
        -*)
            echo "Unknown flag: $1" >&2; exit 1 ;;
        *)
            BACKUP_DIR="$1"; shift ;;
    esac
done

if [[ -z "$BACKUP_DIR" ]]; then
    echo "Usage: restore.sh [--db-only|--qdrant-only|--volumes-only] [--yes] <backup-directory>"
    exit 1
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "Error: Backup directory does not exist: ${BACKUP_DIR}" >&2
    exit 1
fi

# Resolve to absolute path
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Show what will be restored ───────────────────────────────────────────────
echo "========== Restore Plan =========="
echo "Source: ${BACKUP_DIR}"
echo "----------------------------------"
$DO_DB      && echo "  [x] PostgreSQL  ($(ls "$BACKUP_DIR"/postgres_*.dump 2>/dev/null | head -1 || echo 'NOT FOUND'))"
$DO_QDRANT  && echo "  [x] Qdrant      ($(ls "$BACKUP_DIR"/qdrant_*.snapshot 2>/dev/null | head -1 || echo 'NOT FOUND'))"
$DO_VOLUMES && echo "  [x] Volumes     ($(ls "$BACKUP_DIR"/volume_*.tar.gz 2>/dev/null | wc -l) archives)"
echo "=================================="

# ── Confirmation ─────────────────────────────────────────────────────────────
if ! $AUTO_YES; then
    echo ""
    echo "WARNING: This will overwrite current data. This action cannot be undone."
    read -rp "Proceed with restore? [y/N] " CONFIRM
    case "$CONFIRM" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Restore cancelled."; exit 0 ;;
    esac
fi

ERRORS=0

# ── 1. Restore PostgreSQL ───────────────────────────────────────────────────
if $DO_DB; then
    PG_DUMP_FILE=$(ls "$BACKUP_DIR"/postgres_*.dump 2>/dev/null | head -1)
    if [[ -z "$PG_DUMP_FILE" ]]; then
        log "!! No PostgreSQL dump found in backup directory, skipping."
        ERRORS=$((ERRORS + 1))
    else
        log "Restoring PostgreSQL database '${PG_DB}' from $(basename "$PG_DUMP_FILE")..."

        # Stop services that hold DB connections to prevent partial-restore race conditions.
        # backend + arq-worker both maintain PG connection pools.
        log "  -> Stopping backend services (backend, arq-worker)..."
        docker compose -f "${PROJECT_DIR}/docker-compose.yml" stop backend arq-worker 2>/dev/null || true

        # Terminate any remaining connections (pgAdmin, leftover workers, etc.)
        docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
             WHERE datname = '$PG_DB' AND pid <> pg_backend_pid();" \
            >/dev/null 2>&1 || true

        # Drop + recreate for a clean slate (avoids --clean ordering issues with active objects)
        docker exec "$PG_CONTAINER" dropdb -U "$PG_USER" --if-exists "$PG_DB"
        docker exec "$PG_CONTAINER" createdb -U "$PG_USER" -O "$PG_USER" "$PG_DB"

        PG_RESTORE_ERR="/tmp/pg_restore_err_$$.log"
        if docker exec -i "$PG_CONTAINER" \
            pg_restore -U "$PG_USER" -d "$PG_DB" \
            --no-owner --no-acl \
            < "$PG_DUMP_FILE" 2>"$PG_RESTORE_ERR"; then
            log "  -> PostgreSQL restore completed."
        else
            ERROR_COUNT=$(grep -c "^pg_restore: error" "$PG_RESTORE_ERR" 2>/dev/null || echo 0)
            if (( ERROR_COUNT > 0 )); then
                log "  !! PostgreSQL restore FAILED ($ERROR_COUNT fatal errors):"
                grep "^pg_restore: error" "$PG_RESTORE_ERR" | sed 's/^/     /' >&2
                ERRORS=$((ERRORS + 1))
            else
                log "  -> PostgreSQL restore completed (with non-fatal warnings)."
            fi
        fi
        rm -f "$PG_RESTORE_ERR"

        # Restart services regardless of restore outcome so the app is not left stopped
        log "  -> Restarting backend services..."
        docker compose -f "${PROJECT_DIR}/docker-compose.yml" start backend arq-worker 2>/dev/null || true
    fi
fi

# ── 2. Restore Qdrant ───────────────────────────────────────────────────────
if $DO_QDRANT; then
    QDRANT_SNAP_FILE=$(ls "$BACKUP_DIR"/qdrant_*.snapshot 2>/dev/null | head -1)
    if [[ -z "$QDRANT_SNAP_FILE" ]]; then
        log "!! No Qdrant snapshot found in backup directory, skipping."
        ERRORS=$((ERRORS + 1))
    else
        log "Restoring Qdrant collection '${QDRANT_COLLECTION}' from $(basename "$QDRANT_SNAP_FILE")..."

        QDRANT_URL="http://localhost:${QDRANT_HOST_PORT}"
        AUTH_HEADER=""
        [[ -n "${QDRANT_API_KEY:-}" ]] && AUTH_HEADER="-H api-key:${QDRANT_API_KEY}"

        RESTORE_RESP=$(curl -sf -X POST $AUTH_HEADER \
            "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/upload?priority=snapshot" \
            -F "snapshot=@${QDRANT_SNAP_FILE}" 2>/dev/null) || true

        if echo "$RESTORE_RESP" | grep -q '"status".*"ok"'; then
            log "  -> Qdrant restore completed."
        else
            log "  !! Qdrant restore may have FAILED (response: ${RESTORE_RESP:-empty})"
            ERRORS=$((ERRORS + 1))
        fi
    fi
fi

# ── 3. Restore volumes ──────────────────────────────────────────────────────
if $DO_VOLUMES; then
    for VOL in "${VOLUME_LIST[@]}"; do
        FULL_VOL="${COMPOSE_PROJECT}_${VOL}"
        TAR_FILE="${BACKUP_DIR}/volume_${VOL}.tar.gz"

        if [[ ! -f "$TAR_FILE" ]]; then
            log "!! Volume archive not found for '${VOL}', skipping."
            ERRORS=$((ERRORS + 1))
            continue
        fi

        log "Restoring volume '${FULL_VOL}' from $(basename "$TAR_FILE")..."

        if docker run --rm \
            -v "${FULL_VOL}:/data" \
            -v "${BACKUP_DIR}:/backup:ro" \
            alpine sh -c "rm -rf /data/* && tar xzf /backup/volume_${VOL}.tar.gz -C /data" 2>/dev/null; then
            log "  -> Volume '${VOL}' restored."
        else
            log "  !! Volume restore FAILED for '${VOL}'"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "========== Restore Summary =========="
echo "Source : ${BACKUP_DIR}"
echo "Errors : ${ERRORS}"
echo "======================================"

if [[ $ERRORS -gt 0 ]]; then
    exit 1
fi
exit 0
