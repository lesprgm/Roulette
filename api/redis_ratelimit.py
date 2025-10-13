import os
import time
from typing import Optional, Tuple

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis is an optional dependency in some envs
    redis = None  # type: ignore

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WINDOW_SECONDS = int(os.getenv("RATE_WINDOW_SECONDS", "60"))
MAX_REQUESTS = int(os.getenv("RATE_MAX_REQUESTS", "5"))


class RedisRateLimiter:
    """
    Fixed-window Redis rate limiter that mirrors the in-process API used by api.ratelimit.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        window_seconds: Optional[int] = None,
        max_requests: Optional[int] = None,
    ) -> None:
        if redis is None:
            raise RuntimeError("redis package is not installed")

        self.redis_url = (redis_url or REDIS_URL).strip() or REDIS_URL
        self.window_seconds = int(window_seconds or WINDOW_SECONDS)
        self.max_requests = int(max_requests or MAX_REQUESTS)
        # Connection is lazy — this does not hit the network until first command.
        self._client = redis.from_url(self.redis_url, decode_responses=True)

    def _bucket_key(self, prefix: str, key: str, now: int) -> str:
        bucket = (prefix or "default").strip() or "default"
        user_key = (key or "anon").strip() or "anon"
        window_start = now - (now % self.window_seconds)
        return f"rl:{bucket}:{user_key}:{window_start}"

    def check_and_increment(self, prefix: str, key: str, now: Optional[int] = None) -> Tuple[bool, int, int]:
        """
        Returns (allowed, remaining, reset_ts) for the provided bucket/key.
        """
        current_ts = now or int(time.time())
        bucket_key = self._bucket_key(prefix, key, current_ts)
        pipe = self._client.pipeline()
        pipe.incr(bucket_key, 1)
        pipe.expire(bucket_key, self.window_seconds)
        count, _ = pipe.execute()
        used = int(count)
        remaining = max(0, self.max_requests - used)
        reset_ts = current_ts - (current_ts % self.window_seconds) + self.window_seconds
        return (used <= self.max_requests, remaining, reset_ts)


_default_limiter: Optional[RedisRateLimiter] = None


def _get_default_limiter() -> RedisRateLimiter:
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RedisRateLimiter()
    return _default_limiter


def check_and_increment(prefix: str, key: str, now: Optional[int] = None) -> Tuple[bool, int, int]:
    """
    Backwards-compatible module-level helper retained for direct imports.
    """
    limiter = _get_default_limiter()
    return limiter.check_and_increment(prefix, key, now)
