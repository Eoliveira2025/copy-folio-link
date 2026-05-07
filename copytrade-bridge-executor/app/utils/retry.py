"""Retry helpers."""
from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


def redis_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type(Exception),
    )
