import asyncio
import os
import sys
import logging

# Add the parent directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import get_settings
from app.workers.metaapi_v3_monitor import monitoring_worker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metaapi_v3_standalone_monitor")

async def main():
    settings = get_settings()
    if not settings.V3_COPY_ENABLED:
        logger.error("V3_COPY_ENABLED is not set to true. Exiting.")
        return

    logger.info("Starting standalone MetaApi V3 Monitoring Worker...")
    await monitoring_worker()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitoring worker stopped by user.")
    except Exception as e:
        logger.critical(f"Monitoring worker crashed: {e}")
