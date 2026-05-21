import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.metaapi import MetaApiAccount, MetaApiAccountMetric
from app.services.metaapi.http_client import HttpMetaApiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("metaapi_account_sync_worker")

async def sync_metaapi_accounts():
    """
    Worker to sync account information (balance, equity, etc.) for all connected MetaApi accounts.
    """
    logger.info("Starting MetaApi account sync cycle...")
    http_client = HttpMetaApiClient()
    
    async with SessionLocal() as session:
        # Query all CLIENT accounts that are CONNECTED and DEPLOYED
        query = select(MetaApiAccount).where(
            MetaApiAccount.account_type == "CLIENT",
            MetaApiAccount.connection_status == "CONNECTED",
            MetaApiAccount.deployment_status == "DEPLOYED",
            MetaApiAccount.metaapi_account_id.is_not(None)
        )
        
        result = await session.execute(query)
        accounts = result.scalars().all()
        
        logger.info(f"Found {len(accounts)} active accounts to sync.")
        
        for account in accounts:
            try:
                logger.info(f"Syncing account {account.login} (ID: {account.metaapi_account_id})")
                
                # Fetch info from internal service
                info = await http_client.get_account_information(account.metaapi_account_id)
                
                # Update account model
                account.last_balance = float(info.get("balance", 0))
                account.last_equity = float(info.get("equity", 0))
                account.last_margin = float(info.get("margin", 0))
                account.last_free_margin = float(info.get("free_margin", 0))
                account.last_profit_loss = float(info.get("profit", 0))
                account.last_sync_at = datetime.now(timezone.utc)
                account.updated_at = datetime.now(timezone.utc)
                
                # Also create a metric entry for history
                metric = MetaApiAccountMetric(
                    account_id=account.id,
                    balance=account.last_balance,
                    equity=account.last_equity,
                    margin=account.last_margin,
                    free_margin=account.last_free_margin,
                    profit_loss=account.last_profit_loss,
                    captured_at=datetime.now(timezone.utc)
                )
                session.add(metric)
                
                logger.info(f"Successfully synced account {account.login}. Balance: {account.last_balance}")
                
            except Exception as e:
                logger.error(f"Error syncing account {account.login}: {str(e)}")
                continue
                
        await session.commit()
        logger.info("Sync cycle completed.")

async def main():
    while True:
        try:
            await sync_metaapi_accounts()
        except Exception as e:
            logger.error(f"Critical error in sync worker: {e}")
            
        # Run every 5 minutes
        logger.info("Waiting 5 minutes for next cycle...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
