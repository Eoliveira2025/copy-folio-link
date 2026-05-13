"""Script to validate symbol resolution for a specific demo account."""

import sys
from uuid import UUID
from ..utils.logger import get_logger
from ..pool.repo import get_account_details
from ..pool.account_session import AccountSession
from ..utils.symbol_discovery import SymbolDiscoveryService

def run():
    log = get_logger("validate_symbols")
    
    # Target demo account
    # We'll try to find it in the DB first
    # If not found, we can't really login
    account_login = 83097251
    
    from sqlalchemy import text
    from ..db import session_scope
    
    with session_scope() as s:
        row = s.execute(
            text("SELECT id FROM mt5_accounts WHERE login = :l"),
            {"l": str(account_login)}
        ).fetchone()
        
    if not row:
        log.error("account not found in database", login=account_login)
        return

    account_id = row.id
    details = get_account_details(account_id)
    
    log.info("testing login for account", login=account_login, server=details.server)
    
    # Use AccountSession to handle login
    # Path is not strictly necessary for this test if MT5 is already installed/available
    # but we follow the pattern
    session = AccountSession(
        account_id=account_id,
        terminal_path="C:\\copytrade_v2\\test_symbol_discovery"
    )
    
    try:
        with session.login_scope() as login_ok:
            if not login_ok:
                log.error("login failed")
                return
                
            log.info("login successful")
            
            # 1. List some symbols
            all_symbols = SymbolDiscoveryService.list_all_for_account(account_id)
            log.info("total symbols available", count=len(all_symbols))
            log.info("sample symbols", sample=all_symbols[:10])
            
            # 2. Test resolution
            for raw in ["EURUSD", "XAUUSD"]:
                resolved = SymbolDiscoveryService.resolve(account_id, raw)
                log.info("resolution test", raw=raw, resolved=resolved)
                
    except Exception as e:
        log.error("test failed", exc_info=e)

if __name__ == "__main__":
    run()
