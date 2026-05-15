import logging
import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import get_settings
from app.models.metaapi import MetaApiAccount, MetaApiAccountType, CopyFactorySubscription, MetaApiEvent
from app.services.metaapi.client import MetaApiClient
from app.services.metaapi.copyfactory import CopyFactoryService
from app.services.metaapi.institutional import MetaApiAccountSyncService
import json

settings = get_settings()
logger = logging.getLogger(__name__)

class MetaApiService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = MetaApiClient()
        self.cf = CopyFactoryService()
        self.sync_service = MetaApiAccountSyncService(db)

    async def log_event(self, account_id: Optional[Any], event_type: str, message: str, payload: Optional[Dict] = None):
        event = MetaApiEvent(
            account_id=account_id,
            event_type=event_type,
            message=message,
            payload=json.dumps(payload) if payload else None
        )
        self.db.add(event)
        await self.db.commit()

    async def create_and_deploy_account(self, user_id: Any, data: Dict[str, Any]) -> MetaApiAccount:
        # Check if already exists in DB
        stmt = select(MetaApiAccount).where(MetaApiAccount.login == data["login"])
        result = await self.db.execute(stmt)
        db_account = result.scalars().first()

        if not db_account:
            db_account = MetaApiAccount(
                user_id=user_id,
                login=data["login"],
                server=data["server"],
                name=data["name"],
                account_type=data["type"]
            )
            self.db.add(db_account)
            await self.db.flush()

        try:
            # 1. Create in MetaApi with appropriate roles
            roles = ['PROVIDER'] if data.get("type") == MetaApiAccountType.MASTER else ['SUBSCRIBER']
            
            ma_account = await self.client.create_account(
                name=data["name"],
                login=data["login"],
                server=data["server"],
                password=data["password"],
                roles=roles
            )
            
            db_account.metaapi_account_id = ma_account["id"]
            await self.db.commit()

            # 2. Deploy
            await self.client.deploy_account(db_account.metaapi_account_id)
            db_account.deployment_status = "DEPLOYING"
            db_account.connection_status = "CONNECTING"
            await self.db.commit()
            
            # Start background task to wait for connection
            asyncio.create_task(self._wait_and_update_status(db_account.id, db_account.metaapi_account_id))
            
            await self.log_event(db_account.id, "ACCOUNT_CREATED", f"Account {data['login']} created and deployment started")
            
            return db_account
        except Exception as e:
            logger.error(f"Error creating MetaApi account: {e}")
            await self.log_event(db_account.id, "CREATION_ERROR", str(e))
            raise e

    async def _wait_and_update_status(self, db_id: Any, ma_id: str):
        """Background task to wait for connection and update DB."""
        await asyncio.sleep(5)
        res = await self.client.wait_until_connected(ma_id, timeout=120)
        
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            stmt = select(MetaApiAccount).where(MetaApiAccount.id == db_id)
            result = await db.execute(stmt)
            account = result.scalars().first()
            if account:
                # Use institutional sync service for a full refresh
                sync_service = MetaApiAccountSyncService(db)
                await sync_service.sync_account(account)
                logger.info(f"Background status update for {ma_id}: {account.connection_status}")

    async def list_accounts(self) -> List[MetaApiAccount]:
        stmt = select(MetaApiAccount).order_by(MetaApiAccount.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_account_status(self, account_id: Any) -> Dict[str, Any]:
        stmt = select(MetaApiAccount).where(MetaApiAccount.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalars().first()
        if not account or not account.metaapi_account_id:
            return {"status": "NOT_FOUND"}
        
        try:
            await self.sync_service.sync_account(account)
            return {
                "id": account.metaapi_account_id,
                "connectionStatus": account.connection_status,
                "deploymentStatus": account.deployment_status,
                "connected": account.connection_status == "CONNECTED"
            }
        except Exception as e:
            logger.error(f"Error fetching status for {account.metaapi_account_id}: {e}")
            return {"error": str(e), "id": account.metaapi_account_id, "connectionStatus": "ERROR"}

    async def deploy_account(self, account_id: Any):
        stmt = select(MetaApiAccount).where(MetaApiAccount.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalars().first()
        if account and account.metaapi_account_id:
            res = await self.client.deploy_account(account.metaapi_account_id)
            account.deployment_status = "DEPLOYING"
            await self.db.commit()
            await self.log_event(account.id, "DEPLOY_REQUESTED", "Manual deploy requested")
            return res
        return {"error": "Account not found"}

    async def remove_account(self, account_id: Any):
        stmt = select(MetaApiAccount).where(MetaApiAccount.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalars().first()
        if account:
            if account.metaapi_account_id:
                await self.client.remove_account(account.metaapi_account_id)
            await self.db.delete(account)
            await self.db.commit()
            return {"status": "REMOVED"}
        return {"error": "Account not found"}
