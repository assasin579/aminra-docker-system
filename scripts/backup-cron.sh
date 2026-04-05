#!/bin/bash
# =============================================================================
# AMINRA Docker System - Cron Backup Wrapper
# Intended to be called by cron. Runs a full backup and prunes old ones.
#
# Example crontab entry (daily at 02:00):
#   0 2 * * * /home/user/Documents/aminra-docker-system/scripts/backup-cron.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_ROOT="${PROJECT_DIR}/backups"
LOG_FILE="${BACKUP_ROOT}/backup.log"
KEEP_DAYS=7

mkdir -p "$BACKUP_ROOT"

{
    echo "============================================"
    echo "Cron backup started: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================"

    # Run the main backup script
    if "${PROJECT_DIR}/scripts/backup.sh"; then
        echo "Backup completed successfully."
    else
        echo "Backup completed with errors (exit code: $?)."
    fi

    # Prune old backups: keep only the last $KEEP_DAYS daily directories
    # Backup directories are named with timestamps (YYYYMMDD_HHMMSS)
    BACKUP_DIRS=$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d | sort -r)
    COUNT=0
    while IFS= read -r DIR; do
        COUNT=$((COUNT + 1))
        if [[ $COUNT -gt $KEEP_DAYS ]]; then
            echo "Pruning old backup: $(basename "$DIR")"
            rm -rf "$DIR"
        fi
    done <<< "$BACKUP_DIRS"

    echo "Retained $((COUNT > KEEP_DAYS ? KEEP_DAYS : COUNT)) of ${COUNT} backup(s)."
    echo "Cron backup finished: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
} >> "$LOG_FILE" 2>&1
