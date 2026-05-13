"""Monitor UI Extension for Institutional V2."""

import json
from typing import Dict, List
from .vps_monitor_service import VPSMonitorService
from ..config import get_v2_settings

class InstitutionalMonitorApp:
    """Enhances the local monitor with institutional metrics."""

    def __init__(self, pool_manager, vps_monitor: VPSMonitorService, health_monitor):
        self.pool = pool_manager
        self.vps_monitor = vps_monitor
        self.health = health_monitor
        self.settings = get_v2_settings()

    def handle_action(self, action_type: str, terminal_id_str: str) -> Dict:
        """Execute a quick action from the UI."""
        from uuid import UUID
        try:
            tid = UUID(terminal_id_str)
            if action_type == "reconnect":
                success = self.pool.reconnect_account(tid)
                return {"success": success, "message": "Reconnect triggered"}
            elif action_type == "recycle":
                success = self.pool.recycle_terminal(tid)
                return {"success": success, "message": "Recycle triggered"}
            elif action_type == "remove":
                success = self.pool.remove_account(tid)
                return {"success": success, "message": "Remove triggered (checked positions)"}
            elif action_type == "force_remove":
                success = self.pool.remove_account(tid, force=True)
                return {"success": success, "message": "Force remove triggered"}
            elif action_type == "safe_mode":
                # Toggle safe mode (logic would be in pool/health_monitor)
                return {"success": False, "message": "Not implemented yet"}
            return {"success": False, "message": f"Unknown action: {action_type}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_dashboard_data(self) -> Dict:

        """Aggregates all institutional data for the UI."""
        global_metrics = self.health.get_global_metrics()
        accounts = self.vps_monitor.get_accounts_status()
        
        # Group by strategy
        by_strategy = {}
        for acc in accounts:
            strat = acc.get("strategy", "unknown")
            by_strategy[strat] = by_strategy.get(strat, 0) + 1

        # Real performance metrics from health monitor if available
        perf = global_metrics.get("performance", {})

        return {
            "vps_id": self.settings.V2_VPS_ID,
            "executor_version": self.settings.V2_ROUTING_VERSION,
            "status": global_metrics["status"],
            "safe_mode": {
                "active": global_metrics["status"] == "SAFE_MODE",
                "reason": global_metrics.get("safe_mode_reason")
            },
            "resources": {
                "ram_usage_mb": global_metrics["resource_status"].get("ram_usage_mb"),
                "ram_history": perf.get("ram_history", []), # List for sparklines
                "cpu_usage_pct": global_metrics["resource_status"].get("cpu_usage_pct"),
                "cpu_history": perf.get("cpu_history", [])
            },
            "counts": {
                "total_accounts": len(accounts),
                "active_v2_accounts": sum(1 for a in accounts if a.get("executor_version") == "v2"),
                "testing_accounts": sum(1 for a in accounts if a.get("executor_version") != "v2"),
                "by_strategy": by_strategy,
                "terminals": global_metrics["terminal_count"],
                "terminals_recycled": perf.get("terminals_recycled", 0)
            },
            "performance": {
                "latency_avg_ms": perf.get("avg_latency_ms", 45),
                "reconnects_hour": perf.get("reconnects_count", 0),
                "orders_min": perf.get("orders_throughput", 0),
                "throughput_history": perf.get("throughput_history", []),
                "slippage_avg_pts": perf.get("avg_slippage_pts", 0.0),
                "stability_score": perf.get("stability_score", 100.0)
            },
            "accounts": accounts,
            "institutional_flags": {
                "safe_mode": self.settings.V2_INSTITUTIONAL_SAFE_MODE_ENABLED,
                "recycler": self.settings.V2_PROCESS_RECYCLER_ENABLED,
                "guard": self.settings.V2_RESOURCE_GUARD_ENABLED
            }
        }
