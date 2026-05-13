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
        if not self.settings.AUTO_REMOVE_DISCONNECTED_ACCOUNTS:
            return

        # 1. List accounts marked as disconnected in DB for > timeout
        # 2. For each:
        #    - Check open positions via terminal or DB
        #    - If 0 positions:
        #        - stop_terminal()
        #        - delete_account_mapping()
        #        - update backend status
        #    - Else:
        #        - mark as disconnected_with_open_positions
        pass
