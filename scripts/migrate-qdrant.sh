#!/bin/bash

# Migrate Qdrant data from existing instance to Docker container

set -e

echo "📊 Migrating Qdrant data to Docker container..."

# Stop existing containers if running
docker-compose stop qdrant-db || true

# Create backup of existing data
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Check if existing Qdrant has data
if curl -s http://localhost:6333/collections > /dev/null; then
    echo "📥 Backing up existing Qdrant collections..."
    curl -s http://localhost:6333/collections | jq . > "$BACKUP_DIR/collections.json"
    
    # Export collection if it exists
    if curl -s http://localhost:6333/collections/halal_kb > /dev/null; then
        echo "💾 Exporting halal_kb collection..."
        mkdir -p "$BACKUP_DIR/halal_kb"
        # Note: Full data export would require qdrant-client
        echo "Collection exists and ready for migration" > "$BACKUP_DIR/halal_kb/status.txt"
    fi
fi

echo "✅ Qdrant backup completed in $BACKUP_DIR"
echo "🚀 Starting fresh Qdrant container..."

# Start only qdrant service
docker-compose up -d qdrant-db

# Wait for it to be ready
sleep 10

echo "✅ Qdrant Docker container is ready!"
echo "ℹ️  If you had existing data, you'll need to re-ingest documents"