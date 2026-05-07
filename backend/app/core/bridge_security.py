"""Bridge token validation (header: Authorization: Bearer <BRIDGE_TOKEN>)."""

import hmac
from fastapi import Header, HTTPException, status
from app.core.bridge_config import get_bridge_settings


async def verify_bridge_token(authorization: str | None = Header(default=None)) -> None:
    cfg = get_bridge_settings()
    if not cfg.BRIDGE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bridge feature is disabled",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing bridge token")
    token = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(token, cfg.BRIDGE_TOKEN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bridge token")
