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


def _repair_json_loose(text: str) -> str:
    """Best-effort repair for truncated JSON by closing open strings/braces."""
    t = (text or "").strip()
    if not t:
        return t
    in_str = False
    esc = False
    braces = 0
    brackets = 0
    for ch in t:
        if ch == '"' and not esc:
            in_str = not in_str
        if not in_str:
            if ch == "{":
                braces += 1
            elif ch == "}":
                braces -= 1
            elif ch == "[":
                brackets += 1
            elif ch == "]":
                brackets -= 1
        esc = (ch == "\\") and not esc
    if in_str:
        t += '"'
    if brackets > 0:
        t += "]" * brackets
    if braces > 0:
        t += "}" * braces
    return t


def _extract_completed_objects_from_array(text: str) -> List[Dict[str, Any]]:
    """Naively extract completed {...} objects from a JSON array string."""
    objs: List[Dict[str, Any]] = []
    # Strip the leading '[' if present
    s = text.strip()
    if s.startswith("["):
        s = s[1:].strip()

    depth = 0
    start = -1
    in_str = False
    esc = False

    for i, ch in enumerate(s):
        if ch == '"' and not esc:
            in_str = not in_str
        if in_str:
            esc = (ch == "\\") and not esc
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = s[start : i + 1]
                try:
                    objs.append(json.loads(candidate))
                except Exception:
                    pass
                start = -1
    return objs


def _normalize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model output to one of the accepted shapes or raise ValueError."""
    if not isinstance(doc, dict):
        raise ValueError("not a dict")
    if isinstance(doc.get("error"), str):
        return _sanitize_doc_external_assets({"error": str(doc["error"])[:500]})
    # Inference: if no explicit kind/components but looks like a snippet payload, coerce
    if ("html" in doc or "css" in doc or "js" in doc) and not (
        doc.get("components") or doc.get("kind") or doc.get("type")
    ):
        doc = {
            "kind": "ndw_snippet_v1",
            **{k: v for k, v in doc.items() if k in {"title", "background", "css", "html", "js"}},
        }
    # Accept the new compact snippet format directly
    kind = str(doc.get("kind") or doc.get("type") or "").lower()
    # Tolerate common synonyms for snippet kind
    if kind in {"ndw_snippet", "snippet_v1", "ndw-canvas-snippet", "canvas_snippet", "canvas-snippet"}:
        kind = "ndw_snippet_v1"
    if kind == "ndw_snippet_v1":
        # Validate minimal fields, coerce to expected keys
        out: Dict[str, Any] = {"kind": "ndw_snippet_v1"}
        if isinstance(doc.get("title"), str):
            out["title"] = doc["title"]
        bg = doc.get("background")
        if isinstance(bg, dict):
            out_bg: Dict[str, Any] = {}
            sty = bg.get("style")
            if isinstance(sty, list):
                sty = "; ".join([s for s in sty if isinstance(s, str)])
            if isinstance(sty, str) and sty.strip():
                sty = re.sub(r"^\s*background\s*:\s*", "", sty, flags=re.IGNORECASE)
                out_bg["style"] = sty
            cls = bg.get("class") or bg.get("className") or bg.get("classes")
            if isinstance(cls, list):
                cls = " ".join([c for c in cls if isinstance(c, str)])
            if isinstance(cls, str) and cls.strip():
                out_bg["class"] = cls
            if out_bg:
                out["background"] = out_bg
        css = doc.get("css")
        html = doc.get("html")
        js = doc.get("js")
        if isinstance(css, str) and css.strip():
            out["css"] = css
        if isinstance(html, str) and html.strip():
            out["html"] = html
        if isinstance(js, str) and js.strip():
            out["js"] = js
        if not out.get("html"):
            # If no HTML provided, attempt to derive from any nested structure
            for k in ("content", "body", "markup"):
                v = doc.get(k)
                if isinstance(v, str) and ("<" in v and ">" in v):
                    out["html"] = v
                    break
        if not out.get("html") and not out.get("css") and not out.get("js"):
            raise ValueError("ndw_snippet_v1 missing content")
        return _sanitize_doc_external_assets(out)
    # Accept common variants/synonyms for full-page HTML
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
    comps = doc.get("components")
    if isinstance(comps, dict):
        comps = [comps]
    if isinstance(comps, list):
        normalized_components: list[Dict[str, Any]] = []
        for idx, c in enumerate(comps):
            if not isinstance(c, dict):
                continue
            raw_props = c.get("props")
            props = dict(raw_props) if isinstance(raw_props, dict) else {}
            html = props.get("html")
            if not (isinstance(html, str) and html.strip()):
                html = c.get("html") if isinstance(c.get("html"), str) else None
            if not (isinstance(html, str) and html.strip()):
                continue
            height_val = props.get("height") if isinstance(props, dict) else c.get("height")
            try:
                height = int(height_val) if height_val is not None else 360
            except Exception:
                # If height is a string like "100vh", fall back to a generous default
                height = 720
            # Ensure html/height are present and sanitized
            props["html"] = html.strip()
            props["height"] = height
            normalized_components.append(
                {
                    "id": str(c.get("id") or f"custom-{idx + 1}"),
                    "type": "custom",
                    "props": props,
                }
            )
        if normalized_components:
            return _sanitize_doc_external_assets({"components": normalized_components})

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
    r"^(?:https?:)?//cdnjs\.cloudflare\.com/ajax/libs/gsap/[^/]+/gsap(?:\.min)?\.js",
    re.IGNORECASE,
)
_LUCIDE_CDN_RE = re.compile(r"^(?:https?:)?//unpkg\.com/lucide(?:@[^/]+)?(?:/.*)?$", re.IGNORECASE)


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
        if sanitized != doc["html"]:
            doc = dict(doc)
            doc["html"] = sanitized
        issues.extend(removed)
    comps = doc.get("components")
    if isinstance(comps, list):
        next_comps = []
        changed = False
        for comp in comps:
            if not isinstance(comp, dict):
                next_comps.append(comp)
                continue
            props = comp.get("props")
            html = props.get("html") if isinstance(props, dict) else None
            if isinstance(html, str):
                sanitized, removed = _strip_external_assets(html)
                if sanitized != html:
                    new_comp = dict(comp)
                    new_props = dict(props)
                    new_props["html"] = sanitized
                    new_comp["props"] = new_props
                    comp = new_comp
                    changed = True
                if removed:
                    for item in removed:
                        item = dict(item)
                        item["field"] = f"components[{comp.get('id') or ''}].html"
                        issues.append(item)
            next_comps.append(comp)
        if changed:
            doc = dict(doc)
            doc["components"] = next_comps
    if issues:
        debug = doc.get("ndw_debug")
        if not isinstance(debug, dict):
            debug = {}
        debug.setdefault("external_assets_removed", []).extend(issues)
        doc = dict(doc)
        doc["ndw_debug"] = debug
    return doc
