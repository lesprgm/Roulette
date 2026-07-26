from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def _json_from_text(text: str) -> Any:
    """Extract JSON object or HTML from text with robust fallbacks; raise on failure.

    Strategy:
    - If text starts with HTML tags, wrap as full_page_html.
    - Try fenced blocks: ```json ...``` first, then any ``` ... ```.
    - Try first balanced {...} object (brace-aware in presence of strings).
    - Sanitize: remove trailing commas, normalize smart quotes.
    - If any HTML-like tag appears anywhere, wrap remaining text as full_page_html.
    """
    t = (text or "").strip()
    tl = t.lower().lstrip()
    if tl.startswith("<!doctype") or tl.startswith("<html") or tl.startswith("<div") or tl.startswith("<body"):
        return {"kind": "full_page_html", "html": t}

    def _balanced_json_slice(s: str) -> Optional[str]:
        in_str = False
        esc = False
        depth = 0
        start_idx = -1
        for i, ch in enumerate(s):
            if not in_str and ch == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif not in_str and ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        return s[start_idx : i + 1]
            elif ch == '"':
                if not esc:
                    in_str = not in_str
                esc = False
                continue
            esc = (ch == "\\") and not esc
        return None

    m = re.search(r"```json\s*([\s\S]*?)```", t, re.IGNORECASE)
    candidate = None
    if m:
        candidate = m.group(1)
    else:
        m2 = re.search(r"```\s*([\s\S]*?)```", t)
        if m2:
            candidate = m2.group(1)
    if not candidate:
        candidate = _balanced_json_slice(t)

    def _try_load(s: str) -> Any:
        return json.loads(s)

    if candidate:
        try:
            return _try_load(candidate)
        except Exception:
            s = re.sub(r",\s*([}\]])", r"\1", candidate)
            s = s.replace("“", '"').replace("”", '"').replace("’", "'")
            try:
                return _try_load(s)
            except Exception:
                pass

    # Last resort: if any HTML-like tag appears anywhere, wrap as full_page_html
    if re.search(r"<\s*(?:!doctype|html|body|main|header|section|footer)\b", t, re.IGNORECASE):
        return {"kind": "full_page_html", "html": t}
    raise ValueError("No JSON or HTML content found")


