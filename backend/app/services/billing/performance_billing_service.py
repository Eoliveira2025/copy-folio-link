import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from zoneinfo import ZoneInfo

from app.models.user import User
from app.models.performance_billing import BillingMethod, BillingMethodType, PerformanceBillingCycle, CycleStatus
from app.models.metaapi import MetaApiAccount, CopyFactorySubscription, CopyFactoryStrategy
from app.models.mt5_account import MT5Account
from app.models.invoice import Invoice, InvoiceStatus
from app.models.subscription import Subscription

logger = logging.getLogger("app.performance_billing")

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")

class PerformanceBillingService:
    @staticmethod
    async def get_performance_users(db: AsyncSession):
        """List users for admin performance billing dashboard."""
        stmt = (
            select(
                User.id,
                User.full_name,
                User.email,
                BillingMethod.method,
                BillingMethod.performance_percentage,
                MetaApiAccount.login.label("metaapi_login"),
                MetaApiAccount.last_balance.label("metaapi_balance"),
                MT5Account.login.label("mt5_login"),
                MT5Account.balance.label("mt5_balance"),
                CopyFactoryStrategy.strategy_code
            )
            .outerjoin(BillingMethod, User.id == BillingMethod.user_id)
            .outerjoin(MetaApiAccount, and_(User.id == MetaApiAccount.user_id, MetaApiAccount.account_type == "CLIENT"))
            .outerjoin(CopyFactorySubscription, MetaApiAccount.id == CopyFactorySubscription.client_account_id)
            .outerjoin(CopyFactoryStrategy, CopyFactorySubscription.strategy_id == CopyFactoryStrategy.id)
            .outerjoin(MT5Account, User.id == MT5Account.user_id)
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        users_dict = {}
        for row in rows:
            user_id = row.id
            if user_id not in users_dict:
                users_dict[user_id] = {
                    "user_id": user_id,
                    "full_name": row.full_name,
                    "email": row.email,
                    "method": row.method,
                    "performance_percentage": float(row.performance_percentage) if row.performance_percentage is not None else None,
                    "strategy_code": row.strategy_code,
                    "account_login": str(row.metaapi_login) if row.metaapi_login else (str(row.mt5_login) if row.mt5_login else None),
                    "current_balance": float(row.metaapi_balance) if row.metaapi_login else (float(row.mt5_balance) if row.mt5_balance is not None else 0.0)
                }
            else:
                if row.metaapi_login and not users_dict[user_id].get("metaapi_login"):
                     users_dict[user_id]["account_login"] = str(row.metaapi_login)
                     users_dict[user_id]["current_balance"] = float(row.metaapi_balance)
                     users_dict[user_id]["strategy_code"] = row.strategy_code
                     
        return list(users_dict.values())

    @staticmethod
    async def set_billing_method(db: AsyncSession, user_id: uuid.UUID, method: str, percentage: float, created_by: str = "admin"):
        """Create or update billing method for a user."""
        stmt = select(BillingMethod).where(BillingMethod.user_id == user_id)
        result = await db.execute(stmt)
        billing_method = result.scalar_one_or_none()
        
        if billing_method:
            billing_method.method = method
            billing_method.performance_percentage = percentage
            billing_method.updated_at = datetime.now(timezone.utc)
            billing_method.created_by = created_by
        else:
            billing_method = BillingMethod(
                user_id=user_id,
                method=method,
                performance_percentage=percentage,
                created_by=created_by
            )
            db.add(billing_method)
            
        await db.commit()
        return billing_method

    @staticmethod
    async def get_cycles(db: AsyncSession, user_id: Optional[uuid.UUID] = None, status: Optional[str] = None):
        """List performance billing cycles with filters."""
        stmt = select(PerformanceBillingCycle).order_by(PerformanceBillingCycle.cycle_start.desc())
        if user_id:
            stmt = stmt.where(PerformanceBillingCycle.user_id == user_id)
        if status:
            stmt = stmt.where(PerformanceBillingCycle.status == status)
            
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def start_cycle(db: AsyncSession, user_id: uuid.UUID, force: bool = False):
        """Start a new cycle for a user."""
        stmt = select(BillingMethod).where(BillingMethod.user_id == user_id, BillingMethod.active == True)
        result = await db.execute(stmt)
        method = result.scalar_one_or_none()
        
        if not method or method.method != BillingMethodType.PERFORMANCE_WEEKLY:
            logger.warning(f"[PERF BILLING START] User {user_id} not configured for performance weekly billing")
            return None
            
        stmt_open = select(PerformanceBillingCycle).where(
            PerformanceBillingCycle.user_id == user_id,
            PerformanceBillingCycle.status == CycleStatus.OPEN
        )
        result_open = await db.execute(stmt_open)
        if result_open.scalar_one_or_none() and not force:
            logger.warning(f"[PERF BILLING START] User {user_id} already has an OPEN cycle")
            return None
            
        stmt_meta = select(MetaApiAccount, CopyFactoryStrategy.strategy_code).outerjoin(
            CopyFactorySubscription, MetaApiAccount.id == CopyFactorySubscription.client_account_id
        ).outerjoin(
            CopyFactoryStrategy, CopyFactorySubscription.strategy_id == CopyFactoryStrategy.id
        ).where(
            MetaApiAccount.user_id == user_id,
            MetaApiAccount.account_type == "CLIENT"
        ).order_by(MetaApiAccount.created_at.desc())
        
        result_meta = await db.execute(stmt_meta)
        meta_row = result_meta.first()
        
        source = None
        login = None
        balance = 0.0
        strategy_code = None
        
        if meta_row:
            account, strat_code = meta_row
            source = "metaapi"
            login = str(account.login)
            balance = account.last_balance
            strategy_code = strat_code
        else:
            stmt_mt5 = select(MT5Account).where(MT5Account.user_id == user_id).order_by(MT5Account.created_at.desc())
            result_mt5 = await db.execute(stmt_mt5)
            account_mt5 = result_mt5.scalar_one_or_none()
            if account_mt5:
                source = "mt5"
                login = str(account_mt5.login)
                balance = account_mt5.balance if account_mt5.balance else 0.0
            else:
                logger.error(f"[PERF BILLING START] No account found for user {user_id}")
                return None
                
        now_sp = datetime.now(SAO_PAULO_TZ)
        cycle = PerformanceBillingCycle(
            user_id=user_id,
            account_source=source,
            account_login=login,
            strategy_code=strategy_code,
            cycle_start=now_sp,
            start_balance=balance,
            commission_percentage=method.performance_percentage,
            status=CycleStatus.OPEN
        )
        db.add(cycle)
        await db.commit()
        logger.info(f"[PERF BILLING START] Cycle started for user {user_id} with balance {balance}")
        return cycle

    @staticmethod
    async def close_cycle(db: AsyncSession, cycle_id: uuid.UUID):
        """Close an open cycle and calculate profit/commission."""
        stmt = select(PerformanceBillingCycle).where(PerformanceBillingCycle.id == cycle_id)
        result = await db.execute(stmt)
        cycle = result.scalar_one_or_none()
        
        if not cycle or cycle.status != CycleStatus.OPEN:
            logger.warning(f"[PERF BILLING CLOSE] Cycle {cycle_id} not found or not in OPEN status")
            return None
            
        end_balance = 0.0
        if cycle.account_source == "metaapi":
            stmt_meta = select(MetaApiAccount).where(MetaApiAccount.login == cycle.account_login)
            res = await db.execute(stmt_meta)
            acc = res.scalar_one_or_none()
            if acc:
                end_balance = acc.last_balance
            else:
                cycle.status = CycleStatus.ERROR
                cycle.notes = "Account not found at closure"
                await db.commit()
                return cycle
        else:
            stmt_mt5 = select(MT5Account).where(MT5Account.login == int(cycle.account_login))
            res = await db.execute(stmt_mt5)
            acc = res.scalar_one_or_none()
            if acc:
                end_balance = acc.balance if acc.balance else 0.0
            else:
                cycle.status = CycleStatus.ERROR
                cycle.notes = "Account not found at closure"
                await db.commit()
                return cycle
                
        profit = end_balance - float(cycle.start_balance)
        commission = 0.0
        status = CycleStatus.CLOSED
        
        if profit <= 0:
            status = CycleStatus.NO_PROFIT
            commission = 0.0
        else:
            commission = profit * (float(cycle.commission_percentage) / 100.0)
            
        cycle.end_balance = end_balance
        cycle.gross_profit = profit
        cycle.commission_amount = commission
        cycle.status = status
        cycle.cycle_end = datetime.now(SAO_PAULO_TZ)
        
        await db.commit()
        logger.info(f"[PERF BILLING CLOSE] Cycle {cycle_id} closed. Profit: {profit}, Commission: {commission}")
        
        if profit > 0:
            await PerformanceBillingService.generate_invoice(db, cycle.id)
            
        return cycle

    @staticmethod
    async def generate_invoice(db: AsyncSession, cycle_id: uuid.UUID):
        """Generate a pending invoice for a closed profitable cycle."""
        stmt = select(PerformanceBillingCycle).where(PerformanceBillingCycle.id == cycle_id)
        result = await db.execute(stmt)
        cycle = result.scalar_one_or_none()
        
        if not cycle or cycle.status != CycleStatus.CLOSED or not cycle.commission_amount or cycle.commission_amount <= 0:
            return None
            
        if cycle.invoice_id:
            logger.warning(f"[PERF BILLING INVOICE] Cycle {cycle_id} already has an invoice")
            return None
            
        stmt_sub = select(Subscription).where(Subscription.user_id == cycle.user_id).order_by(Subscription.created_at.desc())
        result_sub = await db.execute(stmt_sub)
        sub = result_sub.scalar_one_or_none()
        
        if not sub:
            logger.error(f"[PERF BILLING INVOICE] No subscription found for user {cycle.user_id}")
            cycle.status = CycleStatus.ERROR
            cycle.notes = "Cannot generate invoice: No subscription found"
            await db.commit()
            return None
            
        due_date = datetime.now(timezone.utc) + timedelta(days=3)
        
        start_str = cycle.cycle_start.astimezone(SAO_PAULO_TZ).strftime("%d/%m/%Y")
        end_str = cycle.cycle_end.astimezone(SAO_PAULO_TZ).strftime("%d/%m/%Y") if cycle.cycle_end else datetime.now().strftime("%d/%m/%Y")
        
        invoice = Invoice(
            subscription_id=sub.id,
            amount=float(cycle.commission_amount),
            currency="USD",
            status=InvoiceStatus.PENDING,
            issue_date=datetime.now(timezone.utc),
            due_date=due_date,
            admin_notes=f"Performance billing semanal de {start_str} a {end_str}",
            manual_payment=False
        )
        db.add(invoice)
        await db.flush()
        
        cycle.invoice_id = invoice.id
        cycle.status = CycleStatus.INVOICED
        
        await db.commit()
        logger.info(f"[PERF BILLING INVOICE] Invoice {invoice.id} generated for cycle {cycle_id}")
        return invoice

    @staticmethod
    async def get_dashboard_summary(db: AsyncSession):
        """Get summary stats for performance billing."""
        stmt_open = select(func.sum(PerformanceBillingCycle.commission_amount)).where(
            PerformanceBillingCycle.status == CycleStatus.INVOICED
        ).join(Invoice, PerformanceBillingCycle.invoice_id == Invoice.id).where(
            Invoice.status == InvoiceStatus.PENDING
        )
        
        stmt_paid = select(func.sum(PerformanceBillingCycle.commission_amount)).where(
            PerformanceBillingCycle.status == CycleStatus.INVOICED
        ).join(Invoice, PerformanceBillingCycle.invoice_id == Invoice.id).where(
            Invoice.status == InvoiceStatus.PAID
        )
        
        stmt_profitable = select(func.count(PerformanceBillingCycle.id)).where(
            PerformanceBillingCycle.status.in_([CycleStatus.CLOSED, CycleStatus.INVOICED]),
            PerformanceBillingCycle.gross_profit > 0
        )
        
        stmt_negative = select(func.count(PerformanceBillingCycle.id)).where(
            PerformanceBillingCycle.status == CycleStatus.NO_PROFIT
        )
        
        open_val = (await db.execute(stmt_open)).scalar() or 0.0
        paid_val = (await db.execute(stmt_paid)).scalar() or 0.0
        profitable_count = (await db.execute(stmt_profitable)).scalar() or 0
        negative_count = (await db.execute(stmt_negative)).scalar() or 0
        
        return {
            "open_commissions": float(open_val),
            "total_invoiced": float(paid_val),
            "profitable_cycles": profitable_count,
            "negative_cycles": negative_count
        }

    @staticmethod
    async def run_automation(db: AsyncSession):
        """Run weekly automation checks."""
        now_sp = datetime.now(SAO_PAULO_TZ)
        weekday = now_sp.weekday()
        hour = now_sp.hour
        
        if weekday == 6 and hour >= 18:
            stmt = select(BillingMethod).where(BillingMethod.method == BillingMethodType.PERFORMANCE_WEEKLY, BillingMethod.active == True)
            res = await db.execute(stmt)
            methods = res.scalars().all()
            for m in methods:
                try:
                    today_start = now_sp.replace(hour=0, minute=0, second=0, microsecond=0)
                    stmt_check = select(PerformanceBillingCycle).where(
                        PerformanceBillingCycle.user_id == m.user_id,
                        PerformanceBillingCycle.cycle_start >= today_start
                    )
                    exists = (await db.execute(stmt_check)).scalar().first() is not None
                    if not exists:
                        await PerformanceBillingService.start_cycle(db, m.user_id)
                except Exception as e:
                    logger.error(f"[PERF BILLING ERROR] Failed to start cycle for user {m.user_id}: {e}")
                    
        if weekday == 4 and hour >= 18:
            stmt = select(PerformanceBillingCycle).where(PerformanceBillingCycle.status == CycleStatus.OPEN)
            res = await db.execute(stmt)
            open_cycles = res.scalars().all()
            for cycle in open_cycles:
                try:
                    await PerformanceBillingService.close_cycle(db, cycle.id)
                except Exception as e:
                    logger.error(f"[PERF BILLING ERROR] Failed to close cycle {cycle.id}: {e}")
