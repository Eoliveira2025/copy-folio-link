#!/bin/bash
set -e

echo "Starting CopyTrade Pro V3 API..."

# Wait for DB if needed (optional but recommended)
# For now, we assume docker-compose handles dependencies

# Run migrations if needed (we can add a check here)
# python -m app.core.migrations_run (placeholder if you have a migration runner)

# Start uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port 8003
