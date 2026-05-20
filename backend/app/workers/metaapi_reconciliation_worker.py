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
    logger.info("[RECON PERIODIC SCAN] Starting reconciliation cycle...")
    async with AsyncSessionLocal() as db:
        service = PositionReconciliationService(db)
        try:
            await service.detect_all_orphans()
            logger.info("[RECON PERIODIC DONE] Cycle completed successfully.")
        except Exception as e:
            logger.error(f"[RECON ERROR] Error during cycle: {e}")

async def metaapi_reconciliation_worker():
    """Continuous worker for MetaApi position reconciliation."""
    if not settings.V3_COPY_ENABLED:
        logger.warning("[RECON WORKER] V3_COPY_ENABLED is false. Worker will not start.")
        return

    # Use interval from settings or default to 300 seconds
    interval = getattr(settings, 'RECONCILIATION_INTERVAL', 300)
    
    logger.info(f"[RECON WORKER STARTED] Worker active. Interval: {interval} seconds.")
    
    while True:
        try:
            await run_metaapi_reconciliation_cycle()
        except Exception as e:
            logger.error(f"[RECON ERROR] Unexpected error in loop: {e}")
        
        # Wait for the configured interval
        await asyncio.sleep(interval)

if __name__ == "__main__":
    # If run directly as a module
    asyncio.run(metaapi_reconciliation_worker())
