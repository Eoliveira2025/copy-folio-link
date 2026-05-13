"""AutoProvisioner — creates a fresh MT5 terminal folder for a pool.

Layout (Windows V2):
    C:\\MT5_Pool_V2\\<strategy_key>\\pool_NN\\
        terminal64.exe                (copied/symlinked from MT5_BASE_PATH)
        config\\common.ini             (headless, light)
        MQL5\\                          (empty — clients have no EA)
        Bases\\                         (empty)
        logs\\

Strategy isolation:
  - Each strategy has its own subdirectory; pools never share folders.
  - Folder name encodes strategy_key, making logs/grep trivial.

This increment ONLY:
  * computes paths
  * creates the folder skeleton (idempotent)
  * writes a minimal common.ini for headless operation
  * does NOT spawn the terminal yet
  * does NOT log in any account

Process spawn + login serialization land in increment 3.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from . import repo


_HEAVY_DIRS = ("Bases", "MQL5/Experts", "MQL5/Indicators",
               "MQL5/Scripts", "Templates", "Profiles")

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


def _write_common_ini(path: Path) -> None:
    """Minimal headless ini — no charts, no EAs (clients are pure API)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Common]\n"
        "Login=0\n"
        "ProxyEnable=0\n"
        "CertInstall=0\n"
        "NewsEnable=0\n"
        "[Experts]\n"
        "AllowLiveTrading=1\n"
        "AllowDllImport=0\n"
        "Enabled=0\n"
        "Account=0\n"
        "Profile=0\n"
        "[StartUp]\n"
        "Expert=\n"
        "Symbol=\n"
        "Period=\n"
        "[Charts]\n"
        "ProfileLast=Default\n"
        "MaxBars=1000\n",
        encoding="utf-16-le",
    )


class AutoProvisioner:
    """Creates pool folders on disk and registers them in `pool_terminal`."""

    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("provisioner")

    # ── disk layout ────────────────────────────────────────────────
    def _create_folder_skeleton(self, terminal_path: str) -> None:
        root = Path(terminal_path)
        root.mkdir(parents=True, exist_ok=True)
        for sub in ("config", "MQL5", "Bases", "logs"):
            (root / sub).mkdir(parents=True, exist_ok=True)
            
        # Copy terminal64.exe from base path if it doesn't exist
        base_path = self.settings.V2_MT5_BASE_PATH
        if base_path:
            source_exe = Path(base_path) / _TERMINAL_EXE
            target_exe = root / _TERMINAL_EXE
            if source_exe.exists() and not target_exe.exists():
                shutil.copy2(source_exe, target_exe)
                self.log.info("copied terminal64.exe", source=str(source_exe), target=str(target_exe))

        # Light footprint: drop heavy MT5 subdirs if MT5_BASE_PATH was copied.
        for d in _HEAVY_DIRS:
            target = root / d
            if target.exists() and target.is_dir():
                shutil.rmtree(target)

        _write_common_ini(root / "config" / "common.ini")

    # ── public API ────────────────────────────────────────────────
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
        """Create the next pool folder for a strategy and register it.

        Idempotent at the DB level via UNIQUE(pool_name).
        Idempotent at the filesystem level (mkdir exist_ok).
        """
        cap = capacity or self.settings.POOL_CAPACITY

        existing = repo.list_pools_for_strategy(strategy_id)
        # Cross-strategy guard (defense in depth — DB FK already enforces).
        for row in existing:
            if row.strategy_id != strategy_id:
                raise RuntimeError(
                    f"strategy mismatch in pool repo: {row.pool_name}"
                )
        pool_name = repo.next_pool_name(
            strategy_key, (r.pool_name for r in existing)
        )
        terminal_path = pool_terminal_path(strategy_key, pool_name)

        log = self.log.bind(
            master_id=str(master_id),
            strategy_id=str(strategy_id),
            pool_name=pool_name,
        )

        # Filesystem (best-effort on non-Windows / dev env)
        try:
            self._create_folder_skeleton(terminal_path)
        except OSError as e:
            log.error(
                "filesystem provision failed; registering DB row only",
                extra={"action": "provision_fs_failed"},
                exc_info=e,
            )

        row = repo.insert_pool(
            pool_name=pool_name,
            master_id=master_id,
            strategy_id=strategy_id,
            terminal_path=terminal_path,
            capacity=cap,
            status=status,
            host=host or os.environ.get("COMPUTERNAME"),
        )
        log.info(
            "pool provisioned",
            extra={
                "action": "pool_provisioned",
                "pool_id": str(row.id),
                "terminal_path": terminal_path,
            },
        )
        return row
