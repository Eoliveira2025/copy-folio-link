import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.metaapi import (
    MetaApiAccount, CopyFactoryStrategy, CopyFactorySubscription, 
    StrategySwitchRequest, MetaApiAccountMetric, MetaApiEvent
)
from app.services.metaapi.client import MetaApiClient
from app.services.metaapi.copyfactory import CopyFactoryService

settings = get_settings()
logger = logging.getLogger(__name__)

class MetaApiAccountSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = MetaApiClient()

    async def sync_account(self, account: MetaApiAccount):
        """Sync status, metrics and positions for a MetaApi account."""
        if not settings.V3_COPY_ENABLED:
            return

        if not account.metaapi_account_id:
            return

        try:
            # 1. Sync connection/deployment status
            status = await self.client.get_account(account.metaapi_account_id)
            account.connection_status = status.get("connection_status", account.connection_status)
            account.deployment_status = status.get("deployment_status", account.deployment_status)

            # 2. If connected, sync metrics and positions
            if account.connection_status == "CONNECTED":
                # Get metrics
                info = await self.client.get_account_information(account.metaapi_account_id)
                if info:
                    account.last_balance = info.get("balance", account.last_balance)
                    account.last_equity = info.get("equity", account.last_equity)
                    account.last_margin = info.get("margin", account.last_margin)
                    account.last_free_margin = info.get("freeMargin", account.last_free_margin)
                    account.last_profit_loss = info.get("profit", account.last_profit_loss)

                # Get positions
                positions = await self.client.get_positions(account.metaapi_account_id)
                account.last_positions_count = len(positions)
                account.last_positions_json = [p if isinstance(p, dict) else str(p) for p in positions]
                
                # Update sync timestamp
                account.last_sync_at = datetime.now(timezone.utc)

                # 3. Save snapshot in metrics table
                metric = MetaApiAccountMetric(
                    account_id=account.id,
                    balance=account.last_balance,
                    equity=account.last_equity,
                    margin=account.last_margin,
                    free_margin=account.last_free_margin,
                    profit_loss=account.last_profit_loss,
                    positions_count=account.last_positions_count,
                    positions_json=account.last_positions_json
                )
                self.db.add(metric)

            await self.db.commit()
            logger.debug(f"Synced MetaApi account {account.login}: Balance={account.last_balance}, Positions={account.last_positions_count}")
        except Exception as e:
            logger.error(f"Error syncing MetaApi account {account.login}: {e}")
            await self.db.rollback()

    async def sync_all_accounts(self):
        """Sync all MetaApi accounts."""
        stmt = select(MetaApiAccount)
        result = await self.db.execute(stmt)
        accounts = result.scalars().all()
        for account in accounts:
            await self.sync_account(account)

class CopyFactoryStrategyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cf = CopyFactoryService()

    async def create_or_update_provider(self, strategy: CopyFactoryStrategy):
        """Ensure provider exists in CopyFactory for a strategy."""
        if not settings.COPYFACTORY_ENABLED:
            return

        stmt = select(MetaApiAccount).where(MetaApiAccount.id == strategy.master_account_id)
        res = await self.db.execute(stmt)
        master = res.scalars().first()

        if not master or not master.metaapi_account_id:
            raise Exception(f"Master account not found or not connected for strategy {strategy.strategy_code}")

        # Create/Update strategy in CopyFactory
        res_cf = await self.cf.create_strategy_provider(strategy.display_name, master.metaapi_account_id)
        strategy.copyfactory_strategy_id = res_cf["strategy_id"]
        
        # Update settings if needed (SDK 29+ might handle these in update_strategy)
        # For now we use the common fields
        
        await self.db.commit()
        return strategy

class CopyFactorySubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cf = CopyFactoryService()

    async def subscribe_client(self, user_id: Any, client_account_id: Any, strategy_id: Any, risk_ratio: float = 1.0):
        """Subscribe a client account to a strategy."""
        if not settings.COPYFACTORY_ENABLED:
            return

        # Fetch entities
        stmt_c = select(MetaApiAccount).where(MetaApiAccount.id == client_account_id)
        client = (await self.db.execute(stmt_c)).scalars().first()
        
        stmt_s = select(CopyFactoryStrategy).where(CopyFactoryStrategy.id == strategy_id)
        strategy = (await self.db.execute(stmt_s)).scalars().first()

        if not client or not strategy or not strategy.copyfactory_strategy_id:
            raise Exception("Client account or Strategy not ready")

        # Create/Update subscriber in CopyFactory
        res = await self.cf.subscribe_account(
            client.metaapi_account_id, 
            strategy.copyfactory_strategy_id, 
            risk_ratio
        )

        # Update or create subscription in DB
        stmt_sub = select(CopyFactorySubscription).where(
            and_(CopyFactorySubscription.client_account_id == client_account_id, 
                 CopyFactorySubscription.strategy_id == strategy_id)
        )
        sub = (await self.db.execute(stmt_sub)).scalars().first()

        if not sub:
            sub = CopyFactorySubscription(
                user_id=user_id,
                client_account_id=client_account_id,
                strategy_id=strategy_id,
                copyfactory_subscription_id=strategy.copyfactory_strategy_id, # In our case we use strategy_id as key in CF
                risk_ratio=risk_ratio,
                status="ACTIVE"
            )
            self.db.add(sub)
        else:
            sub.status = "ACTIVE"
            sub.risk_ratio = risk_ratio
            sub.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        return sub

    async def pause_subscription(self, subscription_id: Any):
        sub = await self.db.get(CopyFactorySubscription, subscription_id)
        if sub:
            # In CopyFactory, we can disable the subscriber or remove the subscription from the list
            # We'll just update the status to PAUSED locally and could update CF too
            sub.status = "PAUSED"
            await self.db.commit()
            return sub

class StrategySwitchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sync_service = MetaApiAccountSyncService(db)
        self.sub_service = CopyFactorySubscriptionService(db)

    async def request_switch(self, user_id: Any, target_strategy_id: Any, requested_by: str = "user"):
        """Request a strategy switch."""
        # Get current subscription
        stmt = select(CopyFactorySubscription).where(CopyFactorySubscription.user_id == user_id)
        sub = (await self.db.execute(stmt)).scalars().first()
        
        current_strategy_id = sub.strategy_id if sub else None
        
        # Check if already has a pending request
        stmt_req = select(StrategySwitchRequest).where(
            and_(StrategySwitchRequest.user_id == user_id, 
                 StrategySwitchRequest.status.in_(["REQUESTED", "PENDING_WAIT_FLAT"]))
        )
        existing_req = (await self.db.execute(stmt_req)).scalars().first()
        if existing_req:
            existing_req.target_strategy_id = target_strategy_id
            await self.db.commit()
            return existing_req

        # Create new request
        request = StrategySwitchRequest(
            user_id=user_id,
            current_strategy_id=current_strategy_id,
            target_strategy_id=target_strategy_id,
            status="REQUESTED",
            requested_by=requested_by
        )
        
        # Immediate check if flat
        if sub:
            stmt_acc = select(MetaApiAccount).where(MetaApiAccount.id == sub.client_account_id)
            client = (await self.db.execute(stmt_acc)).scalars().first()
            
            # Sync to be sure
            await self.sync_service.sync_account(client)
            
            if client.last_positions_count == 0:
                # Perform immediate switch
                await self._perform_switch(request, sub)
            else:
                request.status = "PENDING_WAIT_FLAT"
                request.has_open_positions_at_request = True
                request.open_positions_snapshot = client.last_positions_json
        else:
            # No current sub, just create it directly if client account exists
            # We'll assume the client account is already linked to the user
            request.status = "SWITCHED"
            request.switched_at = datetime.now(timezone.utc)
            # Logic to create subscription would go here if we had the client_account_id
        
        self.db.add(request)
        await self.db.commit()
        return request

    async def process_pending_switches(self):
        """Worker task to process switches when accounts become flat."""
        stmt = select(StrategySwitchRequest).where(StrategySwitchRequest.status == "PENDING_WAIT_FLAT")
        requests = (await self.db.execute(stmt)).scalars().all()
        
        for req in requests:
            # Get user's subscription and account
            stmt_sub = select(CopyFactorySubscription).where(CopyFactorySubscription.user_id == req.user_id)
            sub = (await self.db.execute(stmt_sub)).scalars().first()
            
            if not sub:
                req.status = "FAILED"
                req.notes = "Subscription not found during switch"
                await self.db.commit()
                continue
                
            stmt_acc = select(MetaApiAccount).where(MetaApiAccount.id == sub.client_account_id)
            client = (await self.db.execute(stmt_acc)).scalars().first()
            
            # Sync status
            await self.sync_service.sync_account(client)
            
            if client.last_positions_count == 0:
                await self._perform_switch(req, sub)
                await self.db.commit()

    async def _perform_switch(self, request: StrategySwitchRequest, subscription: CopyFactorySubscription):
        """Execute the actual strategy switch."""
        try:
            # Update subscription to new strategy
            await self.sub_service.subscribe_client(
                request.user_id, 
                subscription.client_account_id, 
                request.target_strategy_id, 
                subscription.risk_ratio
            )
            
            subscription.strategy_id = request.target_strategy_id
            request.status = "SWITCHED"
            request.switched_at = datetime.now(timezone.utc)
            logger.info(f"Strategy switch performed for user {request.user_id}: -> {request.target_strategy_id}")
        except Exception as e:
            logger.error(f"Error performing switch for user {request.user_id}: {e}")
            request.status = "FAILED"
            request.notes = str(e)

class V3HealthMonitor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = MetaApiClient()

    async def check_health(self):
        """Health check for V3 components."""
        if not settings.V3_ADMIN_ENABLED:
            return {"status": "DISABLED"}
            
        # Check masters
        stmt = select(CopyFactoryStrategy).where(CopyFactoryStrategy.is_active == True)
        strategies = (await self.db.execute(stmt)).scalars().all()
        
        issues = []
        for strategy in strategies:
            if not strategy.master_account_id:
                issues.append(f"Strategy {strategy.strategy_code} has no master account")
                continue
                
            stmt_m = select(MetaApiAccount).where(MetaApiAccount.id == strategy.master_account_id)
            master = (await self.db.execute(stmt_m)).scalars().first()
            
            if not master or master.connection_status != "CONNECTED":
                issues.append(f"Master account for {strategy.strategy_code} is {master.connection_status if master else 'MISSING'}")

        return {
            "status": "OK" if not issues else "WARNING",
            "issues": issues,
            "strategies_count": len(strategies),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
