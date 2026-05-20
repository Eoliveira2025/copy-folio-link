from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.api.deps import require_admin
from app.services.billing.performance_billing_service import PerformanceBillingService
from app.schemas.performance_billing import (
    BillingMethodCreate, BillingMethodResponse, 
    PerformanceCycleResponse, PerformanceUserSummary,
    PerformanceBillingDashboard
)

router = APIRouter(prefix="/v1/admin/performance-billing", tags=["admin-performance-billing"])

@router.get("/users", response_model=List[PerformanceUserSummary])
async def list_performance_users(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """List users for performance billing configuration."""
    return await PerformanceBillingService.get_performance_users(db)

@router.post("/method", response_model=BillingMethodResponse)
async def set_billing_method(
    body: BillingMethodCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Set or update user billing method."""
    return await PerformanceBillingService.set_billing_method(
        db, body.user_id, body.method.value, body.performance_percentage, admin.email
    )

@router.get("/cycles", response_model=List[PerformanceCycleResponse])
async def list_cycles(
    user_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """List billing cycles with filters."""
    return await PerformanceBillingService.get_cycles(db, user_id, status)

@router.post("/cycles/start")
async def start_cycle_manual(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Manually start a cycle."""
    cycle = await PerformanceBillingService.start_cycle(db, user_id, force=True)
    if not cycle:
        raise HTTPException(status_code=400, detail="Failed to start cycle. Check logs.")
    return cycle

@router.post("/cycles/close")
async def close_cycle_manual(
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Manually close an open cycle."""
    cycle = await PerformanceBillingService.close_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=400, detail="Failed to close cycle.")
    return cycle

@router.post("/cycles/{cycle_id}/generate-invoice")
async def generate_invoice_manual(
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Manually generate invoice for a cycle."""
    invoice = await PerformanceBillingService.generate_invoice(db, cycle_id)
    if not invoice:
        raise HTTPException(status_code=400, detail="Failed to generate invoice. Cycle must be CLOSED with profit.")
    return {"invoice_id": invoice.id, "status": "generated"}

@router.get("/summary", response_model=PerformanceBillingDashboard)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Get dashboard summary metrics."""
    return await PerformanceBillingService.get_dashboard_summary(db)
