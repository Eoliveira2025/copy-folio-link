#!/bin/bash
# Rollback script for V3 Monitoring

echo "Stopping and disabling V3 Monitor service..."
sudo systemctl stop copytrade-v3-monitor || true
sudo systemctl disable copytrade-v3-monitor || true
sudo rm /etc/systemd/system/copytrade-v3-monitor.service || true
sudo systemctl daemon-reload

echo "Reverting database migration..."
cd backend && alembic downgrade 021_add_metaapi_reconciliation
cd ..

echo "Monitoring worker removed. Frontend/Backend code will remain but flag V3_COPY_ENABLED=false will hide it."
echo "Please set V3_COPY_ENABLED=false and RECONCILIATION_ENABLED=false in backend/.env if needed."
