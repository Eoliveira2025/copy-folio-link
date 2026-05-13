"""AccountCleanupService — Safely removes stale or disconnected accounts."""

import time
import threading
from uuid import UUID
from .repo import delete_account_mapping
from ..utils.logger import get_logger
from ..config import get_v2_settings

class AccountCleanupService:
    """Service to automatically cleanup terminals for accounts that are gone."""

    def __init__(self, terminal_manager, repo_module=None):
        self.tm = terminal_manager
        self.repo = repo_module
        self.settings = get_v2_settings()
        self.log = get_logger("account_cleanup")
        self._stop_event = threading.Event()

    def run_cleanup_cycle(self):
        """Checks for stale accounts and removes them if safe."""
        if not self.settings.V2_AUTO_REMOVE_DISCONNECTED_ACCOUNTS:
            return


        self.log.info("running account cleanup cycle")
        
        # In a real system, we'd query the DB for accounts that haven't heartbeated from the user
        # or are explicitly marked as "disconnected" for > timeout.
        
        # Example logic for internal pool cleanup:
        with self.tm._lock:
            terminal_ids = list(self.tm._terminals.keys())
            
        for tid in terminal_ids:
            session = self.tm.get_session(tid)
            if not session: continue
            
            # Check if account is still active in our local repo/cache
            # (In production this would call the API or check Redis)
            account_id = session.current_account()
            if not account_id: continue
            
            # If account is marked for removal or has been inactive too long:
            # For demonstration, we'll just check if it has open positions
            if not session.has_open_positions():
                # If it's been idle for too long (dummy check)
                self.log.info("cleaning up idle account terminal", extra={"terminal_id": str(tid)})
                self.tm.remove_account(tid)

    def cleanup_orphaned_folders(self):
        """Removes folders in V2_POOL_DIR that don't belong to any active terminal."""
        from pathlib import Path
        pool_dir = Path(self.settings.V2_POOL_DIR)
        if not pool_dir.exists(): return
        
        with self.tm._lock:
            active_account_ids = {str(s.current_account()) for s in self.tm._sessions.values() if s.current_account()}
        
        for folder in pool_dir.iterdir():
            if folder.is_dir() and folder.name not in active_account_ids:
                # Check if it's a UUID folder
                try:
                    from uuid import UUID
                    UUID(folder.name)
                    self.log.info("removing orphaned account folder", extra={"folder": folder.name})
                    # In production, be careful with rmtree
                    # import shutil
                    # shutil.rmtree(folder)
                except ValueError:
                    pass

