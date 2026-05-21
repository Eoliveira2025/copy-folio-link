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
    StrategySwitchRequest, MetaApiAccountMetric, MetaApiEvent,
    MetaApiMonitorEvent
)
from app.services.metaapi.http_client import HttpMetaApiClient
from app.services.metaapi.copyfactory import CopyFactoryService

settings = get_settings()
logger = logging.getLogger(__name__)

class MetaApiAccountSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = HttpMetaApiClient()

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
                    account.last_free_margin = info.get("free_margin", account.last_free_margin)
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
        self.client = HttpMetaApiClient()
        self.cf = CopyFactoryService()

    async def log_event(self, account_id: Optional[Any], severity: str, event_type: str, message: str, user_id: Optional[Any] = None):
        """Log a monitor event."""
        event = MetaApiMonitorEvent(
            metaapi_account_id=account_id,
            user_id=user_id,
            severity=severity,
            event_type=event_type,
            message=message
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(f"Monitor Event [{severity}]: {message}")

    async def check_health(self):
        """Detailed health check for V3 components."""
        if not settings.V3_COPY_ENABLED:
            return {"status": "DISABLED"}
            
        # Get all MetaApi accounts
        stmt = select(MetaApiAccount)
        res = await self.db.execute(stmt)
        accounts = res.scalars().all()
        
        stats = {
            "total_accounts": len(accounts),
            "connected": 0,
            "disconnected": 0,
            "deployed": 0,
            "undeployed": 0,
            "equity_zero": 0,
            "issues": []
        }
        
        for acc in accounts:
            if acc.connection_status == "CONNECTED":
                stats["connected"] += 1
            else:
                stats["disconnected"] += 1
                if acc.deployment_status == "DEPLOYED":
                    await self.log_event(acc.id, "WARNING", "ACCOUNT_DISCONNECTED", f"Account {acc.login} is DEPLOYED but DISCONNECTED", acc.user_id)
            
            if acc.deployment_status == "DEPLOYED":
                stats["deployed"] += 1
            else:
                stats["undeployed"] += 1
            
            if acc.last_equity == 0 and acc.connection_status == "CONNECTED":
                stats["equity_zero"] += 1
                await self.log_event(acc.id, "CRITICAL", "EQUITY_ZERO", f"Account {acc.login} has ZERO equity", acc.user_id)

        # Check CopyFactory Subscriptions
        stmt_sub = select(CopyFactorySubscription)
        res_sub = await self.db.execute(stmt_sub)
        subscriptions = res_sub.scalars().all()
        
        for sub in subscriptions:
            # Check if strategy exists and is active
            stmt_st = select(CopyFactoryStrategy).where(CopyFactoryStrategy.id == sub.strategy_id)
            strategy = (await self.db.execute(stmt_st)).scalars().first()
            
            if not strategy or not strategy.is_active:
                await self.log_event(sub.client_account_id, "CRITICAL", "MISSING_STRATEGY", f"Subscription for user {sub.user_id} has missing or inactive strategy", sub.user_id)
            
            # Here we could call CF API to verify status if needed, but it's expensive in a loop
            # We'll rely on the worker to do that periodically

        return {
            "status": "OK" if not stats["issues"] else "WARNING",
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def run_full_scan(self):
        """Run a full scan of all accounts and verify with MetaApi/CopyFactory directly."""
        logger.info("Starting full MetaApi V3 monitor scan...")
        
        # 1. Sync all accounts (uses MetaApiAccountSyncService)
        # 2. Verify subscribers in CopyFactory
        stmt_sub = select(CopyFactorySubscription).where(CopyFactorySubscription.status == "ACTIVE")
        res_sub = await self.db.execute(stmt_sub)
        subscriptions = res_sub.scalars().all()
        
        for sub in subscriptions:
            try:
                stmt_acc = select(MetaApiAccount).where(MetaApiAccount.id == sub.client_account_id)
                acc = (await self.db.execute(stmt_acc)).scalars().first()
                
                if not acc or not acc.metaapi_account_id:
                    continue
                
                # Check CF status
                try:
                    cf_sub = await self.cf.cf_api.configuration_api.get_subscriber(acc.metaapi_account_id)
                    
                    # If subscription is cancelled in CF but ACTIVE in DB
                    is_enabled_in_cf = cf_sub.get('enabled', False)
                    if not is_enabled_in_cf and sub.status == "ACTIVE":
                        sub.status = "PAUSED" # Or ERROR
                        await self.log_event(acc.id, "CRITICAL", "SUBSCRIPTION_MISMATCH", f"Subscription for {acc.login} is enabled in DB but DISABLED in CopyFactory", sub.user_id)
                except Exception as cf_e:
                    if "not found" in str(cf_e).lower():
                        await self.log_event(acc.id, "CRITICAL", "SUBSCRIBER_NOT_FOUND", f"Subscriber for {acc.login} not found in CopyFactory API", sub.user_id)
            except Exception as e:
                logger.error(f"Error scanning subscription {sub.id}: {e}")
        
        await self.db.commit()
        return await self.check_health()

