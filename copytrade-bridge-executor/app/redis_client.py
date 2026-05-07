"""Redis connection helpers."""
from __future__ import annotations

import redis

from app.config import settings

_pool: redis.ConnectionPool | None = None


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url, decode_responses=True, socket_keepalive=True
        )
    return redis.Redis(connection_pool=_pool)


def ping() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
