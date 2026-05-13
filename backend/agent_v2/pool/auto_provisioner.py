"""AutoProvisioner — creates a fresh MT5 terminal folder for a pool with automatic onboarding."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from . import repo
from .terminal_footprint_optimizer import optimize_terminal_folder

_TERMINAL_EXE = "terminal64.exe"

def strategy_key_for(strategy_name: str) -> str:
    """Normalize strategy name to a folder-safe key."""
    return "".join(c for c in strategy_name.lower() if c.isalnum() or c == "_") or "default"

def pool_root_for(strategy_key: str) -> Path:
    settings = get_v2_settings()
    return Path(settings.V2_POOL_DIR) / strategy_key

def pool_terminal_path(strategy_key: str, pool_name: str) -> str:
    """Absolute path of a pool's terminal folder."""
    return str(pool_root_for(strategy_key) / pool_name)

class AutoProvisioner:
    """Creates pool folders on disk and registers them in `pool_terminal`."""

    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("provisioner")

    def _create_folder_skeleton(self, terminal_path: str) -> None:
        root = Path(terminal_path)
        root.mkdir(parents=True, exist_ok=True)
        
        # Copy terminal64.exe from base path if it doesn't exist
        # We assume the base MT5 is already there or we use the global settings path
        base_path = self.settings.MT5_BASE_PATH
        source_exe = Path(base_path) / _TERMINAL_EXE
        target_exe = root / _TERMINAL_EXE
        
        if source_exe.exists() and not target_exe.exists():
            shutil.copy2(source_exe, target_exe)
            self.log.info("copied terminal64.exe", source=str(source_exe), target=str(target_exe))

        # Apply extreme footprint optimization
        optimize_terminal_folder(terminal_path)

    def provision(
        self,
        *,
        master_id: UUID,
        strategy_id: UUID,
        strategy_key: str,
        status: str = "STANDBY",
        capacity: Optional[int] = None,
        host: Optional[str] = None,
    ) -> repo.PoolRow:
        """Create the next pool folder for a strategy and register it."""
        cap = capacity or self.settings.POOL_CAPACITY

        existing = repo.list_pools_for_strategy(strategy_id)
        pool_name = repo.next_pool_name(
            strategy_key, (r.pool_name for r in existing)
        )
        terminal_path = pool_terminal_path(strategy_key, pool_name)

        log = self.log.bind(
            master_id=str(master_id),
            strategy_id=str(strategy_id),
            pool_name=pool_name,
        )

        try:
            self._create_folder_skeleton(terminal_path)
        except OSError as e:
            log.error("filesystem provision failed", exc_info=e)
            raise

        row = repo.insert_pool(
            pool_name=pool_name,
            master_id=master_id,
            strategy_id=strategy_id,
            terminal_path=terminal_path,
            capacity=cap,
            status=status,
            host=host or os.environ.get("COMPUTERNAME"),
        )
        log.info("pool provisioned", pool_id=str(row.id), path=terminal_path)
        return row

