"""
Copy Engine integration service (Redis-only, no MT5 dependency).

Publishes commands to Redis for the engine to:
- Spawn/tear down MT5 terminal connections
- Subscribe/unsubscribe client accounts to strategies
- Force-check connection health
"""

import json
import logging
from typing import Optional
import redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.services.copy_engine")

# Redis channels
CHANNEL_TERMINAL_CMD = "copytrade:terminal:commands"
CHANNEL_ENGINE_CMD = "copytrade:engine:commands"


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def dispatch_connect_terminal(
    account_id: str,
    login: int,
    encrypted_password: str,
    server: str,
    strategy_level: Optional[str] = None,
    master_login: Optional[int] = None,
):
    """Tell the MT5 Terminal Manager to spawn a terminal for this account."""
    r = _get_redis()
    command = {
        "action": "spawn",
        "account_id": account_id,
        "login": login,
        "encrypted_password": encrypted_password,
        "server": server,
        "strategy_level": strategy_level,
        "master_login": master_login,
    }
    r.publish(CHANNEL_TERMINAL_CMD, json.dumps(command))
    r.lpush("copytrade:terminal:queue", json.dumps(command))
    logger.info(f"Dispatched terminal spawn for account {login}")


def dispatch_disconnect_terminal(account_id: str, login: int):
    """Tell the MT5 Terminal Manager to tear down a terminal."""
    r = _get_redis()
    command = {
        "action": "stop",
        "account_id": account_id,
        "login": login,
    }
    r.publish(CHANNEL_TERMINAL_CMD, json.dumps(command))
    r.lpush("copytrade:terminal:queue", json.dumps(command))
    logger.info(f"Dispatched terminal stop for account {login}")


def dispatch_subscribe_strategy(
    account_id: str,
    client_login: int,
    strategy_level: str,
    master_login: int,
    risk_multiplier: float = 1.0,
):
    """Subscribe a client account to a strategy's master account."""
    r = _get_redis()
    command = {
        "action": "subscribe",
        "account_id": account_id,
        "client_login": client_login,
        "strategy_level": strategy_level,
        "master_login": master_login,
        "risk_multiplier": risk_multiplier,
    }
    r.publish(CHANNEL_ENGINE_CMD, json.dumps(command))
    r.lpush("copytrade:engine:queue", json.dumps(command))
    logger.info(f"Dispatched strategy subscribe: account {client_login} → master {master_login}")


def dispatch_unsubscribe_strategy(account_id: str, client_login: int):
    """Unsubscribe a client account from copy trading."""
    r = _get_redis()
    command = {
        "action": "unsubscribe",
        "account_id": account_id,
        "client_login": client_login,
    }
    r.publish(CHANNEL_ENGINE_CMD, json.dumps(command))
    r.lpush("copytrade:engine:queue", json.dumps(command))
    logger.info(f"Dispatched strategy unsubscribe for account {client_login}")


def dispatch_reconnect_terminal(account_id: str, login: int):
    """Force reconnect a terminal."""
    r = _get_redis()
    command = {
        "action": "reconnect",
        "account_id": account_id,
        "login": login,
    }
    r.publish(CHANNEL_TERMINAL_CMD, json.dumps(command))
    logger.info(f"Dispatched terminal reconnect for account {login}")


def dispatch_block_account(account_id: str, login: int):
    """Block an account — stops copy trading and disconnects terminal."""
    dispatch_unsubscribe_strategy(account_id, login)
    dispatch_disconnect_terminal(account_id, login)
    logger.info(f"Dispatched block for account {login}")


def dispatch_unblock_account(
    account_id: str,
    login: int,
    encrypted_password: str,
    server: str,
    strategy_level: Optional[str] = None,
    master_login: Optional[int] = None,
    risk_multiplier: float = 1.0,
):
    """Unblock an account — reconnects terminal and re-subscribes to strategy."""
    dispatch_connect_terminal(account_id, login, encrypted_password, server, strategy_level, master_login)
    if strategy_level and master_login:
        dispatch_subscribe_strategy(account_id, login, strategy_level, master_login, risk_multiplier)
    logger.info(f"Dispatched unblock for account {login}")
