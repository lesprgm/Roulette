import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from api import dedupe


log = logging.getLogger(__name__)


PREFETCH_DIR = Path(os.getenv("PREFETCH_DIR", "cache/prefetch"))
BATCH_MIN = int(os.getenv("PREFETCH_BATCH_MIN", "5"))
BATCH_MAX = int(os.getenv("PREFETCH_BATCH_MAX", "20"))


def _ensure_dir() -> None:
    PREFETCH_DIR.mkdir(parents=True, exist_ok=True)


def _list_files() -> list[Path]:
    _ensure_dir()
    return sorted(PREFETCH_DIR.glob("*.json"))


def size() -> int:
    return len(_list_files())


def enqueue(doc: Dict[str, Any]) -> Optional[Path]:
    """Persist a generated page to the prefetch queue; returns path if enqueued.
    Skips if duplicate by signature.
    """
    sig = dedupe.signature_for_doc(doc)
    if not sig:
        log.warning("prefetch.enqueue: skipping doc without signature")
        return None
    current_size = size()
    if dedupe.has(sig) and current_size > 0:
        log.debug("prefetch.enqueue: skipping duplicate doc sig=%s queue_size=%d", sig[:12], current_size)
        return None
    if dedupe.has(sig):
        log.debug("prefetch.enqueue: forcing enqueue for duplicate sig=%s because queue empty", sig[:12])

    dedupe.add(sig)
    _ensure_dir()
    # Use nanosecond resolution to preserve enqueue order reliably under fast successive calls
    fname = f"{time.time_ns()}-{uuid.uuid4().hex[:8]}.json"
    path = PREFETCH_DIR / fname
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    log.info("prefetch.enqueue: stored doc sig=%s file=%s queue_size=%d", sig[:12], path.name, current_size + 1)
    return path


def dequeue() -> Optional[Dict[str, Any]]:
    files = _list_files()
    if not files:
        log.debug("prefetch.dequeue: queue empty")
        return None
    path = files[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        log.warning("prefetch.dequeue: failed to parse %s, dropping file", path.name, exc_info=True)
        try:
            path.unlink(missing_ok=True)  
        except Exception:
            pass
        return None
    try:
        path.unlink(missing_ok=True)  
    except Exception:
        pass
    log.info("prefetch.dequeue: served file=%s remaining=%d", path.name, len(files) - 1)
    return data


def clamp_batch(n: int) -> int:
    if n < BATCH_MIN:
        return BATCH_MIN
    if n > BATCH_MAX:
        return BATCH_MAX
    return n
