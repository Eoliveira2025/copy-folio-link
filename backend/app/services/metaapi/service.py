import logging
import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import get_settings
from app.models.metaapi import MetaApiAccount, MetaApiAccountType, MetaApiSubscription, MetaApiEvent
from app.services.metaapi.client import MetaApiClient
from app.services.metaapi.copyfactory import CopyFactoryService
import json

settings = get_settings()
logger = logging.getLogger(__name__)

class MetaApiService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = MetaApiClient()
        self.cf = CopyFactoryService()

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
            # 1. Create in MetaApi
            ma_account = await self.client.create_account(
                name=data["name"],
                login=data["login"],
                server=data["server"],
                password=data["password"]
            )
            
            db_account.metaapi_account_id = ma_account["id"]
            await self.db.commit()

            # 2. Deploy
            await self.client.deploy_account(db_account.metaapi_account_id)
            db_account.deployment_status = "DEPLOYING"
            await self.db.commit()
            
            await self.log_event(db_account.id, "ACCOUNT_CREATED", f"Account {data['login']} created and deployment started")
            
            return db_account
        except Exception as e:
            logger.error(f"Error creating MetaApi account: {e}")
            await self.log_event(db_account.id, "CREATION_ERROR", str(e))
            raise e

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
            status = await self.client.get_account(account.metaapi_account_id)
            # Update DB cache
            account.connection_status = status.get("connectionStatus", "UNKNOWN")
            account.deployment_status = status.get("deploymentStatus", "UNKNOWN")
            await self.db.commit()
            return status
        except Exception as e:
            return {"error": str(e)}

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

    async def create_cf_provider(self, master_id: Any):
        stmt = select(MetaApiAccount).where(MetaApiAccount.id == master_id)
        result = await self.db.execute(stmt)
        account = result.scalars().first()
        
        if not account or account.account_type != MetaApiAccountType.MASTER:
            raise Exception("Invalid master account")
            
        res = await self.cf.create_strategy_provider(account.name, account.metaapi_account_id)
        account.copyfactory_strategy_id = res["strategy_id"]
        await self.db.commit()
        await self.log_event(account.id, "CF_PROVIDER_CREATED", f"Strategy provider created: {res['strategy_id']}")
        return res

    async def subscribe_client(self, client_id: Any, master_id: Any, risk_ratio: float):
        stmt_c = select(MetaApiAccount).where(MetaApiAccount.id == client_id)
        res_c = await self.db.execute(stmt_c)
        client = res_c.scalars().first()
        
        stmt_m = select(MetaApiAccount).where(MetaApiAccount.id == master_id)
        res_m = await self.db.execute(stmt_m)
        master = res_m.scalars().first()
        
        if not client or not master or not master.copyfactory_strategy_id:
            raise Exception("Client or Master Strategy not ready")
            
        res = await self.cf.subscribe_account(client.metaapi_account_id, master.copyfactory_strategy_id, risk_ratio)
        
        sub = MetaApiSubscription(
            client_account_id=client.id,
            master_account_id=master.id,
            copyfactory_subscription_id=res["subscription_id"],
            risk_ratio=risk_ratio
        )
        self.db.add(sub)
        await self.db.commit()
        await self.log_event(client.id, "CF_SUBSCRIBED", f"Subscribed to master {master.login}")
        return res

    async def list_subscriptions(self):
        stmt = select(MetaApiSubscription).order_by(MetaApiSubscription.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