def _normalize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model output to full-page HTML or raise ValueError."""
    if not isinstance(doc, dict):
        raise ValueError("not a dict")
    if isinstance(doc.get("error"), str):
        return _sanitize_doc_external_assets({"error": str(doc["error"])[:500]})
    for key in ("kind", "type"):
        k = str(doc.get(key) or "").lower()
        if k in {"full_page_html", "page_html", "html_page", "full_html"}:
            html = doc.get("html") or doc.get("content") or doc.get("body")
            if isinstance(html, str) and html.strip():
                return _sanitize_doc_external_assets({"kind": "full_page_html", "html": html})
    if isinstance(doc.get("html"), str) and doc["html"].strip():
        return _sanitize_doc_external_assets({"kind": "full_page_html", "html": doc["html"]})
    for key in ("content", "body", "page", "app", "markup"):
        val = doc.get(key)
        if isinstance(val, str) and ("<" in val and ">" in val):
            return _sanitize_doc_external_assets({"kind": "full_page_html", "html": val})
        if isinstance(val, dict) and isinstance(val.get("html"), str):
            return _sanitize_doc_external_assets({"kind": "full_page_html", "html": val.get("html")})

    def _find_html(obj: Any, depth: int = 0) -> Optional[str]:
        if depth > 2:
            return None
        if isinstance(obj, str) and ("<" in obj and ">" in obj) and len(obj) > 20:
            return obj
        if isinstance(obj, dict):
            for v in obj.values():
                found = _find_html(v, depth + 1)
                if found:
                    return found
        if isinstance(obj, list):
            for v in obj:
                found = _find_html(v, depth + 1)
                if found:
                    return found
        return None

    html_any = _find_html(doc)
    if html_any:
        return _sanitize_doc_external_assets({"kind": "full_page_html", "html": html_any})
    raise ValueError("No renderable HTML found")


_EXTERNAL_URL_RE = re.compile(r"^(https?:)?//", re.IGNORECASE)
_SCRIPT_SRC_RE = re.compile(
    r"<script\b[^>]*\bsrc\s*=\s*(\"|')?([^\"'>\s]+)\1[^>]*>\s*</script\s*>",
    re.IGNORECASE,
)
_LINK_HREF_RE = re.compile(r"<link\b[^>]*\bhref\s*=\s*(\"|')?([^\"'>\s]+)\1[^>]*>", re.IGNORECASE)
_CSS_IMPORT_RE = re.compile(
    r"@import\s+(?:url\(\s*([^)]+)\s*\)|([\"'][^\"']+[\"']))\s*;?",
    re.IGNORECASE,
)
_TAILWIND_CDN_RE = re.compile(r"^(?:https?:)?//cdn\.tailwindcss\.com(?:/|\?|$)", re.IGNORECASE)
_GSAP_CDN_RE = re.compile(
    r"^(?:https?:)?//cdn\.jsdelivr\.net/npm/gsap@[^/]+/dist/gsap(?:\.min)?\.js",
    re.IGNORECASE,
)
_GSAP_DRAGGABLE_CDN_RE = re.compile(
    r"^(?:https?:)?//cdn\.jsdelivr\.net/npm/gsap@[^/]+/dist/Draggable(?:\.min)?\.js",
    re.IGNORECASE,
)
_LUCIDE_CDN_RE = re.compile(r"^(?:https?:)?//unpkg\.com/lucide(?:@[^/]+)?(?:/.*)?$", re.IGNORECASE)
_SCRIPT_STYLE_BLOCK_RE = re.compile(
    r"(<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)\s*>)",
    re.IGNORECASE,
)


def _strip_visible_text_artifacts(html: str) -> Tuple[str, List[Dict[str, str]]]:
    """Clean visible model debris without touching JavaScript or CSS bodies."""
    if not isinstance(html, str) or not html:
        return html, []

    issues: List[Dict[str, str]] = []

    def clean_chunk(chunk: str) -> str:
        original = chunk
        # Text-node debris from LLM drafts, e.g. "ESTABLISHED // ARCHIVES" or "// Start".
        chunk = re.sub(r"(?<=>)\s*//\s*(?=[A-Za-z])", "", chunk)
        chunk = re.sub(r"(?<=[A-Za-z0-9])\s+//\s+(?=[A-Za-z0-9])", " - ", chunk)
        chunk = re.sub(r"```(?:html|json|javascript|js)?|~~~", "", chunk, flags=re.IGNORECASE)
        chunk = re.sub(r"\bTODO\b", "", chunk, flags=re.IGNORECASE)
        chunk = re.sub(r"(?<=>)\s*(?:undefined|null)\s*(?=<)", "", chunk, flags=re.IGNORECASE)
        if chunk != original:
            issues.append(
                {
                    "severity": "info",
                    "field": "html",
                    "message": "Removed visible draft/code artifact text from rendered HTML.",
                }
            )
        return chunk

    parts = _SCRIPT_STYLE_BLOCK_RE.split(html)
    for idx, part in enumerate(parts):
        if not part:
            continue
        if idx % 2 == 1 and _SCRIPT_STYLE_BLOCK_RE.fullmatch(part):
            continue
        parts[idx] = clean_chunk(part)
    return "".join(parts), issues


def _strip_external_assets(html: str) -> Tuple[str, List[Dict[str, str]]]:
    issues: List[Dict[str, str]] = []
    if not isinstance(html, str):
        return html, issues

    def is_external(url: str) -> bool:
        return bool(_EXTERNAL_URL_RE.match((url or "").strip()))

    def rewrite_script_src(src: str) -> Optional[str]:
        if _TAILWIND_CDN_RE.match(src):
            return "/static/vendor/tailwind-play.js"
        if _GSAP_CDN_RE.match(src):
            return "/static/vendor/gsap.min.js"
        if _GSAP_DRAGGABLE_CDN_RE.match(src):
            return "/static/vendor/Draggable.min.js"
        if _LUCIDE_CDN_RE.match(src):
            return "/static/vendor/lucide.min.js"
        return None

    def strip_script(match: re.Match[str]) -> str:
        src = match.group(2) or ""
        if is_external(src):
            local = rewrite_script_src(src)
            if local:
                tag = match.group(0)
                new_tag = re.sub(
                    r"\bsrc\s*=\s*(['\"]).*?\1",
                    f'src="{local}"',
                    tag,
                    flags=re.IGNORECASE,
                )
                issues.append(
                    {
                        "severity": "info",
                        "field": "html",
                        "message": f"Rewrote external script: {src} -> {local}",
                    }
                )
                return new_tag
            issues.append({"severity": "warn", "field": "html", "message": f"Removed external script: {src}"})
            return ""
        return match.group(0)

    def strip_link(match: re.Match[str]) -> str:
        tag = match.group(0)
        href = match.group(2) or ""
        if is_external(href):
            issues.append(
                {"severity": "warn", "field": "html", "message": f"Removed external stylesheet: {href}"}
            )
            return ""
        return tag

    def strip_import(match: re.Match[str]) -> str:
        raw = match.group(1) or match.group(2) or ""
        url = raw.strip().strip("\"' ")
        if is_external(url):
            issues.append({"severity": "warn", "field": "html", "message": f"Removed external @import: {url}"})
            return ""
        return match.group(0)

    html = _SCRIPT_SRC_RE.sub(strip_script, html)
    html = _LINK_HREF_RE.sub(strip_link, html)
    html = _CSS_IMPORT_RE.sub(strip_import, html)
    return html, issues


def _sanitize_doc_external_assets(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(doc, dict):
        return doc
    issues: List[Dict[str, str]] = []
    if doc.get("kind") == "full_page_html" and isinstance(doc.get("html"), str):
        sanitized, removed = _strip_external_assets(doc["html"])
        sanitized, cleaned = _strip_visible_text_artifacts(sanitized)
        if sanitized != doc["html"]:
            doc = dict(doc)
            doc["html"] = sanitized
        issues.extend(removed)
        issues.extend(cleaned)
    if issues:
        debug = doc.get("ndw_debug")
        if not isinstance(debug, dict):
            debug = {}
        debug.setdefault("external_assets_removed", []).extend(issues)
        doc = dict(doc)
        doc["ndw_debug"] = debug
    return doc
