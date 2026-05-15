import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.config import get_settings
from app.models.metaapi import (
    MetaApiAccount, CopyFactoryStrategy, CopyFactorySubscription, 
    PositionReconciliationEvent, MetaApiReconciliationSettings
)
from app.services.metaapi.client import MetaApiClient

settings = get_settings()
logger = logging.getLogger(__name__)

class PositionReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = MetaApiClient()

    async def get_settings(self) -> MetaApiReconciliationSettings:
        stmt = select(MetaApiReconciliationSettings)
        result = await self.db.execute(stmt)
        recon_settings = result.scalars().first()
        if not recon_settings:
            recon_settings = MetaApiReconciliationSettings()
            self.db.add(recon_settings)
            await self.db.commit()
            await self.db.refresh(recon_settings)
        return recon_settings

    async def update_settings(self, data: Dict[str, Any]) -> MetaApiReconciliationSettings:
        recon_settings = await self.get_settings()
        for key, value in data.items():
            if hasattr(recon_settings, key):
                setattr(recon_settings, key, value)
        recon_settings.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(recon_settings)
        return recon_settings

    async def sync_positions(self, master_account_id: UUID, subscriber_account_id: UUID):
        """Compare positions between master and subscriber and detect orphans."""
        recon_settings = await self.get_settings()
        
        # 1. Fetch accounts
        master_acc = await self.db.get(MetaApiAccount, master_account_id)
        sub_acc = await self.db.get(MetaApiAccount, subscriber_account_id)
        
        if not master_acc or not sub_acc:
            logger.error(f"Account not found for reconciliation: Master={master_account_id}, Sub={subscriber_account_id}")
            return
            
        if not master_acc.metaapi_account_id or not sub_acc.metaapi_account_id:
            logger.warning(f"Accounts not ready for reconciliation: Master={master_acc.login}, Sub={sub_acc.login}")
            return

        try:
            # 2. Fetch positions from MetaApi
            master_positions = await self.client.get_positions(master_acc.metaapi_account_id)
            sub_positions = await self.client.get_positions(sub_acc.metaapi_account_id)
            
            # 3. Detect orphans
            orphans = []
            for sp in sub_positions:
                found = False
                for mp in master_positions:
                    if self._is_match(sp, mp, recon_settings):
                        found = True
                        break
                
                if not found:
                    orphans.append(sp)
            
            # 4. Handle orphans
            for orphan in orphans:
                await self._process_orphan(orphan, master_acc, sub_acc, recon_settings, master_positions, sub_positions)
                
            await self.db.commit()
            logger.info(f"Reconciliation completed for {sub_acc.login}. Orphans detected: {len(orphans)}")
        except Exception as e:
            logger.error(f"Error in sync_positions for sub {sub_acc.login}: {e}")
            await self.db.rollback()

    def _is_match(self, sub_pos: Dict, master_pos: Dict, recon_settings: MetaApiReconciliationSettings) -> bool:
        """Logic to match a subscriber position to a master position."""
        # Symbol match
        if recon_settings.strict_symbol_match:
            if sub_pos.get("symbol") != master_pos.get("symbol"):
                return False
        
        # Side match
        if sub_pos.get("type") != master_pos.get("type"):
            return False
            
        # Optional: volume match with tolerance
        # volume_diff = abs(sub_pos.get("volume", 0) - master_pos.get("volume", 0))
        # if volume_diff > recon_settings.lot_tolerance:
        #     return False

        return True

    async def _process_orphan(self, orphan: Dict, master_acc: MetaApiAccount, sub_acc: MetaApiAccount, 
                             recon_settings: MetaApiReconciliationSettings, 
                             master_snapshot: List, sub_snapshot: List):
        
        pos_id = orphan.get("id")
        profit = orphan.get("profit", 0.0)
        
        # Check if already exists in events to avoid duplicates
        stmt = select(PositionReconciliationEvent).where(
            and_(PositionReconciliationEvent.position_id == pos_id, 
                 PositionReconciliationEvent.status.in_(["ORPHAN_POSITION_DETECTED", "WAITING_ADMIN_APPROVAL"]))
        )
        existing_res = await self.db.execute(stmt)
        existing = existing_res.scalars().first()
        
        if existing:
            # Update current state if still orphan
            existing.current_price = orphan.get("currentPrice", 0.0)
            existing.profit = profit
            existing.updated_at = datetime.now(timezone.utc)
            return

        # Create new event
        event = PositionReconciliationEvent(
            account_id=sub_acc.id,
            user_id=sub_acc.user_id,
            master_account_id=master_acc.id,
            subscriber_account_id=sub_acc.id,
            symbol=orphan.get("symbol", "UNKNOWN"),
            position_id=pos_id,
            side=orphan.get("type", "BUY"),
            volume=orphan.get("volume", 0.0),
            open_price=orphan.get("openPrice", 0.0),
            current_price=orphan.get("currentPrice", 0.0),
            profit=profit,
            status="ORPHAN_DETECTED",
            snapshot_master_positions=master_snapshot,
            snapshot_subscriber_positions=sub_snapshot
        )
        self.db.add(event)
        
        # Apply Auto-close rules
        should_auto_close = False
        if recon_settings.auto_close_orphan_positions:
            if profit >= 0 and recon_settings.orphan_auto_close_profit_enabled:
                should_auto_close = True
                event.reason = "Auto-close: Profit >= 0"
            elif profit < 0 and profit >= recon_settings.orphan_auto_close_loss_limit:
                should_auto_close = True
                event.reason = f"Auto-close: Loss ({profit}) within limit ({recon_settings.orphan_auto_close_loss_limit})"
        
        if should_auto_close:
            try:
                await self.client.close_position(sub_acc.metaapi_account_id, pos_id)
                event.status = "AUTO_CLOSED"
                event.action_taken = "CLOSED_BY_SYSTEM"
                logger.info(f"Orphan position {pos_id} auto-closed for {sub_acc.login} (Profit: {profit})")
            except Exception as e:
                logger.error(f"Failed to auto-close orphan position {pos_id} for {sub_acc.login}: {e}")
                event.status = "FAILED"
                event.reason = f"Auto-close failed: {str(e)}"
        else:
            if profit < recon_settings.orphan_auto_close_loss_limit:
                event.status = "WAITING_ADMIN_APPROVAL"
                event.reason = f"High loss orphan detected: {profit} < {recon_settings.orphan_auto_close_loss_limit}"
                logger.warning(f"High loss orphan {pos_id} on {sub_acc.login} needs admin approval (Profit: {profit})")
            else:
                # If auto-close disabled but profit/loss within range
                event.status = "ORPHAN_DETECTED"
                event.reason = "Orphan detected, awaiting manual action (auto-close disabled)"

    async def detect_all_orphans(self):
        """Worker task to run reconciliation for all active subscriptions."""
        if not settings.V3_COPY_ENABLED:
            return

        stmt = select(CopyFactorySubscription).where(CopyFactorySubscription.status == "ACTIVE")
        result = await self.db.execute(stmt)
        subs = result.scalars().all()
        
        for sub in subs:
            # Find strategy to get master
            stmt_strat = select(CopyFactoryStrategy).where(CopyFactoryStrategy.id == sub.strategy_id)
            res_strat = await self.db.execute(stmt_strat)
            strat = res_strat.scalars().first()
            
            if strat and strat.master_account_id:
                await self.sync_positions(strat.master_account_id, sub.client_account_id)

    async def approve_close_orphan(self, event_id: UUID, admin_id: UUID):
        event = await self.db.get(PositionReconciliationEvent, event_id)
        if not event or event.status not in ["WAITING_ADMIN_APPROVAL", "ORPHAN_DETECTED"]:
            raise Exception("Invalid event or status")
            
        sub_acc = await self.db.get(MetaApiAccount, event.subscriber_account_id)
        if not sub_acc or not sub_acc.metaapi_account_id:
            raise Exception("Subscriber account not found or not connected")

        try:
            await self.client.close_position(sub_acc.metaapi_account_id, event.position_id)
            event.status = "ADMIN_CLOSED"
            event.action_taken = "CLOSED_BY_ADMIN"
            event.approved_by = admin_id
            event.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            return event
        except Exception as e:
            event.status = "FAILED"
            event.reason = str(e)
            await self.db.commit()
            raise e

    async def ignore_orphan(self, event_id: UUID, admin_id: UUID):
        event = await self.db.get(PositionReconciliationEvent, event_id)
        if not event:
            raise Exception("Event not found")
            
        event.status = "IGNORED"
        event.action_taken = "IGNORED_BY_ADMIN"
        event.approved_by = admin_id
        event.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return event

    async def get_events(self, status: Optional[str] = None) -> List[PositionReconciliationEvent]:
        stmt = select(PositionReconciliationEvent)
        if status:
            stmt = stmt.where(PositionReconciliationEvent.status == status)
        stmt = stmt.order_by(PositionReconciliationEvent.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()
