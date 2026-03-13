"""Rate limiting middleware using Redis for distributed tracking."""

import time
import logging
from fastapi import Request, HTTPException
import redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.middleware.rate_limit")


class RateLimiter:
    def __init__(self):
        try:
            self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            self.redis = None
            logger.warning("Redis not available — rate limiting disabled")

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        if not self.redis:
            return True

        try:
            current = self.redis.get(key)
            if current is None:
                self.redis.setex(key, window_seconds, 1)
                return True

            if int(current) >= max_requests:
                return False

            self.redis.incr(key)
            return True
        except Exception:
            return True  # Fail open if Redis is down


rate_limiter = RateLimiter()


async def login_rate_limit(request: Request):
    """Dependency to rate-limit login attempts by IP."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:login:{client_ip}"

    if not rate_limiter.check_rate_limit(
        key,
        max_requests=settings.LOGIN_RATE_LIMIT,
        window_seconds=settings.LOGIN_RATE_WINDOW,
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again in a few minutes.",
        )
