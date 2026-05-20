import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.config import get_settings
from app.models.metaapi import (
    MetaApiAccount, CopyFactoryStrategy, CopyFactorySubscription, 
    PositionReconciliationEvent, MetaApiReconciliationSettings
)
from app.services.metaapi.http_client import HttpMetaApiClient

settings = get_settings()
logger = logging.getLogger(__name__)

class PositionReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = HttpMetaApiClient()

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
        """[RECON] Compare positions between master and subscriber and detect orphans."""
        recon_settings = await self.get_settings()
        
        # 1. Fetch accounts
        master_acc = await self.db.get(MetaApiAccount, master_account_id)
        sub_acc = await self.db.get(MetaApiAccount, subscriber_account_id)
        
        if not master_acc or not sub_acc:
            logger.error(f"[RECON] Account not found: Master={master_account_id}, Sub={subscriber_account_id}")
            return
            
        if not master_acc.metaapi_account_id or not sub_acc.metaapi_account_id:
            logger.warning(f"[RECON] Accounts not ready: Master={master_acc.login}, Sub={sub_acc.login}")
            return

        try:
            # 2. Fetch positions from MetaApi Service (Isolated)
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
            if orphans:
                logger.info(f"[RECON DONE] Account: {sub_acc.login}. Orphans: {len(orphans)}")
        except Exception as e:
            logger.error(f"[RECON ERROR] Failed for sub {sub_acc.login}: {e}")
            await self.db.rollback()

    def _is_match(self, sub_pos: Dict, master_pos: Dict, recon_settings: MetaApiReconciliationSettings) -> bool:
        """Logic to match a subscriber position to a master position."""
        # Symbol match
        if recon_settings.strict_symbol_match:
            sub_symbol = sub_pos.get("symbol", "")
            master_symbol = master_pos.get("symbol", "")
            # Basic suffix/prefix handling if not identical
            if sub_symbol != master_symbol:
                return False
        
        # Side match
        if sub_pos.get("type") != master_pos.get("type"):
            return False
            
        return True

    async def _process_orphan(self, orphan: Dict, master_acc: MetaApiAccount, sub_acc: MetaApiAccount, 
                             recon_settings: MetaApiReconciliationSettings, 
                             master_snapshot: List, sub_snapshot: List):
        
        pos_id = orphan.get("id")
        profit = orphan.get("profit", 0.0)
        symbol = orphan.get("symbol", "UNKNOWN")
        
        # Age calculation
        pos_time_str = orphan.get("openTime") or orphan.get("time")
        age_minutes = 0
        if pos_time_str:
            try:
                pos_time = datetime.fromisoformat(pos_time_str.replace('Z', '+00:00'))
                age_delta = datetime.now(timezone.utc) - pos_time
                age_minutes = age_delta.total_seconds() / 60
            except Exception as e:
                logger.warning(f"[RECON] Error parsing position time {pos_time_str}: {e}")

        # Check existing events
        stmt = select(PositionReconciliationEvent).where(
            and_(PositionReconciliationEvent.position_id == pos_id, 
                 PositionReconciliationEvent.status.in_(["ORPHAN_POSITION_DETECTED", "WAITING_ADMIN_APPROVAL"]))
        )
        existing_res = await self.db.execute(stmt)
        existing = existing_res.scalars().first()
        
        if existing:
            existing.profit = profit
            existing.updated_at = datetime.now(timezone.utc)
            return

        logger.warning(f"[ORPHAN DETECTED] Acc: {sub_acc.login}, Sym: {symbol}, ID: {pos_id}, Profit: {profit}, Age: {age_minutes:.1f}m")

        # Create event
        event = PositionReconciliationEvent(
            account_id=sub_acc.id,
            user_id=sub_acc.user_id,
            master_account_id=master_acc.id,
            subscriber_account_id=sub_acc.id,
            symbol=symbol,
            position_id=pos_id,
            side=orphan.get("type", "BUY"),
            volume=orphan.get("volume", 0.0),
            open_price=orphan.get("openPrice", 0.0),
            current_price=orphan.get("currentPrice", 0.0),
            profit=profit,
            status="ORPHAN_POSITION_DETECTED",
            snapshot_master_positions=master_snapshot,
            snapshot_subscriber_positions=sub_snapshot
        )
        self.db.add(event)
        
        # Auto-close rules
        should_auto_close = False
        close_reason = ""
        
        if recon_settings.auto_close_orphan_positions:
            if age_minutes > recon_settings.max_minutes_orphan:
                should_auto_close = True
                close_reason = f"Age ({age_minutes:.1f}m) > Limit ({recon_settings.max_minutes_orphan}m)"
            elif profit >= 0 and recon_settings.orphan_auto_close_profit_enabled:
                should_auto_close = True
                close_reason = "Profit >= 0"
            elif profit < 0 and profit >= recon_settings.orphan_auto_close_loss_limit:
                should_auto_close = True
                close_reason = f"Loss ({profit}) within limit ({recon_settings.orphan_auto_close_loss_limit})"
        
        if should_auto_close:
            try:
                await self.client.close_position(sub_acc.metaapi_account_id, pos_id)
                event.status = "AUTO_CLOSED"
                event.action_taken = "CLOSED_BY_SYSTEM"
                event.reason = close_reason
                logger.info(f"[AUTO CLOSE SUCCESS] Position {pos_id} for {sub_acc.login}. Reason: {close_reason}")
            except Exception as e:
                logger.error(f"[AUTO CLOSE FAILED] Position {pos_id} for {sub_acc.login}: {e}")
                event.status = "FAILED"
                event.reason = f"Auto-close failed: {str(e)}"
        else:
            if profit < recon_settings.orphan_auto_close_loss_limit:
                event.status = "WAITING_ADMIN_APPROVAL"
                event.reason = f"High loss orphan: {profit} < {recon_settings.orphan_auto_close_loss_limit}"
            else:
                event.status = "ORPHAN_POSITION_DETECTED"
                event.reason = "Awaiting manual action or age limit"

    async def detect_all_orphans(self):
        """[RECON] Process all active subscriptions."""
        if not settings.V3_COPY_ENABLED:
            return

        stmt = select(CopyFactorySubscription).where(CopyFactorySubscription.status == "ACTIVE")
        result = await self.db.execute(stmt)
        subs = result.scalars().all()
        
        for sub in subs:
            stmt_strat = select(CopyFactoryStrategy).where(CopyFactoryStrategy.id == sub.strategy_id)
            res_strat = await self.db.execute(stmt_strat)
            strat = res_strat.scalars().first()
            
            if strat and strat.master_account_id:
                await self.sync_positions(strat.master_account_id, sub.client_account_id)

    async def detect_orphans_for_strategy(self, strategy_code: str):
        """[RECON] Process subscriptions for a specific strategy."""
        stmt = select(CopyFactoryStrategy).where(CopyFactoryStrategy.code == strategy_code)
        result = await self.db.execute(stmt)
        strat = result.scalars().first()
        
        if not strat or not strat.master_account_id:
            logger.warning(f"[RECON TRIGGER] Strategy {strategy_code} not found or no master")
            return await self.detect_all_orphans()

        stmt_subs = select(CopyFactorySubscription).where(
            and_(CopyFactorySubscription.strategy_id == strat.id, CopyFactorySubscription.status == "ACTIVE")
        )
        res_subs = await self.db.execute(stmt_subs)
        subs = res_subs.scalars().all()
        
        for sub in subs:
            await self.sync_positions(strat.master_account_id, sub.client_account_id)

    async def detect_orphans_for_master(self, master_account_id: UUID):
        """[RECON] Process subscriptions linked to a specific master account."""
        stmt_strats = select(CopyFactoryStrategy).where(CopyFactoryStrategy.master_account_id == master_account_id)
        res_strats = await self.db.execute(stmt_strats)
        strats = res_strats.scalars().all()
        
        if not strats:
            logger.warning(f"[RECON TRIGGER] Master account {master_account_id} not linked to any strategy")
            return await self.detect_all_orphans()

        for strat in strats:
            stmt_subs = select(CopyFactorySubscription).where(
                and_(CopyFactorySubscription.strategy_id == strat.id, CopyFactorySubscription.status == "ACTIVE")
            )
            res_subs = await self.db.execute(stmt_subs)
            subs = res_subs.scalars().all()
            
            for sub in subs:
                await self.sync_positions(strat.master_account_id, sub.client_account_id)

    async def approve_close_orphan(self, event_id: UUID, admin_id: UUID):
        event = await self.db.get(PositionReconciliationEvent, event_id)
        if not event or event.status not in ["WAITING_ADMIN_APPROVAL", "ORPHAN_POSITION_DETECTED"]:
            raise Exception("Invalid event or status")
            
        sub_acc = await self.db.get(MetaApiAccount, event.subscriber_account_id)
        if not sub_acc or not sub_acc.metaapi_account_id:
            raise Exception("Subscriber account not found")

        try:
            await self.client.close_position(sub_acc.metaapi_account_id, event.position_id)
            event.status = "ADMIN_CLOSED"
            event.action_taken = "CLOSED_BY_ADMIN"
            event.approved_by = admin_id
            event.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.info(f"[ADMIN CLOSE SUCCESS] Position {event.position_id} for {sub_acc.login}")
            return event
        except Exception as e:
            event.status = "FAILED"
            event.reason = str(e)
            await self.db.commit()
            logger.error(f"[ADMIN CLOSE FAILED] {event.position_id} on {sub_acc.login}: {e}")
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
