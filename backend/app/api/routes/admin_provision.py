"""Admin provisioning endpoints — manual MT5 account first-login flow."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decrypt_mt5_password
from app.api.deps import require_admin
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, MasterAccount, UserStrategy
from app.services import copy_engine

router = APIRouter()
logger = logging.getLogger("app.admin_provision")
audit_logger = logging.getLogger("app.audit.provision")


@router.get("/provision/pending")
async def list_pending_accounts(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all MT5 accounts awaiting manual first login by admin.
    Passwords are returned masked. Use /provision/reveal/{id} to get plain text."""
    result = await db.execute(
        select(MT5Account)
        .where(MT5Account.status == MT5Status.PENDING_PROVISION)
        .order_by(MT5Account.created_at.desc())
    )
    accounts = result.scalars().all()

    response = []
    for a in accounts:
        user_result = await db.execute(select(User).where(User.id == a.user_id))
        user = user_result.scalar_one_or_none()

        response.append({
            "id": str(a.id),
            "user_email": user.email if user else "unknown",
            "login": a.login,
            "password": "••••••••",
            "server": a.server,
            "status": a.status.value,
            "created_at": a.created_at.isoformat(),
        })

    audit_logger.info(f"Admin {admin.email} listed {len(response)} pending provision accounts")
    return response


@router.get("/provision/reveal/{account_id}")
async def reveal_provision_password(
    account_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reveal decrypted password for a pending provision account. Audit-logged."""
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        plain_password = decrypt_mt5_password(account.encrypted_password)
    except Exception:
        audit_logger.error(f"Admin {admin.email} failed to decrypt password for account {account.login}")
        raise HTTPException(status_code=500, detail="Failed to decrypt password")

    audit_logger.warning(
        f"AUDIT: Admin {admin.email} revealed password for MT5 account {account.login} (account_id={account_id})"
    )
    return {"password": plain_password}


@router.post("/provision/complete/{account_id}")
async def complete_provision(
    account_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin confirms manual first login is done. Activates the account."""
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status != MT5Status.PENDING_PROVISION:
        raise HTTPException(status_code=400, detail=f"Account status is '{account.status.value}', not pending_provision")

    # Mark as connected
    account.status = MT5Status.CONNECTED

    # Get user's active strategy for copy engine dispatch
    us_result = await db.execute(
        select(UserStrategy).where(
            UserStrategy.user_id == account.user_id,
            UserStrategy.is_active == True,
        )
    )
    active_us = us_result.scalar_one_or_none()

    master_login = None
    strategy_level = None
    risk_multiplier = 1.0

    if active_us:
        strat = await db.execute(select(Strategy).where(Strategy.id == active_us.strategy_id))
        strategy = strat.scalar_one_or_none()
        if strategy:
            strategy_level = strategy.level.value
            risk_multiplier = strategy.risk_multiplier
            ma_result = await db.execute(
                select(MasterAccount).where(MasterAccount.strategy_id == strategy.id)
            )
            master = ma_result.scalar_one_or_none()
            if master:
                master_login = master.login

    # Dispatch to Copy Engine
    try:
        copy_engine.dispatch_connect_terminal(
            account_id=str(account.id),
            login=account.login,
            encrypted_password=account.encrypted_password,
            server=account.server,
            strategy_level=strategy_level,
            master_login=master_login,
        )

        if strategy_level and master_login:
            copy_engine.dispatch_subscribe_strategy(
                account_id=str(account.id),
                client_login=account.login,
                strategy_level=strategy_level,
                master_login=master_login,
                risk_multiplier=risk_multiplier,
            )
    except Exception as e:
        logger.error(f"Failed to dispatch to copy engine for {account.login}: {e}")

    await db.commit()
    logger.info(f"MT5 account {account.login} provisioned and connected by admin")
    return {"message": f"Account {account.login} is now connected and active"}


@router.post("/provision/reset/{account_id}")
async def reset_provision(
    account_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reset account back to pending_provision for re-attempt."""
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.status = MT5Status.PENDING_PROVISION
    await db.commit()
    return {"message": f"Account {account.login} reset to pending_provision"}
