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


def _skeletonize(html: str) -> str:
    """Extract a structural 'skeleton' of the HTML.
    Removes comments, scripts, styles, and all text nodes. 
    Keeps only tags and their class attributes to identify layout similarity.
    """
    if not html:
        return ""
    # 1. Remove comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # 2. Remove script and style blocks completely
    html = re.sub(r"<(script|style).*?>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 3. Strip all text between tags
    html = re.sub(r">[^<]+<", "><", html)
    # 4. Strip start/end text
    html = re.sub(r"^[^<]+", "", html)
    html = re.sub(r"[^>]+$", "", html)
    # 5. Extract just tags and classes? No, let's just use the stripped tags as-is.
    # We want to be sensitive to tag order and nesting.
    # Optionally: keep only classes to be even more structural
    # html = re.sub(r'<([a-z0-9]+)\s+[^>]*class=(["\'])(.*?)\2[^>]*>', r'<\1 class=\2\3\2>', html, flags=re.IGNORECASE)
    
    return _WS_RE.sub("", html)


def signature_for_doc(doc: Dict) -> str:
    """Compute a stable structural signature for a normalized doc.
    Uses the skeletonized HTML to ensure visual variety.
    """
    if not isinstance(doc, dict):
        return ""
    if doc.get("kind") == "ndw_snippet_v1":
        payload = _skeletonize(doc.get("html") or "") + (doc.get("css") or "") + (doc.get("js") or "")
    elif doc.get("kind") == "full_page_html" and isinstance(doc.get("html"), str):
        payload = _skeletonize(doc["html"])
    else:
        payload = ""
        comps = doc.get("components")
        if isinstance(comps, list) and comps:
            c0 = comps[0]
            if isinstance(c0, dict):
                props = c0.get("props") or {}
                h = props.get("html")
                if isinstance(h, str):
                    payload = _skeletonize(h)
    
    if not payload:
        # Fallback to JSON dump if we can't extract HTML
        try:
            payload = json.dumps(doc, sort_keys=True)
        except Exception:
            payload = str(doc)
            
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
