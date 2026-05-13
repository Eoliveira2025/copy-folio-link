"""Support Helper — CLI tools for operational troubleshooting."""

import os
import sys
import argparse
from pathlib import Path
from uuid import UUID
from ..config import get_v2_settings

def find_account_logs(account_id: str):
    settings = get_v2_settings()
    pool_dir = Path(settings.V2_POOL_DIR) / account_id
    
    if not pool_dir.exists():
        print(f"Error: Account folder not found: {pool_dir}")
        return

    print(f"--- Logs for Account {account_id} ---")
    log_paths = [
        pool_dir / "Logs",
        pool_dir / "MQL5" / "Logs"
    ]
    
    for lp in log_paths:
        if lp.exists():
            print(f"Location: {lp}")
            logs = sorted(lp.glob("*.log"), key=os.path.getmtime, reverse=True)
            for l in logs[:5]:
                print(f"  [{l.stat().st_mtime}] {l.name}")

def list_active_terminals():
    # This would need to talk to the running process via Redis or a socket
    # For now, we look at the filesystem PIDs if stored, or use tasklist
    print("Listing active MT5 processes with V2 tags...")
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'environ']):
            if 'terminal64.exe' in proc.info['name'].lower():
                env = proc.info.get('environ') or {}
                tid = env.get('V2_TERMINAL_ID')
                if tid:
                    print(f"PID: {proc.info['pid']} | Terminal: {tid} | Account: {env.get('V2_ACCOUNT_ID', 'N/A')}")
    except Exception as e:
        print(f"Error listing processes: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V2 Support Tools")
    subparsers = parser.add_subparsers(dest="command")
    
    logs_p = subparsers.add_parser("logs")
    logs_p.add_argument("account_id", help="UUID of the account")
    
    list_p = subparsers.add_parser("list")
    
    args = parser.parse_args()
    
    if args.command == "logs":
        find_account_logs(args.account_id)
    elif args.command == "list":
        list_active_terminals()
    else:
        parser.print_help()
