"""Admin endpoints: user management, plan management, subscriptions, invoices, upgrade requests, terms."""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import require_admin
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, UserStrategy, MasterAccount, LOCKED_STRATEGIES
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.upgrade_request import UpgradeRequest, UpgradeRequestStatus
from app.models.terms import TermsDocument, TermsAcceptance
from app.schemas.plan import PlanCreate, PlanUpdate, PlanResponse, ChangePlanRequest
from app.schemas.billing import UpgradeRequestResponse, UpgradeRequestAction
from app.schemas.legal import AdminTermsListItem, AdminCreateTerms, AdminUpdateTerms
from app.services import copy_engine
from app.services.strategy_switcher import switch_user_strategy_for_plan
from app.services.payments import get_gateway, GatewayStatus

router = APIRouter()


# ── Dashboard ───────────────────────────────────────────

@router.get("/dashboard")
async def admin_dashboard(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.execute(select(func.count(User.id)))
    active_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    trial_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.TRIAL)
    )
    blocked_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.BLOCKED)
    )
    pending_inv = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.PENDING)
    )
    overdue_inv = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.OVERDUE)
    )
    revenue = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0.0)).where(Invoice.status == InvoiceStatus.PAID)
    )

    return {
        "total_users": total.scalar() or 0,
        "active_accounts": active_subs.scalar() or 0,
        "trial_accounts": trial_subs.scalar() or 0,
        "blocked_accounts": blocked_subs.scalar() or 0,
        "pending_invoices": pending_inv.scalar() or 0,
        "overdue_invoices": overdue_inv.scalar() or 0,
        "total_revenue": float(revenue.scalar() or 0),
    }


# ── Plans CRUD ──────────────────────────────────────────

@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).order_by(Plan.price))
    return result.scalars().all()


@router.post("/plans", response_model=PlanResponse)
async def create_plan(body: PlanCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    plan = Plan(**body.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str, body: PlanUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    # Check if any active subscriptions use this plan
    subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.plan_id == plan_id)
    )
    if (subs.scalar() or 0) > 0:
        raise HTTPException(status_code=409, detail="Cannot delete plan with active subscriptions. Deactivate it instead.")
    await db.delete(plan)
    await db.commit()
    return {"message": "Plan deleted"}


# ── User Management ─────────────────────────────────────

