from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from typing import Dict

_LOCK = threading.Lock()
_COUNTER_FILE = Path(os.getenv("COUNTER_FILE", "cache/counter.json"))


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


def get_total() -> int:
    with _LOCK:
        return _read()["total"]


def increment(n: int = 1) -> int:
    if n <= 0:
        return get_total()
    with _LOCK:
        state = _read()
        state["total"] = int(state.get("total", 0)) + int(n)
        _write(state)
        return state["total"]
