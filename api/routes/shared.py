import os
import time
from typing import Any, Dict, Tuple

from fastapi import HTTPException

from api.auth import is_admin_key, keys_required
from api.generation.novelty import record_served_doc
from api.generation.redis_diversity import record_site_descriptor
from api.settings import SETTINGS

try:
    import api.ratelimit as _rate_limiter
except Exception:
    _rate_limiter = None

try:
    from api.redis_ratelimit import RedisRateLimiter
except Exception:
    RedisRateLimiter = None


_redis_rate_limiter = None
if SETTINGS.storage.redis_url and RedisRateLimiter and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        _redis_rate_limiter = RedisRateLimiter(SETTINGS.storage.redis_url)
    except Exception:
        _redis_rate_limiter = None


def record_user_visible_serve(doc: Dict[str, Any]) -> None:
    try:
        record_served_doc(doc)
    except Exception:
        pass
    try:
        record_site_descriptor(doc, event="site_served")
    except Exception:
        pass


def safe_rate_check(bucket: str, key: str) -> Tuple[bool, int, int]:
    if is_admin_key(key):
        return True, 9999, int(time.time()) + 60
    if _redis_rate_limiter and not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            return _redis_rate_limiter.check_and_increment(bucket, key)
        except Exception:
            pass

    if _rate_limiter:
        if hasattr(_rate_limiter, "check_and_increment"):
            return _rate_limiter.check_and_increment(bucket, key)
        if hasattr(_rate_limiter, "try_acquire"):
            return _rate_limiter.try_acquire(bucket, key)
        if hasattr(_rate_limiter, "allow"):
            allowed = _rate_limiter.allow(bucket, key)
            remaining = getattr(_rate_limiter, "remaining", lambda *_: 0)(bucket, key)
            reset_ts = getattr(_rate_limiter, "reset_ts", lambda *_: int(time.time()) + 60)(bucket, key)
            return allowed, remaining, reset_ts

    return True, 9999, int(time.time()) + 60


def safe_rate_inspect(bucket: str, key: str) -> Tuple[bool, int, int]:
    if is_admin_key(key):
        return True, 9999, int(time.time()) + 60
    if _redis_rate_limiter and not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            return _redis_rate_limiter.inspect(bucket, key)
        except Exception:
            pass
    if _rate_limiter and hasattr(_rate_limiter, "inspect"):
        try:
            return _rate_limiter.inspect(bucket, key)
        except Exception:
            pass
    return True, 9999, int(time.time()) + 60


def rate_limit_headers(remaining: int, reset_ts: int, *, limited: bool = False) -> Dict[str, str]:
    headers = {
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_ts),
    }
    if limited:
        headers["Retry-After"] = str(max(0, reset_ts - int(time.time())))
    return headers


def rate_limit_payload(reset_ts: int) -> Dict[str, Any]:
    wait_seconds = max(0, reset_ts - int(time.time()))
    return {
        "error": "rate limit exceeded",
        "reset": reset_ts,
        "retry_after_seconds": wait_seconds,
        "message": f"Rate limit exceeded. Try again in {wait_seconds} seconds.",
    }


def require_admin_or_dev(api_key: str) -> None:
    if keys_required() and not is_admin_key(api_key):
        raise HTTPException(status_code=403, detail="Admin API key required")
