#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CopyTrade Pro — PostgreSQL Backup Script
# Runs daily at 03:00 UTC via cron inside db-backup container
# Keeps 30 days of backups
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

BACKUP_DIR="/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/copytrade_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30

echo "[$(date)] Starting backup..."

# Create compressed backup
pg_dump -Fc --no-acl --no-owner | gzip > "$BACKUP_FILE"

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup complete: $BACKUP_FILE ($BACKUP_SIZE)"

# Remove old backups
find "$BACKUP_DIR" -name "copytrade_*.sql.gz" -mtime +$RETENTION_DAYS -delete
REMAINING=$(find "$BACKUP_DIR" -name "copytrade_*.sql.gz" | wc -l)
echo "[$(date)] Cleanup done. $REMAINING backups retained."
