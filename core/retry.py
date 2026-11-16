"""Exponential-backoff retry decorator for async functions."""
import asyncio
from functools import wraps


def retry(max_attempts=3, delay=2.0, backoff=2.0,
          exceptions=(Exception,), notifier=None, context=""):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        if notifier:
                            notifier.warn(
                                f"{context or func.__name__} attempt {attempt} failed: "
                                f"{type(e).__name__} — retrying in {wait:.1f}s"
                            )
                        await asyncio.sleep(wait)
                        wait *= backoff
            raise last_exc
        return wrapper
    return decorator
