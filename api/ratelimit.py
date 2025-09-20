import time
from collections import deque
from typing import Deque, Dict

# 15 requests per 60 seconds per key.
WINDOW_SECONDS = 60
MAX_REQUESTS = 15

_buckets: Dict[str, Deque[float]] = {}


def allow(key: str) -> bool:
    """
    Return True if this request is allowed for the given key, else False.
    Uses a simple sliding time-window stored in memory.
    """
    now = time.time()
    q = _buckets.setdefault(key, deque())

    # Drop timestamps that are older than the window.
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()

    if len(q) >= MAX_REQUESTS:
        return False

    q.append(now)
    return True


def _reset():
    """
    TEST HELPER ONLY: clears all buckets so tests can start from a clean state.
    """
    _buckets.clear()
