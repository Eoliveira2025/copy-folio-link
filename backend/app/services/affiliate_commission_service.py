import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.affiliate import Affiliate, AffiliateReferral, AffiliateCommission, CommissionBase, CommissionStatus
from app.models.performance_billing import PerformanceBillingCycle, CycleStatus
from app.models.user import User

logger = logging.getLogger("app.affiliate_commission")

class AffiliateCommissionService:
    @staticmethod
    async def create_from_performance_cycle(db: AsyncSession, cycle_id: uuid.UUID):
        """Calculate and create affiliate commission from a performance billing cycle."""
        # 1. Fetch cycle
        stmt_cycle = select(PerformanceBillingCycle).where(PerformanceBillingCycle.id == cycle_id)
        result_cycle = await db.execute(stmt_cycle)
        cycle = result_cycle.scalar_one_or_none()
        
        if not cycle:
            logger.error(f"[AFFILIATE COMMISSION SKIPPED] Cycle {cycle_id} not found")
            return None
            
        if cycle.status not in [CycleStatus.CLOSED, CycleStatus.INVOICED] or (cycle.gross_profit or 0) <= 0:
            logger.info(f"[AFFILIATE COMMISSION SKIPPED] Cycle {cycle_id} not eligible (status: {cycle.status}, profit: {cycle.gross_profit})")
            return None
            
        # 2. Check for existing commission
        stmt_exists = select(AffiliateCommission).where(AffiliateCommission.performance_cycle_id == cycle_id)
        if (await db.execute(stmt_exists)).scalar_one_or_none():
            logger.warning(f"[AFFILIATE COMMISSION SKIPPED] Commission already exists for cycle {cycle_id}")
            return None
            
        # 3. Check for active referral
        stmt_ref = select(AffiliateReferral).where(
            AffiliateReferral.referred_user_id == cycle.user_id,
            AffiliateReferral.active == True
        )
        referral = (await db.execute(stmt_ref)).scalar_one_or_none()
        if not referral:
            logger.info(f"[AFFILIATE COMMISSION SKIPPED] No active affiliate referral for user {cycle.user_id}")
            return None
            
        # 4. Fetch affiliate settings
        stmt_aff = select(Affiliate).where(Affiliate.id == referral.affiliate_id, Affiliate.active == True)
        affiliate = (await db.execute(stmt_aff)).scalar_one_or_none()
        if not affiliate:
            logger.info(f"[AFFILIATE COMMISSION SKIPPED] Affiliate {referral.affiliate_id} is inactive or not found")
            return None
            
        # 5. Calculate amount
        aff_commission_amount = 0.0
        if affiliate.commission_base == CommissionBase.COMPANY_COMMISSION:
            aff_commission_amount = float(cycle.commission_amount or 0) * (float(affiliate.commission_percentage) / 100.0)
        elif affiliate.commission_base == CommissionBase.GROSS_PROFIT:
            aff_commission_amount = float(cycle.gross_profit or 0) * (float(affiliate.commission_percentage) / 100.0)
            
        if aff_commission_amount <= 0:
            logger.info(f"[AFFILIATE COMMISSION SKIPPED] Calculated amount is zero for cycle {cycle_id}")
            return None
            
        # 6. Create commission record
        commission = AffiliateCommission(
            affiliate_id=affiliate.id,
            referred_user_id=cycle.user_id,
            performance_cycle_id=cycle.id,
            gross_profit=cycle.gross_profit,
            company_commission_amount=cycle.commission_amount,
            affiliate_percentage=affiliate.commission_percentage,
            commission_base=affiliate.commission_base,
            affiliate_commission_amount=aff_commission_amount,
            status=CommissionStatus.PENDING,
            notes=f"Commission from performance cycle {cycle.cycle_start.strftime('%Y-%m-%d')}"
        )
        
        db.add(commission)
        await db.commit()
        logger.info(f"[AFFILIATE COMMISSION CREATED] ID: {commission.id}, Affiliate: {affiliate.id}, Amount: {aff_commission_amount}")
        return commission

    @staticmethod
    async def list_commissions_admin(
        db: AsyncSession, 
        affiliate_id: Optional[uuid.UUID] = None, 
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ):
        stmt = select(AffiliateCommission, Affiliate.name.label("affiliate_name"), User.email.label("referred_user_email")).join(
            Affiliate, AffiliateCommission.affiliate_id == Affiliate.id
        ).join(
            User, AffiliateCommission.referred_user_id == User.id
        ).order_by(AffiliateCommission.created_at.desc())
        
        if affiliate_id:
            stmt = stmt.where(AffiliateCommission.affiliate_id == affiliate_id)
        if status:
            stmt = stmt.where(AffiliateCommission.status == status)
        if date_from:
            stmt = stmt.where(AffiliateCommission.created_at >= date_from)
        if date_to:
            stmt = stmt.where(AffiliateCommission.created_at <= date_to)
            
        result = await db.execute(stmt)
        commissions = []
        for row, aff_name, user_email in result.all():
            row.affiliate_name = aff_name
            row.referred_user_email = user_email
            commissions.append(row)
        return commissions

    @staticmethod
    async def update_status(db: AsyncSession, commission_id: uuid.UUID, new_status: CommissionStatus):
        stmt = select(AffiliateCommission).where(AffiliateCommission.id == commission_id)
        commission = (await db.execute(stmt)).scalar_one_or_none()
        
        if not commission:
            return None
            
        commission.status = new_status
        if new_status == CommissionStatus.PAID:
            commission.paid_at = datetime.now(timezone.utc)
            
        await db.commit()
        logger.info(f"[AFFILIATE COMMISSION {new_status.value}] ID: {commission_id}")
        return commission
