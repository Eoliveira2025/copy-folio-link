#!/bin/bash
set -e

# CopyTrade Pro - V3 Institutional Monitoring Deployment Script
# Target: Ubuntu Server /opt/copytrade

echo "=== MetaApi V3 Monitoring Deployment ==="

# 1. Environment Check
if [ ! -f "backend/.env" ]; then
    echo "Error: backend/.env not found. Please ensure you are in the project root."
    exit 1
fi

# 2. Add new ENV variables if missing
grep -q "RECONCILIATION_ENABLED" backend/.env || echo "RECONCILIATION_ENABLED=true" >> backend/.env

echo "Applying Database Migrations..."
cd backend && alembic upgrade head
cd ..

echo "Generating frontend build..."
npm install && npm run build

echo "Setting up Systemd Monitoring Service..."
cat <<EOF > /tmp/copytrade-v3-monitor.service
[Unit]
Description=CopyTrade Pro V3 Monitoring Worker
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/copytrade/backend
EnvironmentFile=/opt/copytrade/backend/.env
ExecStart=/opt/copytrade/backend/venv/bin/python scripts/monitor_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/copytrade-v3-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable copytrade-v3-monitor
sudo systemctl restart copytrade-v3-monitor

echo "=== Deployment Complete ==="
echo "Monitor logs: journalctl -u copytrade-v3-monitor -f"
echo "Check health: curl http://localhost:8000/api/v1/metaapi/admin/health"
