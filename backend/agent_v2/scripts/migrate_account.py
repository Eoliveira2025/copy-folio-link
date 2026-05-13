"""Script to migrate accounts between executor versions (V1 <-> V2)."""

import sys
import argparse
from uuid import UUID
from sqlalchemy import text
from ..db import session_scope
from ..utils.logger import get_logger

log = get_logger("migration_tool")

def migrate(account_id: str, to_version: str):
    try:
        acc_id = UUID(account_id)
    except ValueError:
        print(f"Error: Invalid UUID {account_id}")
        return

    if to_version not in ('v1', 'v2'):
        print(f"Error: Invalid version {to_version}. Must be v1 or v2.")
        return

    with session_scope() as s:
        # 1. Check if account exists
        row = s.execute(text("SELECT id, login, executor_version FROM mt5_accounts WHERE id = :aid"), 
                        {"aid": str(acc_id)}).fetchone()
        
        if not row:
            print(f"Error: Account {account_id} not found.")
            return

        print(f"Migrating account {row.login} from {row.executor_version} to {to_version}...")

        # 2. Update version
        s.execute(text("UPDATE mt5_accounts SET executor_version = :ver, updated_at = now() WHERE id = :aid"),
                  {"aid": str(acc_id), "ver": to_version})
        
        # 3. If moving back to V1, ensure we cleanup V2 flags/mappings if desired
        # For safety, we keep them but the V2 agent will ignore the account due to routing version filter.
        
        print("Migration successful.")
        log.info("account migrated", extra={"account_id": account_id, "to_version": to_version})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate account between V1 and V2 executors.")
    parser.add_argument("--account_id", required=True, help="UUID of the account")
    parser.add_argument("--to", required=True, choices=['v1', 'v2'], help="Target version")
    
    args = parser.parse_args()
    migrate(args.account_id, args.to)