@router.get("/users")
async def search_users(
    q: str = Query("", description="Search by email or MT5 login"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if q:
        query = query.outerjoin(MT5Account).where(
            or_(User.email.ilike(f"%{q}%"), MT5Account.login == int(q) if q.isdigit() else False)
        )
    result = await db.execute(query.limit(50))
    users = result.scalars().unique().all()

    response = []
    for u in users:
        mt5_result = await db.execute(select(MT5Account).where(MT5Account.user_id == u.id))
        mt5s = mt5_result.scalars().all()

        sub_result = await db.execute(
            select(Subscription).where(Subscription.user_id == u.id).order_by(Subscription.created_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        plan_name = None
        if sub and sub.plan_id:
            plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
            plan = plan_result.scalar_one_or_none()
            plan_name = plan.name if plan else None

        strategy_result = await db.execute(
            select(UserStrategy).where(UserStrategy.user_id == u.id, UserStrategy.is_active == True)
        )
        active_strategy = strategy_result.scalar_one_or_none()

        response.append({
            "id": str(u.id),
            "email": u.email,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "mt5_accounts": [
                {"id": str(m.id), "login": m.login, "server": m.server, "status": m.status.value}
                for m in mt5s
            ],
            "subscription_status": sub.status.value if sub else None,
            "plan_name": plan_name,
            "active_strategy": str(active_strategy.strategy_id) if active_strategy else None,
        })
    return response


# ── Plan assignment ─────────────────────────────────────

@router.post("/users/{user_id}/change-plan")
async def change_user_plan(
    user_id: str,
    body: ChangePlanRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Validate plan exists
    plan_result = await db.execute(select(Plan).where(Plan.id == body.plan_id))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not plan.active:
        raise HTTPException(status_code=400, detail="Plan is inactive")

    # Get or create subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="User has no subscription")

    old_plan_id = sub.plan_id
    sub.plan_id = plan.id

    # If upgrading from blocked, reactivate
    if sub.status == SubscriptionStatus.BLOCKED:
        sub.status = SubscriptionStatus.ACTIVE

    # Switch strategy to match new plan
    switch_result = await switch_user_strategy_for_plan(user_id, plan, db)

    await db.commit()
    return {
        "message": f"User plan changed to '{plan.name}'",
        "old_plan_id": str(old_plan_id) if old_plan_id else None,
        "new_plan_id": str(plan.id),
        "strategy_switch": switch_result,
    }


# ── Subscriptions list ──────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(
    status: str = Query("", description="Filter by status"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Subscription).order_by(Subscription.created_at.desc())
    if status:
        query = query.where(Subscription.status == SubscriptionStatus(status))
    result = await db.execute(query.limit(100))
    subs = result.scalars().all()

    response = []
    for s in subs:
        user_result = await db.execute(select(User).where(User.id == s.user_id))
        user = user_result.scalar_one_or_none()
        plan_name = None
        if s.plan_id:
            p = await db.execute(select(Plan).where(Plan.id == s.plan_id))
            plan_obj = p.scalar_one_or_none()
            plan_name = plan_obj.name if plan_obj else None

        response.append({
            "id": str(s.id),
            "user_email": user.email if user else "unknown",
            "user_id": str(s.user_id),
            "plan_name": plan_name,
            "status": s.status.value,
            "trial_start": s.trial_start.isoformat() if s.trial_start else None,
            "trial_end": s.trial_end.isoformat() if s.trial_end else None,
            "created_at": s.created_at.isoformat(),
        })
    return response


# ── Invoices list ────────────────────────────────────────

@router.get("/invoices")
async def list_all_invoices(
    status: str = Query("", description="Filter by status"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Invoice).order_by(Invoice.issue_date.desc())
    if status:
        query = query.where(Invoice.status == InvoiceStatus(status))
    result = await db.execute(query.limit(100))
    invoices = result.scalars().all()

    response = []
    for inv in invoices:
        sub_result = await db.execute(select(Subscription).where(Subscription.id == inv.subscription_id))
        sub = sub_result.scalar_one_or_none()
        user_email = "unknown"
        if sub:
            user_result = await db.execute(select(User).where(User.id == sub.user_id))
            user = user_result.scalar_one_or_none()
            user_email = user.email if user else "unknown"

        response.append({
            "id": str(inv.id),
            "user_email": user_email,
            "amount": inv.amount,
            "currency": inv.currency,
            "status": inv.status.value,
            "issue_date": inv.issue_date.isoformat(),
            "due_date": inv.due_date.isoformat(),
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            "provider": inv.provider.value if inv.provider else None,
        })
    return response


# ── Existing endpoints ──────────────────────────────────

@router.post("/users/{user_id}/unlock-strategy/{strategy_id}")
async def unlock_strategy(
    user_id: str, strategy_id: str,
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy or strategy.level not in LOCKED_STRATEGIES:
        raise HTTPException(status_code=400, detail="Strategy not found or doesn't require unlock")
    existing = await db.execute(
        select(UserStrategy).where(UserStrategy.user_id == user_id, UserStrategy.strategy_id == strategy_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already unlocked")
    db.add(UserStrategy(user_id=user_id, strategy_id=strategy_id, unlocked_by_admin=True, is_active=False))
    await db.commit()
    return {"message": "Strategy unlocked"}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str, new_password: str,
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(new_password)
    await db.commit()
    return {"message": "Password reset"}


@router.post("/users/{user_id}/disconnect-mt5/{account_id}")
async def admin_disconnect_mt5(
    user_id: str, account_id: str,
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id, MT5Account.user_id == user_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    try:
        copy_engine.dispatch_disconnect_terminal(str(account.id), account.login)
    except Exception:
        pass
    account.status = MT5Status.DISCONNECTED
    await db.commit()
    return {"message": f"MT5 account {account.login} disconnected"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    mt5_result = await db.execute(
        select(MT5Account).where(MT5Account.user_id == user_id, MT5Account.status == MT5Status.BLOCKED)
    )
    for account in mt5_result.scalars().all():
        account.status = MT5Status.CONNECTED
        us_result = await db.execute(
            select(UserStrategy).where(UserStrategy.user_id == user_id, UserStrategy.is_active == True)
        )
        active_us = us_result.scalar_one_or_none()
        if active_us:
            strat = await db.execute(select(Strategy).where(Strategy.id == active_us.strategy_id))
            strategy = strat.scalar_one_or_none()
            if strategy:
                ma = await db.execute(select(MasterAccount).where(MasterAccount.strategy_id == strategy.id))
                master = ma.scalar_one_or_none()
                if master:
                    try:
                        copy_engine.dispatch_unblock_account(
                            account_id=str(account.id), login=account.login,
                            encrypted_password=account.encrypted_password, server=account.server,
                            strategy_level=strategy.level.value, master_login=master.login,
                            risk_multiplier=strategy.risk_multiplier,
                        )
                    except Exception:
                        pass

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.ACTIVE
    await db.commit()
    return {"message": "User unblocked"}


@router.post("/check-payments")
async def check_payments_now(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    pending = await db.execute(
        select(Invoice).where(
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.external_id.isnot(None),
            Invoice.provider.isnot(None),
        )
    )
    checked = 0
    paid = 0
    for invoice in pending.scalars().all():
        try:
            gateway = get_gateway(invoice.provider.value)
            result = await gateway.check_status(invoice.external_id)
            checked += 1
            if result.status == GatewayStatus.PAID:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_at = datetime.now(timezone.utc)
                paid += 1
                sub = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
                subscription = sub.scalar_one_or_none()
                if subscription and subscription.status == SubscriptionStatus.BLOCKED:
                    subscription.status = SubscriptionStatus.ACTIVE
        except Exception:
            pass
    await db.commit()
    return {"message": f"Checked {checked} invoices, {paid} newly paid"}


@router.get("/users/{user_id}/invoices")
async def user_payment_history(
    user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice).join(Subscription).where(Subscription.user_id == user_id).order_by(Invoice.issue_date.desc())
    )
    invoices = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "amount": i.amount,
            "currency": i.currency,
            "status": i.status.value,
            "issue_date": i.issue_date.isoformat(),
            "due_date": i.due_date.isoformat(),
            "paid_at": i.paid_at.isoformat() if i.paid_at else None,
        }
        for i in invoices
    ]


# ── Upgrade Requests ────────────────────────────────────

@router.get("/upgrade-requests")
async def list_upgrade_requests(
    status: str = Query("", description="Filter by status: pending, approved, rejected"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(UpgradeRequest).order_by(UpgradeRequest.created_at.desc())
    if status:
        query = query.where(UpgradeRequest.status == UpgradeRequestStatus(status))
    result = await db.execute(query.limit(100))
    requests = result.scalars().all()

    response = []
    for r in requests:
        user_result = await db.execute(select(User).where(User.id == r.user_id))
        user = user_result.scalar_one_or_none()
        current_name = None
        target_name = None
        target_price = None
        if r.current_plan_id:
            cp = await db.execute(select(Plan).where(Plan.id == r.current_plan_id))
            p = cp.scalar_one_or_none()
            current_name = p.name if p else None
        if r.target_plan_id:
            tp = await db.execute(select(Plan).where(Plan.id == r.target_plan_id))
            p = tp.scalar_one_or_none()
            if p:
                target_name = p.name
                target_price = p.price
        response.append(UpgradeRequestResponse(
            id=r.id, user_id=r.user_id,
            user_email=user.email if user else "unknown",
            current_plan_name=current_name, target_plan_name=target_name,
            target_plan_price=target_price, mt5_balance=r.mt5_balance,
            status=r.status.value, admin_note=r.admin_note,
            created_at=r.created_at, resolved_at=r.resolved_at,
        ))
    return response


@router.post("/upgrade-requests/{request_id}")
async def handle_upgrade_request(
    request_id: str,
    body: UpgradeRequestAction,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject an upgrade request."""
    result = await db.execute(select(UpgradeRequest).where(UpgradeRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Upgrade request not found")
    if req.status != UpgradeRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request already processed")

    now = datetime.now(timezone.utc)
    req.resolved_at = now
    req.admin_note = body.note

    if body.action == "reject":
        req.status = UpgradeRequestStatus.REJECTED
        await db.commit()
        return {"message": "Upgrade request rejected"}

    if body.action != "approve":
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    # ── Approve: update plan, switch strategy, create invoice ──
    req.status = UpgradeRequestStatus.APPROVED

    # Get target plan
    target_result = await db.execute(select(Plan).where(Plan.id == req.target_plan_id))
    target_plan = target_result.scalar_one_or_none()
    if not target_plan:
        raise HTTPException(status_code=404, detail="Target plan no longer exists")

    # Update subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == req.user_id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="User has no subscription")

    sub.plan_id = target_plan.id
    sub.status = SubscriptionStatus.ACTIVE
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=sub.billing_cycle_days or 30)
    sub.next_billing_date = now + timedelta(days=sub.billing_cycle_days or 30)

    # Generate invoice for new plan starting immediately
    invoice = Invoice(
        subscription_id=sub.id,
        amount=target_plan.price,
        currency="USD",
        status=InvoiceStatus.PENDING,
        issue_date=now,
        due_date=now + timedelta(days=5),
    )
    db.add(invoice)

    # Switch user strategy to match new plan
    switch_result = await switch_user_strategy_for_plan(req.user_id, target_plan, db)

    await db.commit()
    return {
        "message": f"Upgrade approved. User moved to '{target_plan.name}'. Invoice of ${target_plan.price} generated.",
        "invoice_id": str(invoice.id),
        "strategy_switch": switch_result,
    }


# ── Terms Management ────────────────────────────────────

@router.get("/terms")
async def admin_list_terms(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all terms versions with acceptance counts."""
    result = await db.execute(
        select(
            TermsDocument,
            func.count(TermsAcceptance.id).label("acceptance_count"),
        )
        .outerjoin(TermsAcceptance, TermsAcceptance.terms_id == TermsDocument.id)
        .group_by(TermsDocument.id)
        .order_by(TermsDocument.version.desc())
    )
    rows = result.all()
    return [
        AdminTermsListItem(
            id=str(t.id),
            title=t.title,
            version=t.version,
            company_name=t.company_name,
            is_active=t.is_active,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
            acceptance_count=count,
        )
        for t, count in rows
    ]


@router.post("/terms")
async def admin_create_terms(
    body: AdminCreateTerms,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new terms version."""
    terms = TermsDocument(
        title=body.title,
        content=body.content,
        version=body.version,
        company_name=body.company_name,
        is_active=False,
    )
    db.add(terms)
    await db.commit()
    await db.refresh(terms)
    return {"message": "Terms created", "id": str(terms.id)}


@router.put("/terms/{terms_id}")
async def admin_update_terms(
    terms_id: str,
    body: AdminUpdateTerms,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit terms content."""
    result = await db.execute(select(TermsDocument).where(TermsDocument.id == terms_id))
    terms = result.scalar_one_or_none()
    if not terms:
        raise HTTPException(status_code=404, detail="Terms not found")

    if body.title is not None:
        terms.title = body.title
    if body.content is not None:
        terms.content = body.content
    if body.company_name is not None:
        terms.company_name = body.company_name

    await db.commit()
    return {"message": "Terms updated"}


@router.post("/terms/{terms_id}/activate")
async def admin_activate_terms(
    terms_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Activate a terms version (deactivates all others)."""
    result = await db.execute(select(TermsDocument).where(TermsDocument.id == terms_id))
    terms = result.scalar_one_or_none()
    if not terms:
        raise HTTPException(status_code=404, detail="Terms not found")

    # Deactivate all others
    all_terms = await db.execute(select(TermsDocument))
    for t in all_terms.scalars():
        t.is_active = (t.id == terms.id)

    await db.commit()
    return {"message": f"Terms v{terms.version} is now active"}


@router.get("/terms/{terms_id}/content")
async def admin_get_terms_content(
    terms_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get full terms content for editing."""
    result = await db.execute(select(TermsDocument).where(TermsDocument.id == terms_id))
    terms = result.scalar_one_or_none()
    if not terms:
        raise HTTPException(status_code=404, detail="Terms not found")
    return {
        "id": str(terms.id),
        "title": terms.title,
        "content": terms.content,
        "version": terms.version,
        "company_name": terms.company_name,
        "is_active": terms.is_active,
    }
