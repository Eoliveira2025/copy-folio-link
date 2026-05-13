"""VPSMonitorService — Aggregates data for the local monitor app."""

import threading
import time
from typing import List, Dict
from .background_terminal_manager import BackgroundTerminalManager
from .repo import list_pools_for_strategy, get_account_mapping
from ..utils.logger import get_logger

class VPSMonitorService:
    """Service to provide real-time data for the Monitor UI."""

    def __init__(self, terminal_manager: BackgroundTerminalManager):
        self.tm = terminal_manager
        self.log = get_logger("vps_monitor_service")
        self._data_cache = []
        self._lock = threading.Lock()

    def get_accounts_status(self) -> List[Dict]:
        """Returns aggregated info for all accounts on this VPS."""
        # This would pull from DB + terminal manager
        # Mocking for structure
        return [
            {
                "id": "uuid-1",
                "login": 83097251,
                "client_name": "Demo Client",
                "strategy": "LOW",
                "status": "connected",
                "balance": 10000.0,
                "equity": 10050.0,
                "floating": 50.0,
                "open_orders": 2,
                "symbols": "EURUSD, XAUUSD",
                "pid": 1234,
                "cpu": "1.2%",
                "ram": "48MB",
                "heartbeat": "2s ago"
            }
        ]

    def remove_account(self, account_id: str, force: bool = False):
        """Action to remove account from executor."""
        # Logic to check open positions before removal
        pass
