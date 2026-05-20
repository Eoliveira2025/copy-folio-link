"""API router aggregation."""

from fastapi import APIRouter
from app.api.routes import (
    auth, mt5, strategies, billing, admin, legal, risk, operations, 
    dead_letter, admin_provision, recoveries, bridge, bridge_admin, 
    bridge_auditor_admin, metaapi_admin, metaapi_client, metaapi_reconciliation,
    metaapi_v3, internal_metaapi, performance_billing
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(mt5.router, prefix="/mt5", tags=["MT5 Accounts"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
api_router.include_router(billing.router, prefix="/billing", tags=["Billing"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(admin_provision.router, prefix="/admin", tags=["Admin Provisioning"])
api_router.include_router(legal.router, prefix="/legal", tags=["Legal"])
api_router.include_router(risk.router, prefix="/admin", tags=["Risk Protection"])
api_router.include_router(operations.router, prefix="/admin", tags=["Operations"])
api_router.include_router(dead_letter.router, prefix="/admin", tags=["Dead Letter Queue"])
api_router.include_router(recoveries.router, prefix="/admin", tags=["Copy Recoveries"])
api_router.include_router(bridge.router, prefix="/bridge", tags=["Bridge"])
api_router.include_router(bridge_admin.router, prefix="/admin", tags=["Bridge Admin"])
api_router.include_router(bridge_auditor_admin.router, prefix="/admin", tags=["Bridge Auditor"])
api_router.include_router(metaapi_admin.router, prefix="/admin/metaapi", tags=["MetaApi V3 Admin"])
api_router.include_router(metaapi_reconciliation.router, prefix="/admin/metaapi/reconciliation", tags=["MetaApi V3 Reconciliation"])
api_router.include_router(metaapi_client.router, prefix="/metaapi", tags=["MetaApi V3 Client"])
api_router.include_router(metaapi_v3.router, prefix="/metaapi", tags=["MetaApi V3 Institutional"])

# Internal endpoints for the isolated ct-metaapi-service
api_router.include_router(internal_metaapi.router, prefix="/internal/metaapi", tags=["MetaApi Internal"])
