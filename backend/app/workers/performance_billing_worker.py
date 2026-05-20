import asyncio
import logging
import signal
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.billing.performance_billing_service import PerformanceBillingService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("performance_billing_worker")

settings = get_settings()

# DB setup
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class PerformanceBillingWorker:
    def __init__(self):
        self.running = True
        self.interval = 300 # 5 minutes

    def stop(self, *args):
        logger.info("Stopping performance billing worker...")
        self.running = False

    async def run(self):
        logger.info("Starting performance billing worker...")
        
        while self.running:
            try:
                async with async_session() as db:
                    await PerformanceBillingService.run_automation(db)
            except Exception as e:
                logger.error(f"Error in performance billing worker loop: {e}")
                
            # Wait for interval or stop signal
            for _ in range(self.interval):
                if not self.running:
                    break
                await asyncio.sleep(1)

if __name__ == "__main__":
    worker = PerformanceBillingWorker()
    
    # Handle signals
    signal.signal(signal.SIGINT, worker.stop)
    signal.signal(signal.SIGTERM, worker.stop)
    
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Worker stopped.")
