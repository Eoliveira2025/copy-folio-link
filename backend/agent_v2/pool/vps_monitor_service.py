"""VPSMonitorService — Aggregates data for the local monitor app and admission control."""

import threading
import time
import os
import psutil
from typing import List, Dict, Optional
from .background_terminal_manager import BackgroundTerminalManager
from .repo import list_pools_for_strategy, get_account_mapping
from ..utils.logger import get_logger
from ..config import get_v2_settings

class VPSMonitorService:
    """Service to provide real-time data for the Monitor UI and enforce safety limits."""

    def __init__(self, terminal_manager: BackgroundTerminalManager):
        self.tm = terminal_manager
        self.settings = get_v2_settings()
        self.log = get_logger("vps_monitor_service")
        self._metrics_cache = {}
        self._lock = threading.Lock()
        
    def get_vps_health(self) -> Dict:
        """Returns hardware-level metrics of the VPS."""
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\' if os.name == 'nt' else '/')
        
        # Calculate Capacity Score
        terminals = self.tm.get_all_terminals() if hasattr(self.tm, 'get_all_terminals') else []
        num_terminals = len(terminals)
        
        # Simple admission control logic
        safe_capacity = self.settings.MAX_TERMINALS_PER_VPS
        current_density = num_terminals / safe_capacity if safe_capacity > 0 else 1.0
        
        is_pressure = cpu > self.settings.MAX_CPU_USAGE_PCT or ram.percent > 85
        
        return {
            "vps_id": self.settings.V2_VPS_ID,
            "cpu_usage": cpu,
            "ram_usage_pct": ram.percent,
            "ram_available_mb": ram.available // (1024 * 1024),
            "disk_free_gb": disk.free // (1024**3),
            "terminal_count": num_terminals,
            "current_density": round(current_density, 2),
            "safe_capacity": safe_capacity,
            "resource_pressure": is_pressure,
            "admission_blocked": is_pressure or num_terminals >= safe_capacity
        }

    def get_accounts_status(self) -> List[Dict]:
        """Returns aggregated info for all accounts on this VPS with real-time stats."""
        from .repo import session_scope
        from sqlalchemy import text
        from ..redis_client import get_redis, k
        
        r = get_redis()
        vps_id = self.settings.V2_VPS_ID
        
        accounts = []
        try:
            with session_scope() as s:
                # Query accounts assigned to this VPS via their strategy pools
                rows = s.execute(text(
                    "SELECT a.id, a.login, a.balance, a.equity, a.connection_status, s.name as strategy_name "
                    "FROM mt5_accounts a "
                    "JOIN strategies s ON a.strategy_id = s.id "
                    "JOIN v2_account_flags f ON a.id = f.account_id "
                    "WHERE f.enabled = true AND a.executor_version = :ver"
                ), {"ver": self.settings.V2_ROUTING_VERSION}).fetchall()
                
                for row in rows:
                    # Try to get real-time stats from Redis (updated by MasterSync or TerminalProcess)
                    stats = r.hgetall(k(f"account:{row.id}:stats"))
                    
                    accounts.append({
                        "id": str(row.id),
                        "login": int(row.login),
                        "balance": float(stats.get(b"balance", row.balance or 0)),
                        "equity": float(stats.get(b"equity", row.equity or 0)),
                        "status": row.connection_status or "OFFLINE",
                        "strategy": row.strategy_name,
                        "pid": stats.get(b"pid", b"").decode() or None
                    })
        except Exception as e:
            self.log.error("Failed to query accounts for monitor", exc_info=e)
            
        return accounts

    def can_admit_new_account(self) -> bool:
        """Admission control: check if VPS can handle one more account."""
        health = self.get_vps_health()
        if health["admission_blocked"]:
            self.log.warning("Admission blocked: VPS at capacity or under pressure", extra=health)
            return False
        return True

