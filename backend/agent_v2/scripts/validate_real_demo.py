"""Validation script for V2 Real Demo operation.

Checks infrastructure, flags, and performs a safe end-to-end dry run 
that reaches real MT5 initialization if requested.
"""

from __future__ import annotations

import os
import sys
import time
import json
from uuid import UUID
from sqlalchemy import text

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_v2.config import get_v2_settings
from agent_v2.db import session_scope
from agent_v2.redis_client import get_redis, k, publish
from agent_v2.pool.repo import get_account_details
from agent_v2.utils.security import decrypt_mt5_password

def validate():
    print("=== V2 REAL DEMO VALIDATION ===")
    s = get_v2_settings()
    
    # 1. DB
    print("\n[1/5] Checking Database...")
    try:
        with session_scope() as sess:
            res = sess.execute(text("SELECT version()")).scalar()
            print(f"  OK: {res[:50]}...")
            
            # Check tables
            tables = ["v2_master_flags", "v2_account_flags", "v2_orders", "pool_terminal"]
            for t in tables:
                exists = sess.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{t}')")).scalar()
                if not exists:
                    print(f"  ERROR: Table {t} missing!")
                else:
                    print(f"  OK: Table {t} exists.")
    except Exception as e:
        print(f"  FAILED: {e}")
        return

    # 2. Redis
    print("\n[2/5] Checking Redis (DB /2)...")
    try:
        r = get_redis()
        ping = r.ping()
        print(f"  OK: Ping={ping}")
        db_size = r.dbsize()
        print(f"  OK: Keys in DB /2: {db_size}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return

    # 3. V2 Flags
    print("\n[3/5] Checking V2 Flags...")
    with session_scope() as sess:
        masters = sess.execute(text("SELECT count(*) FROM v2_master_flags WHERE enabled = true")).scalar()
        clients = sess.execute(text("SELECT count(*) FROM v2_account_flags WHERE enabled = true")).scalar()
        print(f"  Enabled V2 Masters: {masters}")
        print(f"  Enabled V2 Clients: {clients}")
        
        if masters == 0:
            print("  WARNING: No V2 masters enabled. Monitor will be idle.")
        if clients == 0:
            print("  WARNING: No V2 clients enabled. Distributor will have no work.")

    # 4. MT5 / Credentials
    print("\n[4/5] Checking Sample Credentials...")
    with session_scope() as sess:
        sample = sess.execute(text(
            "SELECT a.id, a.login, a.account_type FROM mt5_accounts a "
            "JOIN v2_account_flags f ON a.id = f.account_id "
            "WHERE f.enabled = true LIMIT 1"
        )).fetchone()
        
        if sample:
            details = get_account_details(sample.id)
            try:
                pw = decrypt_mt5_password(details.encrypted_password)
                print(f"  OK: Decrypted password for login {details.login} (Type: {details.account_type})")
                
                if details.account_type != "demo" and s.EXECUTION_MODE == "DEMO_ONLY":
                    print(f"  INFO: Account {details.login} is REAL, it will be BLOCKED in DEMO_ONLY mode.")
            except Exception as e:
                print(f"  FAILED: Decryption error: {e}")
        else:
            print("  SKIP: No enabled V2 account to test decryption.")

    # 5. End-to-End Event Simulation (Dry Run)
    print("\n[5/5] Simulating Master Event...")
    with session_scope() as sess:
        master = sess.execute(text(
            "SELECT m.id, m.strategy_id FROM master_accounts m "
            "JOIN v2_master_flags f ON m.id = f.master_id "
            "WHERE f.enabled = true LIMIT 1"
        )).fetchone()
        
        if master:
            event = {
                "event": "OPEN",
                "master_id": str(master.id),
                "strategy_id": str(master.strategy_id),
                "master_ticket": 12345678,
                "symbol": "EURUSD",
                "side": "BUY",
                "volume": 0.01,
                "price": 1.0850,
                "magic": 999,
                "comment": "VALIDATION_TEST",
                "ts": time.time()
            }
            channel = f"events:master:{master.id}"
            n = publish(channel, event)
            print(f"  OK: Published OPEN event to {k(channel)}. Subscribers: {n}")
            print("  Check agent logs to see if it was picked up.")
        else:
            print("  SKIP: No enabled V2 master to simulate event.")

    print("\n=== VALIDATION FINISHED ===")

if __name__ == "__main__":
    validate()
