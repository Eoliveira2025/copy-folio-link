"""
V2 CLI Operator Tool.
Commands for daily management of the Institutional V2 Executor.
"""

import os
import sys
import click
import json
from tabulate import tabulate

# Add root to sys.path
sys.path.append(os.getcwd())

from backend.agent_v2.config import get_v2_settings
from backend.agent_v2.db import session_scope
from backend.agent_v2.redis_client import get_redis, k, get_json

@click.group()
def cli():
    """CopyTrade Pro V2 Institutional Operator CLI."""
    pass

@cli.command()
def list_accounts():
    """List all accounts currently handled by V2 on this VPS."""
    settings = get_v2_settings()
    r = get_redis()
    
    # In V2, we track active accounts in Redis keys like 'copytrade_v2:status:account:{id}'
    # For now, let's list from the database if they are assigned to this VPS
    with session_scope() as session:
        # Assuming there's a column or logic to filter by VPS_ID or V2 Routing
        # This is a placeholder for the real query logic
        click.echo(f"Listing accounts for VPS: {settings.V2_VPS_ID}")
        # dummy data for demonstration
        table = [
            ["Account ID", "Login", "Status", "Latency", "Pool ID"],
            ["uuid-1", "123456", "ACTIVE", "15ms", "pool_01"],
            ["uuid-2", "789012", "CONNECTED", "12ms", "pool_01"],
        ]
        click.echo(tabulate(table, headers="firstrow", tablefmt="grid"))

@cli.command()
@click.argument('account_id')
def reconnect(account_id):
    """Force reconnection of a specific account."""
    click.echo(f"Signaling reconnection for account {account_id}...")
    r = get_redis()
    # Publish reconnect event
    r.publish(k("commands:account"), json.dumps({
        "account_id": account_id,
        "action": "RECONNECT"
    }))
    click.echo("Signal sent.")

@cli.command()
@click.argument('pool_id')
def recycle_terminal(pool_id):
    """Recycle an MT5 terminal instance (Restart)."""
    click.echo(f"Recycling terminal for pool {pool_id}...")
    r = get_redis()
    r.publish(k("commands:pool"), json.dumps({
        "pool_id": pool_id,
        "action": "RECYCLE"
    }))
    click.echo("Signal sent.")

@cli.command()
@click.argument('pool_id')
def open_terminal(pool_id):
    """Open the GUI of a specific background terminal (Debug mode)."""
    # This usually involves moving terminal.ini to show GUI and restarting
    click.echo(f"Requesting GUI for terminal {pool_id}...")
    # Placeholder for logic
    
@cli.command()
@click.option('--lines', default=50, help='Number of lines to show')
def logs(lines):
    """Show recent logs from the V2 Executor."""
    settings = get_v2_settings()
    log_file = os.path.join(settings.V2_LOGS_DIR, "master_monitor.log")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            content = f.readlines()
            for line in content[-lines:]:
                click.echo(line.strip())
    else:
        click.echo(f"Log file not found at {log_file}")

if __name__ == "__main__":
    cli()
