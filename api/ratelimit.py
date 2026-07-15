from __future__ import annotations
import time
from typing import Dict, Tuple

from api.settings import SETTINGS

WINDOW_SECONDS = SETTINGS.rate_limit.window_seconds
MAX_REQUESTS = SETTINGS.rate_limit.max_requests
PREMIUM_WINDOW_SECONDS = SETTINGS.rate_limit.premium_window_seconds
PREMIUM_DAILY_LIMIT = SETTINGS.rate_limit.premium_daily_limit

_store: Dict[Tuple[str, str], Dict[str, int]] = {}

def _now() -> int:
    return int(time.time())

def _bk(bucket: str, key: str) -> Tuple[str, str]:
    return (bucket or "default", key or "anon")

def _bucket_limits(bucket: str) -> Tuple[int, int]:
    bucket_name = (bucket or "default").strip().lower()
    if bucket_name == "premium":
        return max(1, PREMIUM_DAILY_LIMIT), max(60, PREMIUM_WINDOW_SECONDS)
    return max(1, MAX_REQUESTS), max(60, WINDOW_SECONDS)

def _ensure_entry(bucket: str, key: str):
    k = _bk(bucket, key)
    now = _now()
    entry = _store.get(k)
    _max_requests, window_seconds = _bucket_limits(bucket)
    if entry is None or now >= entry["reset_ts"]:
        _store[k] = {"count": 0, "reset_ts": now + window_seconds}
    return _store[k]


def inspect(bucket: str, key: str):
    entry = _ensure_entry(bucket, key)
    max_requests, _window_seconds = _bucket_limits(bucket)
    allowed = entry["count"] < max_requests
    remaining = max(0, max_requests - entry["count"])
    return allowed, remaining, entry["reset_ts"]


def allow_request(bucket: str, key: str):
    """
    Core API used by some codebases.
    Returns (allowed: bool, remaining: int, reset_ts: int)
    """
    entry = _ensure_entry(bucket, key)
    max_requests, _window_seconds = _bucket_limits(bucket)
    if entry["count"] < max_requests:
        entry["count"] += 1
        remaining = max(0, max_requests - entry["count"])
        return True, remaining, entry["reset_ts"]
    # denied
    remaining = 0
    return False, remaining, entry["reset_ts"]

def check_and_increment(bucket: str, key: str):
    """
    Compatibility shim used by the shared request policy.
    Same return tuple as allow_request.
    """
    return allow_request(bucket, key)

def _reset():
    """Used by tests to clear state."""
    _store.clear()
