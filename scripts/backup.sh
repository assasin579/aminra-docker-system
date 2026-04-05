#!/bin/bash
# =============================================================================
# AMINRA Docker System - Backup Script
# Backs up PostgreSQL, Qdrant snapshots, and Docker volume data.
# =============================================================================

set -euo pipefail

# ── Project root (one level up from scripts/) ────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_PROJECT="aminra-docker-system"

# ── Defaults ─────────────────────────────────────────────────────────────────
BACKUP_ROOT="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR=""
DO_DB=true
DO_QDRANT=true
DO_VOLUMES=true

# ── Container / DB settings ──────────────────────────────────────────────────
PG_CONTAINER="${COMPOSE_PROJECT}-postgres-db-1"
PG_USER="aminra_user"
PG_DB="aminra"

QDRANT_CONTAINER="${COMPOSE_PROJECT}-qdrant-db-1"
QDRANT_HOST_PORT=6433
QDRANT_COLLECTION="halal_kb"
QDRANT_API_KEY="${QDRANT_API_KEY:-$(grep '^QDRANT_API_KEY=' "${PROJECT_DIR}/.env" 2>/dev/null | cut -d= -f2)}"

VOLUME_LIST=("upload-data" "review-data" "template-data")

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-only)
            DO_QDRANT=false; DO_VOLUMES=false; shift ;;
        --qdrant-only)
            DO_DB=false; DO_VOLUMES=false; shift ;;
        --volumes-only)
            DO_DB=false; DO_QDRANT=false; shift ;;
        *)
            # Positional: custom backup directory
            BACKUP_DIR="$1"; shift ;;
    esac
done

if [[ -z "$BACKUP_DIR" ]]; then
    BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
fi

mkdir -p "$BACKUP_DIR"

ERRORS=0

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── 1. PostgreSQL backup ────────────────────────────────────────────────────
if $DO_DB; then
    log "Backing up PostgreSQL database '${PG_DB}'..."
    PG_DUMP_FILE="${BACKUP_DIR}/postgres_${PG_DB}.dump"
    if docker exec "$PG_CONTAINER" \
        pg_dump -U "$PG_USER" -d "$PG_DB" -Fc \
        > "$PG_DUMP_FILE" 2>&1; then
        log "  -> PostgreSQL dump saved: $(du -h "$PG_DUMP_FILE" | cut -f1)"
    else
        log "  !! PostgreSQL backup FAILED"
        ERRORS=$((ERRORS + 1))
    fi
fi

# ── 2. Qdrant snapshot ──────────────────────────────────────────────────────
if $DO_QDRANT; then
    log "Creating Qdrant snapshot for collection '${QDRANT_COLLECTION}'..."

    QDRANT_URL="http://localhost:${QDRANT_HOST_PORT}"
    AUTH_HEADER=""
    [[ -n "${QDRANT_API_KEY:-}" ]] && AUTH_HEADER="-H api-key:${QDRANT_API_KEY}"

    # Create snapshot via host curl
    SNAP_RESPONSE=$(curl -sf -X POST $AUTH_HEADER \
        "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots" 2>&1) || true

    SNAP_NAME=$(echo "$SNAP_RESPONSE" | grep -oP '"name"\s*:\s*"\K[^"]+' || true)

    if [[ -n "$SNAP_NAME" ]]; then
        QDRANT_SNAP_FILE="${BACKUP_DIR}/qdrant_${QDRANT_COLLECTION}.snapshot"
        if curl -sf $AUTH_HEADER \
            "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${SNAP_NAME}" \
            -o "$QDRANT_SNAP_FILE" 2>&1; then
            log "  -> Qdrant snapshot saved: $(du -h "$QDRANT_SNAP_FILE" | cut -f1)"
        else
            log "  !! Failed to download Qdrant snapshot"
            ERRORS=$((ERRORS + 1))
        fi

        # Clean up snapshot in Qdrant storage
        curl -sf -X DELETE $AUTH_HEADER \
            "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${SNAP_NAME}" \
            2>&1 || true
    else
        log "  !! Qdrant snapshot creation FAILED (response: ${SNAP_RESPONSE:-empty})"
        ERRORS=$((ERRORS + 1))
    fi
fi

# ── 3. Docker volume backups ────────────────────────────────────────────────
if $DO_VOLUMES; then
    for VOL in "${VOLUME_LIST[@]}"; do
        FULL_VOL="${COMPOSE_PROJECT}_${VOL}"
        TAR_FILE="${BACKUP_DIR}/volume_${VOL}.tar.gz"
        log "Backing up volume '${FULL_VOL}'..."

        if docker run --rm \
            -v "${FULL_VOL}:/data:ro" \
            -v "${BACKUP_DIR}:/backup" \
            alpine tar czf "/backup/volume_${VOL}.tar.gz" -C /data . 2>&1; then
            log "  -> Volume archive saved: $(du -h "$TAR_FILE" | cut -f1)"
        else
            log "  !! Volume backup FAILED for ${VOL}"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "========== Backup Summary =========="
echo "Directory : ${BACKUP_DIR}"
echo "Timestamp : ${TIMESTAMP}"
echo "------------------------------------"
if [[ -d "$BACKUP_DIR" ]]; then
    ls -lhS "$BACKUP_DIR" | tail -n +2
fi
echo "------------------------------------"
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "Total size: ${TOTAL_SIZE}"
echo "Errors    : ${ERRORS}"
echo "===================================="

if [[ $ERRORS -gt 0 ]]; then
    exit 1
fi
exit 0
