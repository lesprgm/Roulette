from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

try:  
    import redis  
except Exception:  
    redis = None  

_LOCK = threading.Lock()
_COUNTER_FILE = Path(os.getenv("COUNTER_FILE", "cache/counter.json"))

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_REDIS_COUNTER_KEY = os.getenv("REDIS_COUNTER_KEY", "ndw:metrics:total")
_REDIS_TIMEOUT = float(os.getenv("REDIS_COUNTER_TIMEOUT", "0.35") or 0.35)

_REDIS_CLIENT: Optional["redis.Redis[str]"] = None  # type: ignore[name-defined]
if redis and _REDIS_URL:
    try:
        _REDIS_CLIENT = redis.from_url(  
            _REDIS_URL,
            decode_responses=True,
            socket_timeout=_REDIS_TIMEOUT,
            socket_connect_timeout=_REDIS_TIMEOUT,
        )
    except Exception as exc:  
        log.warning("counter: failed to initialize Redis client: %s", exc)
        _REDIS_CLIENT = None


def _ensure_dir() -> None:
    _COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read() -> Dict[str, int]:
    _ensure_dir()
    if not _COUNTER_FILE.exists():
        return {"total": 0}
    try:
        data = json.loads(_COUNTER_FILE.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            return {"total": 0}
        total = int(data.get("total", 0))
        return {"total": max(0, total)}
    except Exception:
        return {"total": 0}


def _write(state: Dict[str, int]) -> None:
    _ensure_dir()
    tmp = _COUNTER_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    tmp.replace(_COUNTER_FILE)


def _file_get_total() -> int:
    with _LOCK:
        return _read()["total"]


def _file_set_total(value: int) -> None:
    with _LOCK:
        _write({"total": max(0, int(value))})


def _file_increment(n: int) -> int:
    if n <= 0:
        return _file_get_total()
    with _LOCK:
        state = _read()
        state["total"] = int(state.get("total", 0)) + int(n)
        _write(state)
        return state["total"]


def _redis_get_total() -> Optional[int]:
    if not _REDIS_CLIENT:
        return None
    try:
        raw = _REDIS_CLIENT.get(_REDIS_COUNTER_KEY)
        if raw is None:
            baseline = _file_get_total()
            if baseline > 0:
                try:
                    _REDIS_CLIENT.setnx(_REDIS_COUNTER_KEY, baseline)
                except Exception:
                    pass
            return baseline
        total = max(0, int(raw))
        _file_set_total(total)
        return total
    except Exception as exc:
        log.warning("counter: Redis get failed, falling back to file: %s", exc)
        return None


def _redis_increment(n: int) -> Optional[int]:
    if not _REDIS_CLIENT:
        return None
    try:
        if n <= 0:
            current = _REDIS_CLIENT.get(_REDIS_COUNTER_KEY)
            total = max(0, int(current)) if current is not None else 0
            _file_set_total(total)
            return total
        if not _REDIS_CLIENT.exists(_REDIS_COUNTER_KEY):
            baseline = _file_get_total()
            if baseline > 0:
                try:
                    _REDIS_CLIENT.set(_REDIS_COUNTER_KEY, baseline)
                except Exception:
                    pass
        total = _REDIS_CLIENT.incrby(_REDIS_COUNTER_KEY, int(n))
        total = max(0, int(total))
        _file_set_total(total)
        return total
    except Exception as exc:
        log.warning("counter: Redis increment failed, falling back to file: %s", exc)
        return None


def get_total() -> int:
    total = _redis_get_total()
    if total is not None:
        return total
    return _file_get_total()


def increment(n: int = 1) -> int:
    total = _redis_increment(n)
    if total is not None:
        return total
    return _file_increment(n)
