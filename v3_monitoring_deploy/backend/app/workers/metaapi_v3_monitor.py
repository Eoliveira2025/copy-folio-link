import asyncio
import logging
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.metaapi.institutional import V3HealthMonitor

settings = get_settings()
logger = logging.getLogger("app.workers.metaapi_v3_monitor")

async def monitoring_worker():
    """Periodically run detailed V3 monitoring and health scans."""
    while True:
        if settings.V3_COPY_ENABLED:
            logger.info("Starting MetaApi V3 monitoring scan...")
            try:
                async with AsyncSessionLocal() as db:
                    monitor = V3HealthMonitor(db)
                    # Run full scan (checks accounts + CF subscriptions)
                    result = await monitor.run_full_scan()
                    
                    stats = result.get("stats", {})
                    logger.info(
                        f"V3 Monitor Stats: Total={stats.get('total_accounts')}, "
                        f"Connected={stats.get('connected')}, Deployed={stats.get('deployed')}"
                    )
            except Exception as e:
                logger.error(f"Error in monitoring_worker: {e}")
        
        # Run every 5 minutes for full scan
        await asyncio.sleep(300)

async def start_monitor_worker():
    """Start the V3 monitor background worker."""
    if not settings.V3_COPY_ENABLED:
        logger.info("MetaApi V3 Monitor disabled (V3_COPY_ENABLED=false)")
        return

    logger.info("Starting MetaApi V3 Monitor worker...")
    asyncio.create_task(monitoring_worker())
