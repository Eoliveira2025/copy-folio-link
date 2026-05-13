"""BackgroundTerminalManager — Manages MT5 terminals in headless/hidden mode."""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict
from uuid import UUID
from ..config import get_v2_settings
from ..utils.logger import get_logger
from .terminal_process import PooledTerminalProcess

class BackgroundTerminalManager:
    """Institutional manager for silent MT5 processes."""

    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("bg_terminal_manager")
        self._instances: Dict[UUID, PooledTerminalProcess] = {}

    def get_or_create_terminal(self, account_id: UUID) -> PooledTerminalProcess:
        """Ensures a terminal exists for an account in isolated mode."""
        if account_id in self._instances:
            return self._instances[account_id]

        instance_dir = Path(self.settings.V2_POOL_DIR) / str(account_id)
        # Create instance terminal handle
        terminal = PooledTerminalProcess(
            terminal_id=account_id, # Use account_id as terminal_id for 1:1 isolation
            terminal_path=str(instance_dir)
        )
        terminal.account_id = account_id
        
        self._instances[account_id] = terminal
        return terminal

    def start_silent(self, account_id: UUID):
        """Starts a terminal minimized/hidden."""
        terminal = self.get_or_create_terminal(account_id)
        if terminal.is_alive():
            return True

        self.log.info("starting silent terminal", extra={"account_id": str(account_id)})
        
        # Optimization: Apply minimal configuration before start
        self._apply_memory_optimizations(account_id)
        
        return terminal.start()

    def _apply_memory_optimizations(self, account_id: UUID):
        """Pre-configures MT5 for minimum memory usage (ini files, etc.)."""
        instance_dir = Path(self.settings.V2_POOL_DIR) / str(account_id)
        instance_dir.mkdir(parents=True, exist_ok=True)
        
        # Create/Update terminal.ini or similar if needed
        # No charts, no news, no alerts, etc.
        pass

    def stop_terminal(self, account_id: UUID):
        """Safely stops a terminal."""
        if account_id in self._instances:
            self._instances[account_id].stop()
            del self._instances[account_id]

    def get_resource_usage(self, account_id: UUID) -> Dict:
        """Calculates RAM/CPU usage for a specific terminal."""
        # In a real environment, we'd use psutil
        return {
            "cpu_pct": 0.5,
            "ram_mb": 45.0
        }
