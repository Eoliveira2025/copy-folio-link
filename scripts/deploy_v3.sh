#!/bin/bash

echo "=== CopyTrade Pro V3 MetaApi - Deploy Host Script ==="

# Check for .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create it from .env.example."
    exit 1
fi

# Build and Start containers
echo "Building and starting V3 services..."
docker-compose -f docker-compose.v3.yml up -d --build

echo ""
echo "V3 services started in detached mode."
echo "Check logs with: docker-compose -f docker-compose.v3.yml logs -f"
echo ""
echo "Health Checks:"
echo "API: http://localhost:8003/health"
echo "MetaApi: http://localhost:8003/health/metaapi"
echo "CopyFactory: http://localhost:8003/health/copyfactory"
