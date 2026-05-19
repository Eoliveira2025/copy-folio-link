import asyncio
import logging
from datetime import datetime, timezone
from app.core.database import AsyncSessionLocal
from app.services.metaapi.reconciliation import PositionReconciliationService
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.workers.metaapi_reconciliation")

async def run_metaapi_reconciliation_cycle():
    """Run a single reconciliation cycle."""
    logger.info("[RECON WORKER] Starting reconciliation cycle...")
    async with AsyncSessionLocal() as db:
        service = PositionReconciliationService(db)
        try:
            await service.detect_all_orphans()
            logger.info("[RECON WORKER] Cycle completed successfully.")
        except Exception as e:
            logger.error(f"[RECON WORKER] Error during cycle: {e}")

async def metaapi_reconciliation_worker():
    """Continuous worker for MetaApi position reconciliation."""
    if not settings.V3_COPY_ENABLED:
        logger.warning("[RECON WORKER] V3_COPY_ENABLED is false. Worker will not start.")
        return

    logger.info("[RECON WORKER] Worker started. Interval: 30 seconds.")
    
    while True:
        try:
            await run_metaapi_reconciliation_cycle()
        except Exception as e:
            logger.error(f"[RECON WORKER] Unexpected error in loop: {e}")
        
        # Wait for 30 seconds as requested
        await asyncio.sleep(30)

def start_reconciliation_worker():
    """Start the reconciliation worker in a background task."""
    loop = asyncio.get_event_loop()
    loop.create_task(metaapi_reconciliation_worker())
