"""Monitor UI Extension for Institutional V2."""

import json
from typing import Dict, List
from .vps_monitor_service import VPSMonitorService
from ..config import get_v2_settings

class InstitutionalMonitorApp:
    """Enhances the local monitor with institutional metrics."""

    def __init__(self, vps_monitor: VPSMonitorService, health_monitor):
        self.vps_monitor = vps_monitor
        self.health = health_monitor
        self.settings = get_v2_settings()

    def get_dashboard_data(self) -> Dict:
        """Aggregates all institutional data for the UI."""
        global_metrics = self.health.get_global_metrics()
        accounts = self.vps_monitor.get_accounts_status()
        
        # Group by strategy
        by_strategy = {}
        for acc in accounts:
            strat = acc.get("strategy", "unknown")
            by_strategy[strat] = by_strategy.get(strat, 0) + 1

        return {
            "vps_id": self.settings.V2_VPS_ID,
            "status": global_metrics["status"],
            "safe_mode": {
                "active": global_metrics["status"] == "SAFE_MODE",
                "reason": global_metrics.get("safe_mode_reason")
            },
            "resources": global_metrics["resource_status"],
            "counts": {
                "total_accounts": len(accounts),
                "by_strategy": by_strategy,
                "terminals": global_metrics["terminal_count"]
            },
            "performance": {
                "latency_avg_ms": 45, # Mock
                "reconnects_hour": 2,
                "orders_min": 12
            },
            "accounts": accounts
        }
