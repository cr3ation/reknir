#!/bin/sh
# Automatic PostgreSQL backup script for Swedish 7-year retention requirement

BACKUP_DIR=${BACKUP_DIR:-/backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/reknir_backup_$TIMESTAMP.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create compressed backup
echo "Starting backup at $(date)"
pg_dump -h postgres -U ${POSTGRES_USER} ${POSTGRES_DB} | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup successful: $BACKUP_FILE"

    # Remove backups older than retention period (default: 7 years = 2555 days)
    find "$BACKUP_DIR" -name "reknir_backup_*.sql.gz" -type f -mtime +${BACKUP_KEEP_DAYS:-2555} -delete
    echo "Old backups cleaned up"
else
    echo "Backup failed!"
    exit 1
fi

echo "Backup completed at $(date)"
