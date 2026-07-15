import time
from typing import Optional, Tuple

from api.settings import SETTINGS

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis is an optional dependency in some envs
    redis = None  # type: ignore

REDIS_URL = SETTINGS.storage.redis_url or "redis://localhost:6379/0"
WINDOW_SECONDS = SETTINGS.rate_limit.window_seconds
MAX_REQUESTS = SETTINGS.rate_limit.max_requests
PREMIUM_WINDOW_SECONDS = SETTINGS.rate_limit.premium_window_seconds
PREMIUM_DAILY_LIMIT = SETTINGS.rate_limit.premium_daily_limit


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

    def _bucket_limits(self, prefix: str) -> Tuple[int, int]:
        bucket = (prefix or "default").strip().lower() or "default"
        if bucket == "premium":
            return max(1, PREMIUM_DAILY_LIMIT), max(60, PREMIUM_WINDOW_SECONDS)
        return max(1, self.max_requests), max(60, self.window_seconds)

    def _bucket_key(self, prefix: str, key: str, now: int) -> str:
        bucket = (prefix or "default").strip() or "default"
        user_key = (key or "anon").strip() or "anon"
        _max_requests, window_seconds = self._bucket_limits(prefix)
        window_start = now - (now % window_seconds)
        return f"rl:{bucket}:{user_key}:{window_start}"

    def check_and_increment(self, prefix: str, key: str, now: Optional[int] = None) -> Tuple[bool, int, int]:
        """
        Returns (allowed, remaining, reset_ts) for the provided bucket/key.
        """
        current_ts = now or int(time.time())
        max_requests, window_seconds = self._bucket_limits(prefix)
        bucket_key = self._bucket_key(prefix, key, current_ts)
        pipe = self._client.pipeline()
        pipe.incr(bucket_key, 1)
        pipe.expire(bucket_key, window_seconds)
        count, _ = pipe.execute()
        used = int(count)
        remaining = max(0, max_requests - used)
        reset_ts = current_ts - (current_ts % window_seconds) + window_seconds
        return (used <= max_requests, remaining, reset_ts)

    def inspect(self, prefix: str, key: str, now: Optional[int] = None) -> Tuple[bool, int, int]:
        current_ts = now or int(time.time())
        max_requests, window_seconds = self._bucket_limits(prefix)
        bucket_key = self._bucket_key(prefix, key, current_ts)
        raw = self._client.get(bucket_key)
        used = int(raw or 0)
        remaining = max(0, max_requests - used)
        reset_ts = current_ts - (current_ts % window_seconds) + window_seconds
        return (used < max_requests, remaining, reset_ts)
