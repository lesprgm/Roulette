import os, time
import redis
from typing import Tuple

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WINDOW_SECONDS = int(os.getenv("RATE_WINDOW_SECONDS", "60"))
MAX_REQUESTS = int(os.getenv("RATE_MAX_REQUESTS", "15"))

_redis = redis.from_url(REDIS_URL, decode_responses=True)

def _bucket_key(prefix: str, key: str, now: int) -> str:
    # Discrete window (fixed window): one key per rolling window start
    window_start = now - (now % WINDOW_SECONDS)
    return f"rl:{prefix}:{key}:{window_start}"

def check_and_increment(prefix: str, key: str, now: int | None = None) -> Tuple[bool, int, int]:
    """
    Returns (allowed, remaining, reset_ts).
    Fixed-window counter in Redis:
      - INCR the window key
      - EXPIRE the key to WINDOW_SECONDS
    """
    now = now or int(time.time())
    k = _bucket_key(prefix, key, now)
    pipe = _redis.pipeline()
    pipe.incr(k, 1)
    pipe.expire(k, WINDOW_SECONDS)
    count, _ = pipe.execute()
    remaining = max(0, MAX_REQUESTS - int(count))
    reset_ts = now - (now % WINDOW_SECONDS) + WINDOW_SECONDS
    return (count <= MAX_REQUESTS, remaining, reset_ts)
