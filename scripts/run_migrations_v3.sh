#!/bin/bash

echo "=== CopyTrade Pro V3 - Running Migrations ==="

# Check if container is running
if [ ! "$(docker ps -q -f name=ctv3-postgres)" ]; then
    echo "Error: ctv3-postgres container is not running. Start it first with ./scripts/deploy_v3.sh"
    exit 1
fi

echo "Running SQL migrations on ctv3-postgres..."
docker exec -i ctv3-postgres psql -U postgres -d copytrade_v3 < migrations_v3/v3_metaapi.sql

echo "Migrations completed successfully."
