"""Smoke test for real demo execution with automatic symbol resolution."""

import time
import uuid
from uuid import UUID
from ..utils.logger import get_logger
from ..pool.repo import get_account_details
from ..pool.account_session import AccountSession
from ..exec.order_executor import OrderExecutor
from ..exec.order_task import OrderTask, OrderAction, OrderSide

def run():
    log = get_logger("smoke_symbol_exec")
    
    # Using the same demo account
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
    
    # We need a dummy pool/master/strategy context
    dummy_id = uuid.uuid4()
    
    executor = OrderExecutor(
        pool_id=dummy_id,
        terminal_id=dummy_id,
        pool_name="smoke_test_pool",
        master_id=dummy_id,
        strategy_id=dummy_id
    )
    
    session = AccountSession(
        account_id=account_id,
        terminal_path="C:\\copytrade_v2\\smoke_symbol_exec"
    )
    
    try:
        with session.login_scope() as login_ok:
            if not login_ok:
                log.error("login failed")
                return
            
            # Step 1: OPEN with raw symbol
            task_open = OrderTask(
                account_id=account_id,
                symbol="EURUSD", # RAW
                action=OrderAction.OPEN,
                side=OrderSide.BUY,
                volume=0.01,
                idempotency_key=f"smoke_{int(time.time())}",
                master_ticket=12345
            )
            
            log.info("testing OPEN with raw symbol", symbol=task_open.symbol)
            res_open = executor.execute(task_open, session.info)
            log.info("OPEN result", retcode=res_open.retcode, deal=res_open.deal_ticket)
            
            if res_open.retcode != 10009: # TRADE_RETCODE_DONE
                log.error("OPEN failed, skipping CLOSE")
                return
                
            # Wait a bit
            time.sleep(2)
            
            # Step 2: CLOSE
            task_close = OrderTask(
                account_id=account_id,
                symbol="EURUSD", # RAW
                action=OrderAction.CLOSE,
                client_ticket=res_open.order_ticket or res_open.deal_ticket,
                idempotency_key=f"smoke_close_{int(time.time())}",
                master_ticket=12345
            )
            
            log.info("testing CLOSE with raw symbol", symbol=task_close.symbol, ticket=task_close.client_ticket)
            res_close = executor.execute(task_close, session.info)
            log.info("CLOSE result", retcode=res_close.retcode)
            
    except Exception as e:
        log.error("smoke test failed", exc_info=e)

if __name__ == "__main__":
    run()
