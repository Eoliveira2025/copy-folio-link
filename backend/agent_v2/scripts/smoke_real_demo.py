"""Smoke test for REAL DEMO execution.

This script manually enqueues an OrderTask to a running V2 agent
to verify real MT5 login and order_send on a demo account.

Assumes:
1. Agent V2 is running (python -m agent_v2.bootstrap)
2. At least one pool is ACTIVE
3. Account is a DEMO account flagged for V2
"""

import sys
import os
import time
from uuid import UUID

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_v2.config import get_v2_settings
from agent_v2.redis_client import publish
from agent_v2.db import session_scope
from sqlalchemy import text

def smoke_real_demo():
    print("=== SMOKE REAL DEMO EXECUTION ===")
    
    with session_scope() as sess:
        # Find a candidate demo account
        client = sess.execute(text(
            "SELECT a.id, a.login, a.strategy_id, m.master_id, m.pool_id, m.terminal_id "
            "FROM mt5_accounts a "
            "JOIN v2_account_flags f ON a.id = f.account_id "
            "JOIN account_terminal_map m ON a.id = m.account_id "
            "WHERE f.enabled = true AND a.account_type = 'demo' LIMIT 1"
        )).fetchone()
        
        if not client:
            print("ERROR: No enabled V2 demo account with active mapping found.")
            print("Make sure you ran the allocator and the account is mapped to a pool.")
            return

        print(f"Target: Login {client.login} (ID: {client.id})")
        print(f"Pool: {client.pool_id} (Terminal: {client.terminal_id})")

        # 1. Simulate Master OPEN
        print("\n1. Simulating Master OPEN...")
        master_ticket = int(time.time())
        event_open = {
            "event": "OPEN",
            "master_id": str(client.master_id),
            "strategy_id": str(client.strategy_id),
            "master_ticket": master_ticket,
            "symbol": "EURUSD",
            "side": "BUY",
            "volume": 0.01,
            "price": 1.0850,
            "magic": 12345,
            "comment": "SMOKE_TEST_V2",
            "ts": time.time()
        }
        publish(f"events:master:{client.master_id}", event_open)
        print(f"Event published. Watch agent logs for execution of ticket {master_ticket}.")
        
        print("\nWaiting 10 seconds for execution...")
        time.sleep(10)
        
        # 2. Check if order was persisted
        order = sess.execute(text(
            "SELECT client_ticket, status, retcode, broker_comment "
            "FROM v2_orders WHERE master_ticket = :mt AND account_id = :aid"
        ), {"mt": master_ticket, "aid": str(client.id)}).fetchone()
        
        if order:
            print(f"Order found in v2_orders: Status={order.status}, Ticket={order.client_ticket}, Retcode={order.retcode}")
            if order.status == "DONE":
                print("SUCCESS: Order executed successfully!")
                
                # 3. Simulate Master CLOSE
                print("\n2. Simulating Master CLOSE...")
                event_close = {
                    "event": "CLOSE",
                    "master_id": str(client.master_id),
                    "strategy_id": str(client.strategy_id),
                    "master_ticket": master_ticket,
                    "symbol": "EURUSD",
                    "ts": time.time()
                }
                publish(f"events:master:{client.master_id}", event_close)
                print("Close event published.")
            else:
                print(f"FAILED: Order execution failed. Comment: {order.broker_comment}")
        else:
            print("FAILED: No record found in v2_orders. Check if Distributor is running.")

if __name__ == "__main__":
    smoke_real_demo()
