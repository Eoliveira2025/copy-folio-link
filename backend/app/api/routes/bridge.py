"""Bridge HTTP endpoint — receives signals from the EA on the master account."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.bridge_security import verify_bridge_token
from app.schemas.bridge import BridgeSignalIn, BridgeSignalAck
from app.services.bridge_service import ingest_signal

router = APIRouter()


@router.post("/signal", response_model=BridgeSignalAck, dependencies=[Depends(verify_bridge_token)])
async def receive_signal(payload: BridgeSignalIn, db: AsyncSession = Depends(get_db)) -> BridgeSignalAck:
    signal = await ingest_signal(db, payload)
    return BridgeSignalAck(status="received", signal_id=str(signal.id))


@router.get("/health")
async def bridge_health(_: None = Depends(verify_bridge_token)):
    return {"status": "ok"}
