from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

try:
    import redis  # type: ignore
except Exception:
    redis = None  # type: ignore

_LOCK = threading.Lock()
_CREDITS_FILE = Path(os.getenv("PREMIUM_CREDITS_FILE", "cache/premium_credits.json"))
_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_REDIS_TIMEOUT = float(os.getenv("REDIS_COUNTER_TIMEOUT", "0.35") or 0.35)
_REDIS_PREFIX = os.getenv("PREMIUM_CREDITS_REDIS_PREFIX", "ndw:premium:credit:")

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
        log.warning("premium_credits: failed to initialize Redis client: %s", exc)
        _REDIS_CLIENT = None


def _ensure_dir() -> None:
    _CREDITS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read() -> Dict[str, int]:
    _ensure_dir()
    if not _CREDITS_FILE.exists():
        return {}
    try:
        data = json.loads(_CREDITS_FILE.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            return {}
        out: Dict[str, int] = {}
        for key, value in data.items():
            try:
                count = int(value)
            except Exception:
                continue
            if count > 0:
                out[str(key)] = count
        return out
    except Exception:
        return {}


def _write(state: Dict[str, int]) -> None:
    _ensure_dir()
    tmp = _CREDITS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    tmp.replace(_CREDITS_FILE)


def _file_peek(key: str) -> int:
    with _LOCK:
        return max(0, int(_read().get(key, 0)))


def _file_grant(key: str, amount: int = 1) -> int:
    with _LOCK:
        state = _read()
        state[key] = max(0, int(state.get(key, 0))) + max(0, int(amount))
        _write(state)
        return int(state[key])


def _file_consume(key: str) -> bool:
    with _LOCK:
        state = _read()
        current = max(0, int(state.get(key, 0)))
        if current <= 0:
            return False
        next_value = current - 1
        if next_value > 0:
            state[key] = next_value
        else:
            state.pop(key, None)
        _write(state)
        return True


def _redis_key(key: str) -> str:
    return f"{_REDIS_PREFIX}{key or 'anon'}"


def peek(key: str) -> int:
    if _REDIS_CLIENT:
        try:
            raw = _REDIS_CLIENT.get(_redis_key(key))
            return max(0, int(raw or 0))
        except Exception as exc:
            log.warning("premium_credits: Redis peek failed, falling back to file: %s", exc)
    return _file_peek(key)


def grant(key: str, amount: int = 1) -> int:
    amount = max(0, int(amount))
    if amount <= 0:
        return peek(key)
    if _REDIS_CLIENT:
        try:
            total = int(_REDIS_CLIENT.incrby(_redis_key(key), amount))
            return max(0, total)
        except Exception as exc:
            log.warning("premium_credits: Redis grant failed, falling back to file: %s", exc)
    return _file_grant(key, amount)


def consume(key: str) -> bool:
    if _REDIS_CLIENT:
        try:
            redis_key = _redis_key(key)
            while True:
                pipe = _REDIS_CLIENT.pipeline()
                try:
                    pipe.watch(redis_key)
                    current = int(pipe.get(redis_key) or 0)
                    if current <= 0:
                        pipe.unwatch()
                        return False
                    pipe.multi()
                    if current == 1:
                        pipe.delete(redis_key)
                    else:
                        pipe.decrby(redis_key, 1)
                    pipe.execute()
                    return True
                except Exception:
                    try:
                        pipe.reset()
                    except Exception:
                        pass
                    raise
        except Exception as exc:
            log.warning("premium_credits: Redis consume failed, falling back to file: %s", exc)
    return _file_consume(key)
