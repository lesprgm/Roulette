from __future__ import annotations
import os
import time
from typing import Dict, Tuple

WINDOW_SECONDS: int = int(os.getenv("RATE_WINDOW_SECONDS", "10800"))
MAX_REQUESTS: int = int(os.getenv("RATE_MAX_REQUESTS", "30"))

_store: Dict[Tuple[str, str], Dict[str, int]] = {}

def _now() -> int:
    return int(time.time())

def _bk(bucket: str, key: str) -> Tuple[str, str]:
    return (bucket or "default", key or "anon")

def _ensure_entry(bucket: str, key: str):
    k = _bk(bucket, key)
    now = _now()
    entry = _store.get(k)
    if entry is None or now >= entry["reset_ts"]:
        _store[k] = {"count": 0, "reset_ts": now + WINDOW_SECONDS}
    return _store[k]

def allow_request(bucket: str, key: str):
    """
    Core API used by some codebases.
    Returns (allowed: bool, remaining: int, reset_ts: int)
    """
    entry = _ensure_entry(bucket, key)
    if entry["count"] < MAX_REQUESTS:
        entry["count"] += 1
        remaining = max(0, MAX_REQUESTS - entry["count"])
        return True, remaining, entry["reset_ts"]
    # denied
    remaining = 0
    return False, remaining, entry["reset_ts"]

def check_and_increment(bucket: str, key: str):
    """
    Compatibility shim used by your main.py.
    Same return tuple as allow_request.
    """
    return allow_request(bucket, key)

def _reset():
    """Used by tests to clear state."""
    _store.clear()
