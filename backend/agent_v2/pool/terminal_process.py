"""PooledTerminalProcess — manages one MT5 terminal process dedicated to a single account."""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger

class TerminalProcessError(RuntimeError):
    pass

class PooledTerminalProcess:
    """Manages a single MT5 terminal instance.
    
    This class handles the OS-level process for exactly one account session.
    """

    def __init__(self, terminal_id: UUID, terminal_path: str):
        self.terminal_id = terminal_id
        self.terminal_path = Path(terminal_path)
        self.settings = get_v2_settings()
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self.log = get_logger("terminal_process").bind(
            terminal_id=str(terminal_id),
            path=str(terminal_path)
        )
        self.start_time: float = 0
        self.restart_count: int = 0
        self._last_restart_hour: float = time.time()
        self._restarts_this_hour: int = 0
        self.account_id: Optional[UUID] = None

    def start(self) -> bool:
        """Start the MT5 terminal process."""
        with self._lock:
            if self.is_alive():
                return True

            now = time.time()
            if now - self._last_restart_hour > 3600:
                self._last_restart_hour = now
                self._restarts_this_hour = 0
            
            max_restarts = getattr(self.settings, "MAX_RESTARTS_PER_HOUR", 10)
            if self._restarts_this_hour >= max_restarts:
                self.log.error("max restarts per hour reached", 
                               extra={"limit": max_restarts, "count": self._restarts_this_hour})
                return False

            # 1. Determine instance path
            # In institutional V2, each account has its own folder to ensure /portable isolation
            if self.account_id:
                instance_dir = Path(self.settings.V2_POOL_DIR) / str(self.account_id)
            else:
                instance_dir = self.terminal_path
            
            instance_dir.mkdir(parents=True, exist_ok=True)
            exe_path = self.terminal_path / "terminal64.exe"
            
            # If terminal64.exe is not in instance_dir, it might be the global path
            if not exe_path.exists():
                # Fallback to global setting if instance doesn't have it
                exe_path = Path(self.settings.MT5_TERMINAL_PATH)

            if not exe_path.exists():
                self.log.error("terminal64.exe not found", extra={"path": str(exe_path)})
                return False

            try:
                # Add identification tag for easy cleanup and monitoring
                env = os.environ.copy()
                env["V2_TERMINAL_ID"] = str(self.terminal_id)
                if self.account_id:
                    env["V2_ACCOUNT_ID"] = str(self.account_id)

                self._process = subprocess.Popen(
                    [str(exe_path), "/portable"],
                    cwd=str(instance_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env
                )
                self.start_time = time.time()
                self._restarts_this_hour += 1
                self.restart_count += 1
                self.log.info("terminal process started", extra={
                    "pid": self._process.pid,
                    "cwd": str(instance_dir)
                })
                return True
            except Exception as e:
                self.log.error("failed to start terminal process", exc_info=e)
                return False

    def stop(self):
        """Stop the MT5 terminal process."""
        with self._lock:
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                except Exception as e:
                    self.log.error("error stopping terminal", exc_info=e)
                finally:
                    self._process = None
                    self.start_time = 0

    def is_alive(self) -> bool:
        """Check if the terminal process is still running."""
        with self._lock:
            if not self._process:
                return False
            return self._process.poll() is None

    def get_metrics(self) -> Dict:
        """Get process-level metrics."""
        return {
            "uptime_s": time.time() - self.start_time if self.start_time > 0 else 0,
            "restart_count": self.restart_count,
            "is_alive": self.is_alive(),
            "pid": self._process.pid if self._process else None,
            "account_id": str(self.account_id) if self.account_id else None
        }
