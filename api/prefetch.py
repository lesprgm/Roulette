"""Prefetch queue for generated content.

Prefers Redis when REDIS_URL is configured, falling back to a file-based
FIFO queue for local/dev compatibility.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from api import dedupe

log = logging.getLogger(__name__)

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency in some envs
    redis = None  # type: ignore

# Legacy file-based storage (fallback)
PREFETCH_DIR = Path(os.getenv("PREFETCH_DIR", "cache/prefetch"))
PREMIUM_PREFETCH_DIR = Path(os.getenv("PREMIUM_PREFETCH_DIR", "cache/premium_prefetch"))
BATCH_MIN = int(os.getenv("PREFETCH_BATCH_MIN", "5"))
BATCH_MAX = int(os.getenv("PREFETCH_BATCH_MAX", "20"))
DROP_TEST_FIXTURE_DOCS = os.getenv("PREFETCH_DROP_TEST_FIXTURES", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_REDIS_QUEUE_KEY = os.getenv("PREFETCH_REDIS_QUEUE_KEY", "ndw:prefetch:queue")
_REDIS_DOC_PREFIX = os.getenv("PREFETCH_REDIS_DOC_PREFIX", "ndw:prefetch:doc:")
_PREMIUM_REDIS_QUEUE_KEY = os.getenv("PREMIUM_REDIS_QUEUE_KEY", "ndw:premium:queue")
_PREMIUM_REDIS_DOC_PREFIX = os.getenv("PREMIUM_REDIS_DOC_PREFIX", "ndw:premium:doc:")
_REDIS_CLIENT = None
_REDIS_DISABLED_REASON = ""
if redis and _REDIS_URL and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        _REDIS_CLIENT = redis.from_url(_REDIS_URL, decode_responses=True)
        if os.getenv("PREFETCH_REDIS_HEALTHCHECK", "1").strip().lower() not in {"0", "false", "no", "off"}:
            _REDIS_CLIENT.ping()
    except Exception:
        _REDIS_CLIENT = None
        _REDIS_DISABLED_REASON = "initialization_failed"
        log.warning("prefetch.redis: failed to initialize redis client", exc_info=True)

TOKEN_TTL_SECONDS = int(os.getenv("PREFETCH_TOKEN_TTL_SECONDS", "1800"))
PREMIUM_TOKEN_TTL_SECONDS = int(os.getenv("PREMIUM_TOKEN_TTL_SECONDS", "900"))
_token_secret_env = os.getenv("PREFETCH_TOKEN_SECRET", "").strip()
if _token_secret_env:
    _TOKEN_SECRET = _token_secret_env.encode("utf-8")
else:
    _TOKEN_SECRET = os.urandom(32)
    log.warning("prefetch.token: PREFETCH_TOKEN_SECRET not set; tokens reset on restart")


def _lane_name(lane: Optional[str]) -> str:
    return "premium" if str(lane or "fast").strip().lower() == "premium" else "fast"


def _lane_dir(lane: Optional[str] = None) -> Path:
    return PREMIUM_PREFETCH_DIR if _lane_name(lane) == "premium" else PREFETCH_DIR


def _lane_queue_key(lane: Optional[str] = None) -> str:
    return _PREMIUM_REDIS_QUEUE_KEY if _lane_name(lane) == "premium" else _REDIS_QUEUE_KEY


def _lane_doc_prefix(lane: Optional[str] = None) -> str:
    return _PREMIUM_REDIS_DOC_PREFIX if _lane_name(lane) == "premium" else _REDIS_DOC_PREFIX


def _lane_token_ttl(lane: Optional[str] = None) -> int:
    return PREMIUM_TOKEN_TTL_SECONDS if _lane_name(lane) == "premium" else TOKEN_TTL_SECONDS


def _ensure_dir(lane: Optional[str] = None) -> None:
    _lane_dir(lane).mkdir(parents=True, exist_ok=True)


def _list_files(lane: Optional[str] = None) -> list[Path]:
    target = _lane_dir(lane)
    _ensure_dir(lane)
    return sorted(target.glob("*.json"))


def _redis_enabled() -> bool:
    return _REDIS_CLIENT is not None and not _REDIS_DISABLED_REASON


def _disable_redis(reason: str) -> None:
    global _REDIS_CLIENT, _REDIS_DISABLED_REASON
    if _REDIS_DISABLED_REASON:
        return
    _REDIS_DISABLED_REASON = reason or "operation_failed"
    _REDIS_CLIENT = None
    log.warning("prefetch.redis: disabled for this process; using file queue reason=%s", _REDIS_DISABLED_REASON)


def _redis_doc_key(doc_id: str, lane: Optional[str] = None) -> str:
    return f"{_lane_doc_prefix(lane)}{doc_id}"

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)


def _clean_title(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text or "Untitled"


def _extract_title(doc: Dict[str, Any]) -> str:
    title = doc.get("title")
    if isinstance(title, str) and title.strip():
        return _clean_title(title)
    if doc.get("kind") == "full_page_html":
        html = doc.get("html")
        if isinstance(html, str):
            match = _TITLE_RE.search(html)
            if match:
                return _clean_title(match.group(1))
            match = _H1_RE.search(html)
            if match:
                return _clean_title(match.group(1))
    comps = doc.get("components")
    if isinstance(comps, list):
        for comp in comps:
            if not isinstance(comp, dict):
                continue
            props = comp.get("props") or {}
            if isinstance(props, dict):
                t = props.get("title")
                if isinstance(t, str) and t.strip():
                    return _clean_title(t)
                html = props.get("html")
                if isinstance(html, str):
                    match = _TITLE_RE.search(html) or _H1_RE.search(html)
                    if match:
                        return _clean_title(match.group(1))
    return "Untitled"


def _extract_field(doc: Dict[str, Any], key: str, fallback: str) -> str:
    value = doc.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _preview_from_doc(doc: Dict[str, Any], token: str, created_at: float) -> Dict[str, Any]:
    return {
        "id": token,
        "title": _extract_title(doc),
        "category": _extract_field(doc, "category", "unknown"),
        "vibe": _extract_field(doc, "vibe", "unknown"),
        "created_at": float(created_at),
    }


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> Optional[bytes]:
    try:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)
    except Exception:
        return None


def _sign_payload(payload: str) -> str:
    sig = hmac.new(_TOKEN_SECRET, payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def _token_kind_for_lane(kind: str, lane: Optional[str] = None) -> str:
    lane_name = _lane_name(lane)
    if lane_name == "premium":
        return f"premium-{kind}"
    return kind


def _parse_token_kind(kind: str) -> Tuple[Optional[str], str]:
    if kind == "redis":
        return "fast", "redis"
    if kind == "file":
        return "fast", "file"
    if kind == "premium-redis":
        return "premium", "redis"
    if kind == "premium-file":
        return "premium", "file"
    return None, kind


def _make_token(kind: str, ident: str, exp: int, lane: Optional[str] = None) -> str:
    kind = _token_kind_for_lane(kind, lane)
    payload = f"{kind}:{ident}:{exp}"
    encoded = _b64url_encode(payload.encode("utf-8"))
    return f"{encoded}.{_sign_payload(payload)}"


def _parse_token(token: str) -> Optional[Tuple[str, str, int]]:
    if not token or "." not in token:
        return None
    encoded, sig = token.split(".", 1)
    payload_bytes = _b64url_decode(encoded)
    if not payload_bytes:
        return None
    payload = payload_bytes.decode("utf-8", errors="ignore")
    expected = _sign_payload(payload)
    if not hmac.compare_digest(expected, sig):
        return None
    parts = payload.split(":", 2)
    if len(parts) != 3:
        return None
    kind, ident, exp_raw = parts
    try:
        exp = int(exp_raw)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    return kind, ident, exp


def _read_doc(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_test_fixture_doc(doc: Dict[str, Any]) -> bool:
    """Protect local file fallback from serving stale unit-test queue artifacts."""
    if not DROP_TEST_FIXTURE_DOCS:
        return False
    category = str(doc.get("category") or "").strip().lower()
    vibe = str(doc.get("vibe") or "").strip().lower()
    if category in {"unit-test", "test", "testing"}:
        return True
    if vibe in {"unit-test", "test", "testing"}:
        return True
    return False


def _drop_queue_file(path: Path, reason: str) -> None:
    log.warning("prefetch.file: dropping %s reason=%s", path.name, reason)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        log.warning("prefetch.file: failed to drop %s", path.name, exc_info=True)


def _read_file_queue_doc(path: Path) -> Optional[Dict[str, Any]]:
    doc = _read_doc(path)
    if not isinstance(doc, dict):
        _drop_queue_file(path, "invalid_json")
        return None
    if _is_test_fixture_doc(doc):
        _drop_queue_file(path, "test_fixture")
        return None
    return doc


def _strip_prefetch_meta(doc: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(doc, dict) and "_prefetch" in doc:
        doc.pop("_prefetch", None)
    if isinstance(doc, dict) and "created_at" in doc:
        doc.pop("created_at", None)
    return doc


def size(lane: Optional[str] = None) -> int:
    """Get the current queue size."""
    lane_name = _lane_name(lane)
    if _redis_enabled():
        try:
            return int(_REDIS_CLIENT.llen(_lane_queue_key(lane_name)))
        except Exception:
            log.warning("prefetch.redis: failed to read queue size", exc_info=True)
            _disable_redis("size_failed")
    return len(_list_files(lane_name))


def peek(limit: int = 20, lane: Optional[str] = None) -> list[Dict[str, Any]]:
    """Peek at the next unserved items in the queue without removing them."""
    lane_name = _lane_name(lane)
    now = int(time.time())
    ttl = max(60, _lane_token_ttl(lane_name))
    exp = ((now // ttl) + 1) * ttl
    previews: list[Dict[str, Any]] = []
    limit_count = max(0, int(limit or 0))
    if _redis_enabled():
        try:
            ids = _REDIS_CLIENT.lrange(_lane_queue_key(lane_name), 0, max(0, limit_count - 1))
            for doc_id in ids:
                raw = _REDIS_CLIENT.get(_redis_doc_key(doc_id, lane_name))
                if not raw:
                    _REDIS_CLIENT.lrem(_lane_queue_key(lane_name), 0, doc_id)
                    continue
                try:
                    doc = json.loads(raw)
                except Exception:
                    _REDIS_CLIENT.delete(_redis_doc_key(doc_id, lane_name))
                    _REDIS_CLIENT.lrem(_lane_queue_key(lane_name), 0, doc_id)
                    continue
                if not isinstance(doc, dict):
                    _REDIS_CLIENT.delete(_redis_doc_key(doc_id, lane_name))
                    _REDIS_CLIENT.lrem(_lane_queue_key(lane_name), 0, doc_id)
                    continue
                created_at = float(doc.get("created_at") or time.time())
                token = _make_token("redis", doc_id, exp, lane_name)
                previews.append(_preview_from_doc(doc, token, created_at))
            return previews
        except Exception:
            log.warning("prefetch.redis: peek failed; falling back to file queue", exc_info=True)
            _disable_redis("peek_failed")
    files = _list_files(lane_name)
    records: list[Tuple[float, Path, Dict[str, Any]]] = []
    for path in files:
        doc = _read_file_queue_doc(path)
        if not doc:
            continue
        try:
            created_at = doc.get("created_at") or path.stat().st_mtime
        except Exception:
            created_at = time.time()
        records.append((float(created_at), path, doc))
    records.sort(key=lambda entry: entry[0])
    for created_at, path, doc in records[:limit_count]:
        token = _make_token("file", path.name, exp, lane_name)
        previews.append(_preview_from_doc(doc, token, created_at))
    return previews


def take(token: str) -> Optional[Dict[str, Any]]:
    """Fetch and remove a specific queued item by token."""
    if not token:
        return None
    token = str(token)
    parsed = _parse_token(token)
    if not parsed:
        return None
    kind, ident, _exp = parsed
    lane_name, base_kind = _parse_token_kind(kind)
    if not lane_name:
        return None

    if base_kind == "redis" and _redis_enabled():
        try:
            doc_id = ident
            raw = _REDIS_CLIENT.get(_redis_doc_key(doc_id, lane_name))
            _REDIS_CLIENT.lrem(_lane_queue_key(lane_name), 1, doc_id)
            if not raw:
                return None
            _REDIS_CLIENT.delete(_redis_doc_key(doc_id, lane_name))
            doc = json.loads(raw)
            if not isinstance(doc, dict):
                return None
            return _strip_prefetch_meta(doc)
        except Exception:
            log.warning("prefetch.redis: take failed; falling back to file queue", exc_info=True)
            _disable_redis("take_failed")
    if base_kind != "file":
        return None
    name = ident
    if not name or "/" in name or "\\" in name:
        return None
    path = _lane_dir(lane_name) / name
    if not path.exists():
        return None
    doc = _read_doc(path)
    if not isinstance(doc, dict) or _is_test_fixture_doc(doc):
        _drop_queue_file(path, "invalid_or_test_fixture")
        return None
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
    return _strip_prefetch_meta(doc)


def enqueue(doc: Dict[str, Any], lane: Optional[str] = None) -> Optional[str]:
    """Persist a generated page to the prefetch queue; returns identifier if enqueued.
    Skips if duplicate by signature.
    """
    lane_name = _lane_name(lane)
    doc = dict(doc)
    sig = dedupe.signature_for_doc(doc)
    if not sig:
        log.warning("prefetch.enqueue: skipping doc without signature")
        return None

    queue_sig = f"{lane_name}:{sig}"
    current_size = size(lane_name)
    if dedupe.has(queue_sig) and current_size > 0:
        log.debug("prefetch.enqueue: skipping duplicate doc sig=%s queue_size=%d", sig[:12], current_size)
        return None
    if dedupe.has(queue_sig):
        log.debug("prefetch.enqueue: forcing enqueue for duplicate sig=%s because queue empty", sig[:12])

    dedupe.add(queue_sig)

    created_at = float(doc.get("created_at") or time.time())
    doc["created_at"] = created_at
    if isinstance(doc, dict):
        meta = doc.get("_prefetch")
        if not isinstance(meta, dict):
            meta = {}
        meta["lane"] = lane_name
        doc["_prefetch"] = meta
    if _redis_enabled():
        try:
            doc_id = f"{time.time_ns()}-{uuid.uuid4().hex[:8]}"
            payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
            pipe = _REDIS_CLIENT.pipeline()
            pipe.set(_redis_doc_key(doc_id, lane_name), payload)
            pipe.rpush(_lane_queue_key(lane_name), doc_id)
            pipe.execute()
            log.info("prefetch.enqueue: stored doc sig=%s id=%s queue_size=%d", sig[:12], doc_id, current_size + 1)
            return doc_id
        except Exception:
            log.warning("prefetch.redis: enqueue failed; falling back to file queue", exc_info=True)
            _disable_redis("enqueue_failed")
    _ensure_dir(lane_name)
    fname = f"{time.time_ns()}-{uuid.uuid4().hex[:8]}.json"
    path = _lane_dir(lane_name) / fname
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    log.info("prefetch.enqueue: stored doc sig=%s file=%s queue_size=%d", sig[:12], path.name, current_size + 1)
    return path.name


def dequeue(lane: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pop the next document from the queue."""
    lane_name = _lane_name(lane)
    if _redis_enabled():
        try:
            while True:
                doc_id = _REDIS_CLIENT.lpop(_lane_queue_key(lane_name))
                if not doc_id:
                    log.debug("prefetch.dequeue: queue empty")
                    return None
                raw = _REDIS_CLIENT.get(_redis_doc_key(doc_id, lane_name))
                if not raw:
                    continue
                _REDIS_CLIENT.delete(_redis_doc_key(doc_id, lane_name))
                data = json.loads(raw)
                if not isinstance(data, dict):
                    continue
                log.info("prefetch.dequeue: served id=%s", doc_id)
                return _strip_prefetch_meta(data)
        except Exception:
            log.warning("prefetch.redis: dequeue failed; falling back to file queue", exc_info=True)
            _disable_redis("dequeue_failed")
    files = _list_files(lane_name)
    if not files:
        log.debug("prefetch.dequeue: queue empty")
        return None
    for path in files:
        data = _read_file_queue_doc(path)
        if not data:
            continue
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        log.info("prefetch.dequeue: served file=%s remaining=%d", path.name, max(0, len(files) - 1))
        return _strip_prefetch_meta(data)
    log.debug("prefetch.dequeue: no eligible items found")
    return None


def backend() -> str:
    return "redis" if _redis_enabled() else "file"


def redis_disabled_reason() -> str:
    return _REDIS_DISABLED_REASON


def clamp_batch(n: int) -> int:
    if n < BATCH_MIN:
        return BATCH_MIN
    if n > BATCH_MAX:
        return BATCH_MAX
    return n
