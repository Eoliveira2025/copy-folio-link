"""ExecutionDeduplicationService — institutional protection against duplicate orders."""

from __future__ import annotations
import threading
import time
import hashlib
from collections import OrderedDict
from typing import Optional
from uuid import UUID
from ..utils.logger import get_logger
from ..config import get_v2_settings

class ExecutionDeduplicationService:
    """Institutional protection against duplicate orders.
    
    Prevents the same logical trade from being executed twice on the same account
    by tracking execution hashes and master tickets.
    """

    def __init__(self, max_entries: int = 10000):
        self._max = max_entries
        self._cache: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.Lock()
        self.settings = get_v2_settings()
        self.log = get_logger("deduplication")

    def _generate_hash(self, account_id: UUID, master_ticket: int, action: str, 
                       symbol: str, volume: float, strategy_id: UUID) -> str:
        """Generates a unique execution hash for a trade."""
        data = f"{account_id}:{master_ticket}:{action}:{symbol}:{volume:.4f}:{strategy_id}"
        return hashlib.sha256(data.encode()).hexdigest()

    def is_duplicate(self, account_id: UUID, master_ticket: int, action: str, 
                    symbol: str, volume: float, strategy_id: UUID) -> bool:
        """Checks if the order has already been executed."""
        if not self.settings.V2_EXECUTION_DEDUP_ENABLED:
            return False

        key = self._generate_hash(account_id, master_ticket, action, symbol, volume, strategy_id)
        now = time.time()
        
        with self._lock:
            if key in self._cache:
                self.log.critical("DUPLICATE ORDER BLOCKED", extra={
                    "account_id": str(account_id),
                    "master_ticket": master_ticket,
                    "action": action,
                    "symbol": symbol,
                    "volume": volume
                })
                return True
            
            # Record execution
            self._cache[key] = now
            if len(self._cache) > self._max:
                self._cache.popitem(last=False)
            return False

    def clear(self):
        """Clears the cache (use with caution, e.g. during recovery)."""
        with self._lock:
            self._cache.clear()
