"""MT5 Account connection endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import encrypt_mt5_password
from app.api.deps import get_current_user
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.schemas.mt5 import ConnectMT5Request, MT5AccountResponse

router = APIRouter()

ALLOWED_SERVERS = [
    "Exness-MT5Real", "Exness-MT5Real2", "Exness-MT5Real3", "Exness-MT5Trial",
]


@router.post("/connect", response_model=MT5AccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_mt5(
    body: ConnectMT5Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.server not in ALLOWED_SERVERS:
        raise HTTPException(status_code=400, detail=f"Server not supported. Allowed: {ALLOWED_SERVERS}")

    # Check duplicate
    existing = await db.execute(select(MT5Account).where(MT5Account.login == body.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This MT5 account is already connected")

    account = MT5Account(
        user_id=user.id,
        login=body.login,
        encrypted_password=encrypt_mt5_password(body.password),
        server=body.server,
        status=MT5Status.CONNECTED,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # TODO: dispatch to Copy Engine via Redis to establish MT5 terminal connection

    return account


@router.get("/accounts", response_model=list[MT5AccountResponse])
async def list_accounts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MT5Account).where(MT5Account.user_id == user.id))
    return result.scalars().all()


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_mt5(
    account_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id, MT5Account.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # TODO: notify Copy Engine to tear down terminal connection
    await db.delete(account)
    await db.commit()
