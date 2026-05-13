"""ProcessRecycler — Intelligent MT5 terminal recycling."""

from __future__ import annotations
import threading
import time
from typing import Dict, List, Callable
from uuid import UUID
from ..config import get_v2_settings
from ..utils.logger import get_logger

class ProcessRecycler:
    """Recycles MT5 processes to prevent memory leaks and ensure stability."""

    def __init__(self, 
                 get_terminals: Callable[[], List[object]],
                 has_open_positions: Callable[[UUID], bool]):
        self.settings = get_v2_settings()
        self.log = get_logger("process_recycler")
        self._get_terminals = get_terminals
        self._has_open_positions = has_open_positions
        self._last_recycle: Dict[UUID, float] = {}

    def check_and_recycle(self):
        """Checks if any terminals need recycling."""
        if not self.settings.V2_PROCESS_RECYCLER_ENABLED:
            return

        terminals = self._get_terminals()
        now = time.time()
        
        for t in terminals:
            tid = t.terminal_id
            
            # Skip if recently recycled (within 24 hours)
            if tid in self._last_recycle and (now - self._last_recycle[tid]) < 86400:
                continue
            
            # Check if terminal has open positions - NEVER recycle if it does
            if self._has_open_positions(tid):
                continue
                
            # Recycle logic: check memory or time
            # For now, let's say every 24h if no positions
            self.log.info("recycling terminal", extra={"terminal_id": str(tid)})
            try:
                t.stop()
                time.sleep(1)
                t.start()
                self._last_recycle[tid] = now
            except Exception as e:
                self.log.error("failed to recycle terminal", extra={"terminal_id": str(tid)}, exc_info=e)
