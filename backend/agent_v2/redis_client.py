"""Shared Redis client for V2.

Strict isolation: V2 uses DB /2 and prefixes EVERY key/channel with
`copytrade_v2:`. Helpers below add the prefix automatically so callers
never write `copytrade_v2:...` literals.

Channels:
  copytrade_v2:events:master:{master_id}    — master OPEN/CLOSE/MODIFY
  copytrade_v2:health:pool:{pool_id}        — heartbeat
  copytrade_v2:health:terminal:{terminal_id} — terminal alive
"""

from __future__ import annotations

import json
import threading
from typing import Any, Optional

from .config import get_v2_settings
from .utils.logger import get_logger

_log = get_logger("redis")
_client_lock = threading.Lock()
_client = None


def get_redis():
    """Lazy singleton — avoids pulling redis-py at import time in tests."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        try:
            import redis  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"redis-py not installed: {e}")
        s = get_v2_settings()
        _client = redis.Redis.from_url(
            s.REDIS_URL,
            decode_responses=True,
            socket_keepalive=s.REDIS_SOCKET_KEEPALIVE,
            socket_timeout=s.REDIS_SOCKET_TIMEOUT,
        )
        _log.info("redis client created", extra={"action": "redis_init",
                                                 "url": s.REDIS_URL})
        return _client


def k(suffix: str) -> str:
    """Prefix a key/channel name with the V2 namespace."""
    return f"{get_v2_settings().REDIS_PREFIX}{suffix}"


def publish(channel_suffix: str, payload: dict[str, Any]) -> int:
    return get_redis().publish(k(channel_suffix), json.dumps(payload))


def subscribe(channel_suffixes: list[str]):
    pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(*[k(c) for c in channel_suffixes])
    return pubsub


def set_json(key_suffix: str, value: dict[str, Any], ex: Optional[int] = None) -> None:
    get_redis().set(k(key_suffix), json.dumps(value), ex=ex)


def get_json(key_suffix: str) -> Optional[dict[str, Any]]:
    raw = get_redis().get(k(key_suffix))
    return json.loads(raw) if raw else None
