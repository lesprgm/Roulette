from __future__ import annotations

import re
from typing import Any, Dict, List


_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_SCRIPT_RE = re.compile(
    r"<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>",
    re.IGNORECASE,
)


def extract_doc_html(doc: Dict[str, Any]) -> str:
    if not isinstance(doc, dict):
        return ""
    html = doc.get("html")
    if isinstance(html, str):
        return html
    components = doc.get("components")
    if not isinstance(components, list):
        return ""
    chunks: List[str] = []
    for component in components:
        props = component.get("props") if isinstance(component, dict) else None
        chunk = props.get("html") if isinstance(props, dict) else None
        if isinstance(chunk, str):
            chunks.append(chunk)
    return "\n".join(chunks)


def visible_text(html: str, *, lowercase: bool = False) -> str:
    text = _STYLE_SCRIPT_RE.sub(" ", html or "")
    text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()
    return text.lower() if lowercase else text
