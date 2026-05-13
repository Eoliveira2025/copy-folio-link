"""ProcessRecycler — Intelligent MT5 terminal recycling and reuse."""

from __future__ import annotations
import threading
import time
import shutil
from pathlib import Path
from typing import Dict, List, Callable
from uuid import UUID
from ..config import get_v2_settings
from ..utils.logger import get_logger
from .terminal_footprint_optimizer import optimize_terminal_folder

class ProcessRecycler:
    """Recycles MT5 processes and cleans working directories for reuse."""

    def __init__(self, 
                 get_terminals: Callable[[], List[object]],
                 has_open_positions: Callable[[UUID], bool]):
        self.settings = get_v2_settings()
        self.log = get_logger("process_recycler")
        self._get_terminals = get_terminals
        self._has_open_positions = has_open_positions
        self._last_recycle: Dict[UUID, float] = {}

    def recycle_and_clean(self, terminal_id: UUID, terminal_path: str):
        """Clean terminal session files and optimize for reuse."""
        self.log.info("Cleaning terminal for reuse", terminal_id=str(terminal_id))
        
        # 1. Clean history and logs
        optimize_terminal_folder(terminal_path)
        
        # 2. Reset last recycle timer
        self._last_recycle[terminal_id] = time.time()

    def check_and_recycle(self):
        """Checks if any terminals need recycling (leaks or uptime)."""
        if not self.settings.V2_PROCESS_RECYCLER_ENABLED:
            return

        terminals = self._get_terminals()
        now = time.time()
        
        for t in terminals:
            tid = t.terminal_id
            
            # Skip if recently recycled (within 24 hours)
            if tid in self._last_recycle and (now - self._last_recycle[tid]) < 86400:
                continue
            
            # NEVER recycle if there are open positions
            if self._has_open_positions(tid):
                continue
                
            self.log.info("Scheduled recycling", terminal_id=str(tid))
            try:
                t.stop()
                self.recycle_and_clean(tid, str(t.terminal_path))
                t.start()
            except Exception as e:
                self.log.error("Recycle failed", terminal_id=str(tid), exc_info=e)

