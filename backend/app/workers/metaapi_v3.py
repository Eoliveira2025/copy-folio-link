import asyncio
import logging
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.metaapi.institutional import (
    MetaApiAccountSyncService, StrategySwitchService, V3HealthMonitor
)
from app.services.metaapi.reconciliation import PositionReconciliationService
from app.workers.metaapi_v3_monitor import start_monitor_worker

settings = get_settings()
logger = logging.getLogger("app.workers.metaapi_v3")

async def sync_accounts_worker():
    """Periodically sync MetaApi accounts."""
    while True:
        if settings.V3_COPY_ENABLED:
            logger.info("Starting periodic MetaApi account sync...")
            try:
                async with AsyncSessionLocal() as db:
                    sync_service = MetaApiAccountSyncService(db)
                    await sync_service.sync_all_accounts()
            except Exception as e:
                logger.error(f"Error in sync_accounts_worker: {e}")
        
        await asyncio.sleep(60) # Run every 60s

async def process_switches_worker():
    """Periodically process pending strategy switches."""
    while True:
        if settings.V3_COPY_ENABLED:
            logger.info("Processing pending strategy switches...")
            try:
                async with AsyncSessionLocal() as db:
                    switch_service = StrategySwitchService(db)
                    await switch_service.process_pending_switches()
            except Exception as e:
                logger.error(f"Error in process_switches_worker: {e}")
        
        await asyncio.sleep(30) # Run every 30s

async def health_check_worker():
    """Periodically run V3 health checks."""
    while True:
        if settings.V3_COPY_ENABLED:
            logger.info("Running MetaApi V3 health checks...")
            try:
                async with AsyncSessionLocal() as db:
                    monitor = V3HealthMonitor(db)
                    status = await monitor.check_health()
                    if status.get("status") == "WARNING":
                        logger.warning(f"MetaApi V3 Health Warning: {status.get('issues')}")
            except Exception as e:
                logger.error(f"Error in health_check_worker: {e}")
        
        await asyncio.sleep(60) # Run every 60s

async def reconciliation_worker():
    """Periodically run position reconciliation."""
    while True:
        if settings.V3_COPY_ENABLED:
            logger.info("Starting periodic position reconciliation...")
            try:
                async with AsyncSessionLocal() as db:
                    service = PositionReconciliationService(db)
                    await service.detect_all_orphans()
            except Exception as e:
                logger.error(f"Error in reconciliation_worker: {e}")
        
        await asyncio.sleep(60) # Run every 60s

async def start_metaapi_v3_workers():
    """Start all V3 background workers."""
    if not settings.V3_COPY_ENABLED:
        logger.info("MetaApi V3 Workers disabled (V3_COPY_ENABLED=false)")
        return

    logger.info("Starting MetaApi V3 background workers...")
    asyncio.create_task(sync_accounts_worker())
    asyncio.create_task(process_switches_worker())
    asyncio.create_task(health_check_worker())
    asyncio.create_task(reconciliation_worker())
