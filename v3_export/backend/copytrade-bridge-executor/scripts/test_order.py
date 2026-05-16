"""Publish a fake ExecutionOrder into Redis for manual testing.

Example:
    python scripts/test_order.py --login 123456 --symbol XAUUSD --type BUY --lot 0.01
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.redis_client import get_redis  # noqa: E402


@click.command()
@click.option("--login", required=True)
@click.option("--symbol", default="XAUUSD")
@click.option("--type", "order_type", type=click.Choice(["BUY", "SELL"]), default="BUY")
@click.option("--action", type=click.Choice(["OPEN", "CLOSE", "MODIFY"]), default="OPEN")
@click.option("--lot", type=float, default=0.01)
@click.option("--sl", type=float, default=None)
@click.option("--tp", type=float, default=None)
@click.option("--server", default=None)
@click.option("--password", default=None)
@click.option("--master-ticket", default=None)
def main(login, symbol, order_type, action, lot, sl, tp, server, password, master_ticket):
    eo = str(uuid.uuid4())
    payload = {
        "execution_order_id": eo,
        "client_login": login,
        "client_server": server,
        "client_password": password,
        "action": action,
        "symbol": symbol,
        "order_type": order_type,
        "lot": lot,
        "sl": sl,
        "tp": tp,
        "master_ticket": master_ticket or eo[:8],
    }
    queue = settings.test_queue or f"{settings.queue_prefix}:{login}"
    r = get_redis()
    r.rpush(queue, json.dumps(payload))
    click.echo(f"published to {queue}: execution_order_id={eo}")


if __name__ == "__main__":
    main()
