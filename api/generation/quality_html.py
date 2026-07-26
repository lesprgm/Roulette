from __future__ import annotations

import re
from typing import Any, Dict


_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_SCRIPT_RE = re.compile(
    r"<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>",
    re.IGNORECASE,
)


def extract_doc_html(doc: Dict[str, Any]) -> str:
    if not isinstance(doc, dict):
        return ""
    html = doc.get("html")
    return html if isinstance(html, str) else ""


def visible_text(html: str, *, lowercase: bool = False) -> str:
    text = _STYLE_SCRIPT_RE.sub(" ", html or "")
    text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()
    return text.lower() if lowercase else text
