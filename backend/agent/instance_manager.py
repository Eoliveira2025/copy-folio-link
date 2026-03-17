"""
MT5 Instance Manager — manages multiple MetaTrader 5 installations in separate folders.

The MT5 API limitation: only ONE login per terminal64.exe process/folder.
Solution: copy the base MT5 installation to unique folders, one per account.

Persistence: instance mapping is saved to a JSON file so accounts reconnect
to the same folders after agent restart.
"""

from __future__ import annotations
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from agent.config import get_agent_settings

settings = get_agent_settings()
logger = logging.getLogger("agent.instance_manager")

# Files to copy from base installation (skip heavy data folders on subsequent copies)
_ESSENTIAL_FILES = {"terminal64.exe", "terminal.exe", "metatrader64.exe"}
_SKIP_DIRS = {"Logs", "MQL5", "Tester", "Bases"}


class MT5InstanceManager:
    """
    Manages a pool of MT5 terminal installations, one per account.

    Each account (master or client) gets its own folder:
        C:\\MT5_Instances\\master_<id>\\
        C:\\MT5_Instances\\client_<id>\\

    The mapping account_id → folder_path is persisted to instances.json.
    """

    def __init__(
        self,
        base_path: str | None = None,
        instances_dir: str | None = None,
        mapping_file: str | None = None,
    ):
        self.base_path = Path(base_path or settings.MT5_BASE_PATH)
        self.instances_dir = Path(instances_dir or settings.MT5_INSTANCES_DIR)
        self.mapping_file = Path(mapping_file or settings.MT5_INSTANCE_MAPPING_FILE)

        self._lock = Lock()
        self._instances: Dict[str, str] = {}  # account_key → folder path
        self._processes: Dict[str, int] = {}  # account_key → terminal PID (optional tracking)

        # Ensure directories exist
        self.instances_dir.mkdir(parents=True, exist_ok=True)

        # Load persisted mapping
        self._load_mapping()

        logger.info(
            f"InstanceManager initialized: base={self.base_path}, "
            f"instances_dir={self.instances_dir}, "
            f"known_instances={len(self._instances)}"
        )

    # ── Public API ────────────────────────────────────────────────

    def get_terminal_path(self, account_key: str) -> str:
        """
        Return the terminal64.exe path for an account.
        Creates the instance folder (copies base MT5) if it doesn't exist.

        account_key: e.g. "master_<uuid>" or "client_<uuid>"
        """
        with self._lock:
            if account_key in self._instances:
                folder = Path(self._instances[account_key])
                exe = folder / "terminal64.exe"
                if exe.exists():
                    return str(exe)
                # Folder recorded but exe missing — recreate
                logger.warning(f"Instance folder missing for {account_key}, recreating...")

            folder = self._create_instance(account_key)
            self._instances[account_key] = str(folder)
            self._save_mapping()
            return str(folder / "terminal64.exe")

    def release_instance(self, account_key: str, delete_folder: bool = False):
        """
        Release an instance when an account is removed.
        Optionally delete the folder to free disk space.
        """
        with self._lock:
            folder_str = self._instances.pop(account_key, None)
            self._processes.pop(account_key, None)
            self._save_mapping()

        if folder_str and delete_folder:
            folder = Path(folder_str)
            if folder.exists():
                try:
                    # Kill any terminal process using this folder
                    self._kill_terminal_in_folder(folder)
                    time.sleep(1)
                    shutil.rmtree(folder, ignore_errors=True)
                    logger.info(f"Deleted instance folder: {folder}")
                except Exception as e:
                    logger.error(f"Failed to delete instance folder {folder}: {e}")

    def get_all_instances(self) -> Dict[str, str]:
        """Return a copy of the current instance mapping."""
        with self._lock:
            return dict(self._instances)

    def cleanup_orphaned(self, active_keys: set[str]):
        """Remove instance folders that are no longer in use."""
        with self._lock:
            orphaned = set(self._instances.keys()) - active_keys
            for key in orphaned:
                folder_str = self._instances.pop(key, None)
                if folder_str:
                    logger.info(f"Cleaning orphaned instance: {key} → {folder_str}")
            if orphaned:
                self._save_mapping()

    # ── Instance creation ─────────────────────────────────────────

    def _create_instance(self, account_key: str) -> Path:
        """Copy the base MT5 installation to a new unique folder."""
        folder = self.instances_dir / account_key

        if folder.exists():
            exe = folder / "terminal64.exe"
            if exe.exists():
                logger.info(f"Reusing existing instance: {folder}")
                return folder
            # Folder exists but no exe — remove and recreate
            shutil.rmtree(folder, ignore_errors=True)

        logger.info(f"Creating MT5 instance: {self.base_path} → {folder}")
        start = time.time()

        try:
            # Full copy of base installation
            shutil.copytree(
                str(self.base_path),
                str(folder),
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("Logs", "*.log"),
            )
        except Exception as e:
            logger.error(f"Failed to copy MT5 base to {folder}: {e}")
            raise

        elapsed = time.time() - start
        logger.info(f"Instance created in {elapsed:.1f}s: {folder}")

        # Verify terminal exists
        exe = folder / "terminal64.exe"
        if not exe.exists():
            raise FileNotFoundError(f"terminal64.exe not found in {folder}")

        return folder

    # ── Persistence ───────────────────────────────────────────────

    def _load_mapping(self):
        """Load instance mapping from JSON file."""
        if self.mapping_file.exists():
            try:
                with open(self.mapping_file, "r") as f:
                    data = json.load(f)
                self._instances = data.get("instances", {})
                logger.info(f"Loaded {len(self._instances)} instance mappings from {self.mapping_file}")
            except Exception as e:
                logger.error(f"Failed to load instance mapping: {e}")
                self._instances = {}

    def _save_mapping(self):
        """Save instance mapping to JSON file."""
        try:
            self.mapping_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.mapping_file, "w") as f:
                json.dump({"instances": self._instances}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save instance mapping: {e}")

    # ── Process management ────────────────────────────────────────

    @staticmethod
    def _kill_terminal_in_folder(folder: Path):
        """Kill any terminal64.exe process running from a specific folder."""
        try:
            # Use WMIC to find processes by path
            folder_str = str(folder).replace("\\", "\\\\")
            result = subprocess.run(
                ["wmic", "process", "where",
                 f"ExecutablePath like '%{folder_str}%'",
                 "get", "ProcessId"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                       capture_output=True, timeout=5)
                        logger.info(f"Killed terminal PID {pid} in {folder}")
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Could not kill terminals in {folder}: {e}")
