import os
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

from ..config import get_v2_settings
from ..pool.vps_monitor_service import VPSMonitorService
from ..pool.background_terminal_manager import BackgroundTerminalManager # Mock or real
from ..utils.logger import get_logger

# We try to import the institutional UI logic if it exists
try:
    from .institutional_ui import InstitutionalMonitorApp
except ImportError:
    InstitutionalMonitorApp = None

app = FastAPI(title="CopyTrade V2 Institutional Monitor")
logger = get_logger("monitor_server")
settings = get_v2_settings()

# Setup templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Initialize components (lazily or in startup)
# In a real VPS, we'd need to link this to the running PoolManager.
# For now, we use the VPSMonitorService which can independently check resources and DB.
tm = BackgroundTerminalManager() # This might need proper initialization in a real env
monitor_service = VPSMonitorService(tm)

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "vps_id": settings.V2_VPS_ID})

@app.get("/health")
async def health_check():
    return {"status": "healthy", "vps_id": settings.V2_VPS_ID}

@app.get("/api/status")
async def get_status():
    try:
        health = monitor_service.get_vps_health()
        accounts = monitor_service.get_accounts_status()
        return {
            "vps": health,
            "accounts": accounts,
            "timestamp": os.times()[4] # uptime-ish or use time.time()
        }
    except Exception as e:
        logger.error("Failed to get status", exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/account/{account_id}/reconnect")
async def reconnect(account_id: UUID):
    # This would typically send a signal to the main executor or update Redis
    logger.info(f"Reconnect requested for {account_id}")
    return {"success": True, "message": "Reconnect command queued"}

@app.post("/api/account/{account_id}/recycle")
async def recycle(account_id: UUID):
    logger.info(f"Recycle requested for {account_id}")
    return {"success": True, "message": "Recycle command queued"}

@app.post("/api/account/{account_id}/safe_remove")
async def safe_remove(account_id: UUID):
    logger.info(f"Safe remove requested for {account_id}")
    return {"success": True, "message": "Safe remove command queued"}

@app.post("/api/account/{account_id}/force_remove")
async def force_remove(account_id: UUID):
    logger.info(f"Force remove requested for {account_id}")
    return {"success": True, "message": "Force remove command queued"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
