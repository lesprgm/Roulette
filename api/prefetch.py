import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from api import dedupe


PREFETCH_DIR = Path(os.getenv("PREFETCH_DIR", "cache/prefetch"))
BATCH_MIN = int(os.getenv("PREFETCH_BATCH_MIN", "5"))
BATCH_MAX = int(os.getenv("PREFETCH_BATCH_MAX", "10"))


def _ensure_dir() -> None:
    PREFETCH_DIR.mkdir(parents=True, exist_ok=True)


def _list_files() -> list[Path]:
    _ensure_dir()
    return sorted(PREFETCH_DIR.glob("*.json"))


def size() -> int:
    return len(_list_files())


def enqueue(doc: Dict[str, Any]) -> bool:
    """Persist a generated page to the prefetch queue; returns True if enqueued.
    Skips if duplicate by signature.
    """
    sig = dedupe.signature_for_doc(doc)
    if not sig:
        return False
    if dedupe.has(sig):
        return False
    # Record in dedupe and persist
    dedupe.add(sig)
    _ensure_dir()
    # Use nanosecond resolution to preserve enqueue order reliably under fast successive calls
    fname = f"{time.time_ns()}-{uuid.uuid4().hex[:8]}.json"
    path = PREFETCH_DIR / fname
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return True


def dequeue() -> Optional[Dict[str, Any]]:
    files = _list_files()
    if not files:
        return None
    path = files[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            path.unlink(missing_ok=True)  
        except Exception:
            pass
        return None
    try:
        path.unlink(missing_ok=True)  
    except Exception:
        pass
    return data


def clamp_batch(n: int) -> int:
    if n < BATCH_MIN:
        return BATCH_MIN
    if n > BATCH_MAX:
        return BATCH_MAX
    return n
