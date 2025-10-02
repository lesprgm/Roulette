import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Set


DEDUPE_ENABLED = (os.getenv("DEDUPE_ENABLED", "1").lower() in {"1", "true", "yes", "on"})
DEDUPE_FILE = Path(os.getenv("DEDUPE_RECENT_FILE", "cache/seen_pages.json"))
DEDUPE_MAX = int(os.getenv("DEDUPE_MAX", "200"))


_WS_RE = re.compile(r"\s+")


def _norm_text(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").strip().lower())


def signature_for_doc(doc: Dict) -> str:
    """Compute a stable signature for a normalized doc.
    Uses the core HTML payload (full_page_html.html or first custom component props.html).
    """
    if not isinstance(doc, dict):
        return ""
    if doc.get("kind") == "full_page_html" and isinstance(doc.get("html"), str):
        payload = _norm_text(doc["html"])
    else:
        payload = ""
        comps = doc.get("components")
        if isinstance(comps, list) and comps:
            c0 = comps[0]
            if isinstance(c0, dict):
                props = c0.get("props") or {}
                h = props.get("html")
                if isinstance(h, str):
                    payload = _norm_text(h)
    h = hashlib.sha256()
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


def _load() -> Dict[str, float]:
    if not DEDUPE_FILE.exists():
        return {}
    try:
        return json.loads(DEDUPE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: Dict[str, float]) -> None:
    DEDUPE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEDUPE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(DEDUPE_FILE)


def has(sig: str) -> bool:
    if not DEDUPE_ENABLED or not sig:
        return False
    data = _load()
    return sig in data


def add(sig: str) -> None:
    if not DEDUPE_ENABLED or not sig:
        return
    data = _load()
    now = time.time()
    data[sig] = now
    # remove oldest if over max
    if len(data) > DEDUPE_MAX:
        for k in sorted(data.keys(), key=lambda k: data[k])[: max(0, len(data) - DEDUPE_MAX)]:
            data.pop(k, None)
    _save(data)
