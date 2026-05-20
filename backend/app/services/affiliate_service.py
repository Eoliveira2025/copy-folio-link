import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.user import User, UserRole, UserRoleMapping
from app.models.affiliate import Affiliate, AffiliateReferral, AffiliateCommission, CommissionBase, CommissionStatus
from app.models.performance_billing import PerformanceBillingCycle
from app.models.mt5_account import MT5Account
from app.models.strategy import UserStrategy, Strategy
from app.core.security import hash_password

logger = logging.getLogger("app.affiliate")

class AffiliateService:
    @staticmethod
    async def create_affiliate(db: AsyncSession, data: dict, created_by_id: uuid.UUID):
        # 1. Create User
        user = User(
            email=data["email"],
            hashed_password=hash_password("copy123"),
            full_name=data["name"]
        )
        db.add(user)
        await db.flush()

        # 2. Add Affiliate Role
        db.add(UserRoleMapping(user_id=user.id, role=UserRole.AFFILIATE))

        # 3. Create Affiliate Profile
        affiliate = Affiliate(
            user_id=user.id,
            name=data["name"],
            email=data["email"],
            commission_percentage=data["commission_percentage"],
            commission_base=data["commission_base"],
            created_by=created_by_id,
            must_change_password=True
        )
        db.add(affiliate)
        await db.commit()
        await db.refresh(affiliate)
        
        logger.info(f"[AFFILIATE CREATE] ID: {affiliate.id}, Email: {affiliate.email}")
        return affiliate

    @staticmethod
    async def list_affiliates(db: AsyncSession):
        query = select(Affiliate)
        result = await db.execute(query)
        affiliates = result.scalars().all()
        
        response = []
        for aff in affiliates:
            # Stats
            ref_count = await db.execute(select(func.count(AffiliateReferral.id)).where(AffiliateReferral.affiliate_id == aff.id, AffiliateReferral.active == True))
            pending_comm = await db.execute(select(func.coalesce(func.sum(AffiliateCommission.affiliate_commission_amount), 0.0)).where(AffiliateCommission.affiliate_id == aff.id, AffiliateCommission.status == CommissionStatus.PENDING))
            paid_comm = await db.execute(select(func.coalesce(func.sum(AffiliateCommission.affiliate_commission_amount), 0.0)).where(AffiliateCommission.affiliate_id == aff.id, AffiliateCommission.status == CommissionStatus.PAID))
            
            aff_data = {
                "id": aff.id,
                "user_id": aff.user_id,
                "name": aff.name,
                "email": aff.email,
                "commission_percentage": float(aff.commission_percentage),
                "commission_base": aff.commission_base,
                "active": aff.active,
                "must_change_password": aff.must_change_password,
                "created_at": aff.created_at,
                "total_referrals": ref_count.scalar() or 0,
                "pending_commission": float(pending_comm.scalar() or 0),
                "paid_commission": float(paid_comm.scalar() or 0)
            }
            response.append(aff_data)
            
        return response

    @staticmethod
    async def reset_password(db: AsyncSession, affiliate_id: uuid.UUID):
        result = await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))
        affiliate = result.scalar_one_or_none()
        if not affiliate:
            raise HTTPException(status_code=404, detail="Affiliate not found")
        
        if affiliate.user_id:
            await db.execute(
                update(User)
                .where(User.id == affiliate.user_id)
                .values(hashed_password=hash_password("copy123"))
            )
            affiliate.must_change_password = True
            await db.commit()
            logger.info(f"[AFFILIATE PASSWORD RESET] ID: {affiliate_id}")
            return True
        return False

    @staticmethod
    async def assign_referral(db: AsyncSession, affiliate_id: uuid.UUID, user_id: uuid.UUID, created_by_id: uuid.UUID):
        # Deactivate previous active referral for this user
        await db.execute(
            update(AffiliateReferral)
            .where(AffiliateReferral.referred_user_id == user_id, AffiliateReferral.active == True)
            .values(active=False)
        )
        
        # Create new referral
        referral = AffiliateReferral(
            affiliate_id=affiliate_id,
            referred_user_id=user_id,
            active=True,
            created_by=created_by_id
        )
        db.add(referral)
        await db.commit()
        logger.info(f"[AFFILIATE REFERRAL] User {user_id} assigned to affiliate {affiliate_id}")
        return referral

    @staticmethod
    async def get_affiliate_dashboard(db: AsyncSession, affiliate_user_id: uuid.UUID):
        result = await db.execute(select(Affiliate).where(Affiliate.user_id == affiliate_user_id))
        affiliate = result.scalar_one_or_none()
        if not affiliate:
            raise HTTPException(status_code=404, detail="Affiliate profile not found")

        # Stats
        pending_comm = await db.execute(select(func.coalesce(func.sum(AffiliateCommission.affiliate_commission_amount), 0.0)).where(AffiliateCommission.affiliate_id == affiliate.id, AffiliateCommission.status == CommissionStatus.PENDING))
        paid_comm = await db.execute(select(func.coalesce(func.sum(AffiliateCommission.affiliate_commission_amount), 0.0)).where(AffiliateCommission.affiliate_id == affiliate.id, AffiliateCommission.status == CommissionStatus.PAID))
        
        # Referrals
        ref_query = (
            select(AffiliateReferral, User)
            .join(User, AffiliateReferral.referred_user_id == User.id)
            .where(AffiliateReferral.affiliate_id == affiliate.id, AffiliateReferral.active == True)
        )
        refs_result = await db.execute(ref_query)
        referrals = []
        
        for ref, user in refs_result:
            # Get MT5 Account info
            mt5_res = await db.execute(select(MT5Account).where(MT5Account.user_id == user.id).limit(1))
            mt5 = mt5_res.scalar_one_or_none()
            
            # Get latest performance cycle
            cycle_res = await db.execute(
                select(PerformanceBillingCycle)
                .where(PerformanceBillingCycle.user_id == user.id)
                .order_by(PerformanceBillingCycle.created_at.desc())
                .limit(1)
            )
            cycle = cycle_res.scalar_one_or_none()
            
            # Get latest commission status
            comm_res = await db.execute(
                select(AffiliateCommission)
                .where(AffiliateCommission.affiliate_id == affiliate.id, AffiliateCommission.referred_user_id == user.id)
                .order_by(AffiliateCommission.created_at.desc())
                .limit(1)
            )
            comm = comm_res.scalar_one_or_none()
            
            referrals.append({
                "user_id": user.id,
                "email": user.email,
                "mt5_login": mt5.login if mt5 else None,
                "strategy_name": cycle.strategy_code if cycle else "N/A",
                "balance": float(mt5.balance) if mt5 and hasattr(mt5, 'balance') else 0.0,
                "weekly_profit": float(cycle.gross_profit) if cycle and cycle.gross_profit else 0.0,
                "affiliate_commission": float(comm.affiliate_commission_amount) if comm else 0.0,
                "commission_status": comm.status.value if comm else "N/A"
            })

        # Recent commissions
        recent_comm_query = (
            select(AffiliateCommission)
            .where(AffiliateCommission.affiliate_id == affiliate.id)
            .order_by(AffiliateCommission.created_at.desc())
            .limit(10)
        )
        recent_comm_res = await db.execute(recent_comm_query)
        recent_commissions = []
        for c in recent_comm_res.scalars().all():
            recent_commissions.append({
                "id": str(c.id),
                "amount": float(c.affiliate_commission_amount),
                "status": c.status.value,
                "created_at": c.created_at.isoformat()
            })

        return {
            "total_pending": float(pending_comm.scalar() or 0),
            "total_paid": float(paid_comm.scalar() or 0),
            "active_referrals_count": len(referrals),
            "referrals": referrals,
            "recent_commissions": recent_commissions
        }
