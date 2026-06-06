from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

PreflightIssue = Dict[str, str]

_NODE_BIN = shutil.which("node")

_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_LINK_TAG_RE = re.compile(r"<link\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_MEDIA_TAG_RE = re.compile(r"<(?:img|video|audio|source)\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_IFRAME_RE = re.compile(r"<iframe\b", re.IGNORECASE)
_STYLE_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.IGNORECASE)
_ATTR_RE = re.compile(r'([a-zA-Z_:][\w:.-]*)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))')
_ID_RE = re.compile(r'\bid\s*=\s*("([^"]+)"|\'([^\']+)\')', re.IGNORECASE)
_CLASS_RE = re.compile(r'\bclass\s*=\s*("([^"]+)"|\'([^\']+)\')', re.IGNORECASE)

_GET_BY_ID_RE = re.compile(r"(?:document\.)?getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)")
_QUERY_SELECTOR_RE = re.compile(r"querySelector(?:All)?\(\s*['\"]([#.][^'\"]+)['\"]\s*\)")
_UNSAFE_GET_BY_ID_RE = re.compile(
    r"(?:document\.)?getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)\s*(?!\?)\.",
    re.IGNORECASE,
)
_UNSAFE_QUERY_SELECTOR_RE = re.compile(
    r"querySelector\(\s*['\"]([#.][^'\"]+)['\"]\s*\)\s*(?!\?)\.",
    re.IGNORECASE,
)
_SET_ID_RE = re.compile(
    r"(?:\.id\s*=\s*['\"]([^'\"]+)['\"]|setAttribute\(\s*['\"]id['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\))"
)
_STATIC_IMPORT_RE = re.compile(
    r"^\s*import\s+(?:[^;]*?\s+from\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_DYNAMIC_IMPORT_RE = re.compile(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
_DANGEROUS_API_RE = re.compile(
    r"\b(fetch|XMLHttpRequest|WebSocket|Worker|SharedWorker|eval|Function)\b|document\.write\b"
)
_THREE_USAGE_RE = re.compile(
    r"\bTHREE\b|WebGLRenderer|getContext\(\s*['\"](?:webgl|webgl2|experimental-webgl)['\"]",
    re.IGNORECASE,
)
_RAF_OR_TIMER_RE = re.compile(r"\b(requestAnimationFrame|setInterval|setTimeout)\b")
_GLOBAL_LISTENER_RE = re.compile(r"\b(?:window|document)\.addEventListener\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_GLOBAL_REMOVE_RE = re.compile(r"\b(?:window|document)\.removeEventListener\(", re.IGNORECASE)
_INLINE_LOOP_CLEANUP_RE = re.compile(
    r"function\s+\w+\s*\([^)]*\)\s*\{[\s\S]{0,4000}?requestAnimationFrame\([\s\S]{0,2000}?NDW\.registerCleanup\(",
    re.IGNORECASE,
)
_POINTER_ONLY_CONTROL_RE = re.compile(
    r"addEventListener\(\s*['\"]mousedown['\"][\s\S]{0,3000}?addEventListener\(\s*['\"]touchstart['\"]",
    re.IGNORECASE,
)
_KEYBOARD_CONTROL_RE = re.compile(r"addEventListener\(\s*['\"]keydown['\"]", re.IGNORECASE)
_ACCESSIBILITY_ATTR_RE = re.compile(
    r"(role\s*=\s*['\"](?:button|slider|spinbutton)['\"]|tabindex\s*=|aria-label\s*=|aria-labelledby\s*=)",
    re.IGNORECASE,
)

_ALLOWED_FULL_PAGE_MODULE_IMPORTS = {
    "/static/vendor/three.module.js",
    "/static/vendor/three-addons/controls/OrbitControls.js",
    "/static/vendor/three-addons/postprocessing/EffectComposer.js",
    "/static/vendor/three-addons/postprocessing/RenderPass.js",
    "/static/vendor/three-addons/postprocessing/UnrealBloomPass.js",
}
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LOCAL_ROUTE_FILES = {
    "/tailwind.css": _PROJECT_ROOT / "static" / "tailwind.css",
}
_HOST_IDS = {
    "appMain",
    "ndw-app",
    "ndw-content",
    "ndw-sandbox",
    "floatingGenerate",
    "floatingGenerateWrap",
    "sitesCounterBadge",
    "toggleJsonBtn",
    "jsonPanel",
    "jsonOut",
    "ndwSnippetError",
    "ndwSnippetErrorMsg",
}

try:
    _HTML_WARN_BYTES = int(os.getenv("PREFLIGHT_HTML_WARN_BYTES", "180000"))
except Exception:
    _HTML_WARN_BYTES = 180000
try:
    _HTML_BLOCK_BYTES = int(os.getenv("PREFLIGHT_HTML_BLOCK_BYTES", "280000"))
except Exception:
    _HTML_BLOCK_BYTES = 280000


def _issue(severity: str, field: str, message: str) -> PreflightIssue:
    return {"severity": severity, "field": field, "message": message}


def _parse_script_attrs(attr_text: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for match in _ATTR_RE.finditer(attr_text or ""):
        name = (match.group(1) or "").lower()
        value = match.group(3) or match.group(4) or match.group(5) or ""
        attrs[name] = value
    return attrs


def _extract_ids(html: str) -> List[str]:
    ids: List[str] = []
    for match in _ID_RE.finditer(html or ""):
        value = match.group(2) or match.group(3) or ""
        if value:
            ids.append(value)
    return ids


def _extract_classes(html: str) -> Set[str]:
    classes: Set[str] = set()
    for match in _CLASS_RE.finditer(html or ""):
        raw = match.group(2) or match.group(3) or ""
        for item in raw.split():
            item = item.strip()
            if item:
                classes.add(item)
    return classes


def _is_remote_url(value: str) -> bool:
    item = (value or "").strip().lower()
    return item.startswith(("http://", "https://", "//"))


def _is_data_or_fragment_url(value: str) -> bool:
    item = (value or "").strip().lower()
    return item.startswith(("data:", "blob:", "#", "mailto:", "tel:"))


def _local_asset_exists(value: str) -> bool:
    item = (value or "").split("?", 1)[0].split("#", 1)[0].strip()
    if not item or _is_data_or_fragment_url(item):
        return True
    if item in _LOCAL_ROUTE_FILES:
        return _LOCAL_ROUTE_FILES[item].exists()
    if item.startswith("/static/"):
        rel = item.lstrip("/")
        return (_PROJECT_ROOT / rel).is_file()
    return False


def _check_url_reference(value: str, *, field: str, label: str) -> List[PreflightIssue]:
    issues: List[PreflightIssue] = []
    item = (value or "").strip()
    if not item or _is_data_or_fragment_url(item):
        return issues
    if _is_remote_url(item):
        issues.append(_issue("block", field, f"Remote {label} '{item}' is not allowed."))
        return issues
    if item.startswith(("/static/", "/tailwind.css")) and not _local_asset_exists(item):
        issues.append(_issue("block", field, f"Local {label} '{item}' does not exist."))
    elif not item.startswith(("/static/", "/tailwind.css")):
        issues.append(_issue("block", field, f"Relative or unsupported {label} '{item}' is not allowed."))
    return issues


def _extract_scripts(html: str) -> List[Dict[str, str]]:
    scripts: List[Dict[str, str]] = []
    for attrs_raw, content in _SCRIPT_TAG_RE.findall(html or ""):
        attrs = _parse_script_attrs(attrs_raw)
        scripts.append(
            {
                "src": (attrs.get("src") or "").strip(),
                "type": (attrs.get("type") or "").strip().lower(),
                "code": content or "",
            }
        )
    return scripts


def _extract_created_ids(js_code: str) -> Set[str]:
    created: Set[str] = set()
    for match in _SET_ID_RE.finditer(js_code or ""):
        created_id = match.group(1) or match.group(2) or ""
        if created_id:
            created.add(created_id)
    return created


def _check_js_syntax(js_code: str, *, module: bool = False) -> Optional[str]:
    if not _NODE_BIN:
        return None
    code = (js_code or "").strip()
    if not code:
        return None
    suffix = ".mjs" if module else ".js"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as handle:
            handle.write(code)
            tmp_path = handle.name
        proc = subprocess.run(
            [_NODE_BIN, "--check", tmp_path],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        if proc.returncode == 0:
            return None
        msg = (proc.stderr or proc.stdout or "").strip()
        if not msg:
            return "JavaScript syntax check failed"
        lines = [line.strip() for line in msg.splitlines() if line.strip()]
        return " ".join(lines[-2:])[:320]
    except Exception:
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _check_selector_refs(
    js_code: str,
    *,
    field: str,
    html_ids: Sequence[str],
    html_classes: Set[str],
) -> List[PreflightIssue]:
    issues: List[PreflightIssue] = []
    ids = set(html_ids) | _HOST_IDS
    created_ids = _extract_created_ids(js_code)
    blocked_missing_ids: Set[str] = set()
    blocked_missing_selectors: Set[str] = set()
    for match in _UNSAFE_GET_BY_ID_RE.finditer(js_code or ""):
        target_id = match.group(1)
        if target_id and target_id not in ids and target_id not in created_ids:
            blocked_missing_ids.add(target_id)
            issues.append(
                _issue(
                    "block",
                    field,
                    f"Script directly dereferences missing element id '{target_id}'.",
                )
            )
    for match in _UNSAFE_QUERY_SELECTOR_RE.finditer(js_code or ""):
        selector = match.group(1) or ""
        if selector.startswith("#"):
            target_id = selector[1:]
            if target_id and target_id not in ids and target_id not in created_ids:
                blocked_missing_selectors.add(selector)
                issues.append(
                    _issue(
                        "block",
                        field,
                        f"Script directly dereferences missing selector '{selector}'.",
                    )
                )
        elif selector.startswith("."):
            target_class = selector[1:]
            if target_class and target_class not in html_classes:
                blocked_missing_selectors.add(selector)
                issues.append(
                    _issue(
                        "block",
                        field,
                        f"Script directly dereferences missing selector '{selector}'.",
                    )
                )
    for match in _GET_BY_ID_RE.finditer(js_code or ""):
        target_id = match.group(1)
        if target_id and target_id not in ids and target_id not in created_ids and target_id not in blocked_missing_ids:
            issues.append(
                _issue(
                    "warn",
                    field,
                    f"Script references missing element id '{target_id}'.",
                )
            )
    for match in _QUERY_SELECTOR_RE.finditer(js_code or ""):
        selector = match.group(1) or ""
        if selector.startswith("#"):
            target_id = selector[1:]
            if (
                target_id
                and target_id not in ids
                and target_id not in created_ids
                and selector not in blocked_missing_selectors
            ):
                issues.append(
                    _issue(
                        "warn",
                        field,
                        f"Script queries missing selector '{selector}'.",
                    )
                )
        elif selector.startswith("."):
            target_class = selector[1:]
            if target_class and target_class not in html_classes and selector not in blocked_missing_selectors:
                issues.append(
                    _issue(
                        "warn",
                        field,
                        f"Script queries missing selector '{selector}'.",
                    )
                )
    return issues


def _check_module_imports(
    js_code: str,
    *,
    field: str,
    allow_module_imports: bool,
) -> List[PreflightIssue]:
    issues: List[PreflightIssue] = []
    imports = list(_STATIC_IMPORT_RE.finditer(js_code or ""))
    imports.extend(_DYNAMIC_IMPORT_RE.finditer(js_code or ""))
    if not imports:
        return issues
    specifiers = [match.group(1) for match in imports if match.group(1)]
    if not allow_module_imports:
        for specifier in specifiers:
            issues.append(
                _issue(
                    "block",
                    field,
                    f"Module import '{specifier}' is not allowed in this document shape.",
                )
            )
        return issues
    for specifier in specifiers:
        if specifier not in _ALLOWED_FULL_PAGE_MODULE_IMPORTS:
            issues.append(
                _issue(
                    "block",
                    field,
                    f"Unsupported module import '{specifier}'. Only {sorted(_ALLOWED_FULL_PAGE_MODULE_IMPORTS)} are allowed.",
                )
            )
    return issues


def _inspect_js(
    js_code: str,
    *,
    field: str,
    html_ids: Sequence[str],
    html_classes: Set[str],
    allow_module_imports: bool,
    module: bool,
    doc_kind: str,
) -> List[PreflightIssue]:
    issues: List[PreflightIssue] = []
    code = (js_code or "").strip()
    if not code:
        return issues

    issues.extend(
        _check_module_imports(
            code,
            field=field,
            allow_module_imports=allow_module_imports,
        )
    )

    if _DANGEROUS_API_RE.search(code):
        issues.append(
            _issue(
                "block",
                field,
                "Dangerous or networked browser APIs are not allowed in generated code.",
            )
        )

    syntax_error = _check_js_syntax(code, module=module)
    if syntax_error:
        issues.append(_issue("block", field, f"JavaScript syntax error: {syntax_error}"))

    issues.extend(_check_selector_refs(code, field=field, html_ids=html_ids, html_classes=html_classes))

    uses_three = bool(_THREE_USAGE_RE.search(code))
    uses_cleanup = "NDW.registerCleanup(" in code
    if uses_three and not module:
        issues.append(
            _issue(
                "block",
                field,
                "Three.js/WebGL code must run inside <script type=\"module\"> in full_page_html output.",
            )
        )
    if uses_three and doc_kind == "full_page_html" and not uses_cleanup:
        issues.append(
            _issue(
                "warn",
                field,
                "Three.js/WebGL cleanup is handled by iframe teardown; explicit NDW.registerCleanup(...) is optional.",
            )
        )
    if doc_kind == "full_page_html" and _RAF_OR_TIMER_RE.search(code) and not uses_cleanup and "NDW.loop(" not in code:
        issues.append(
            _issue(
                "warn",
                field,
                "Long-lived timers or animation loops should register cleanup with NDW.registerCleanup(...).",
            )
        )
    if doc_kind == "full_page_html" and _INLINE_LOOP_CLEANUP_RE.search(code):
        issues.append(
            _issue(
                "warn",
                field,
                "Cleanup registered inside a recurring animation loop is unnecessary in iframe-rendered full pages.",
            )
        )
    global_listener_matches = list(_GLOBAL_LISTENER_RE.finditer(code))
    if doc_kind == "full_page_html" and global_listener_matches and not _GLOBAL_REMOVE_RE.search(code):
        issues.append(
            _issue(
                "warn",
                field,
                "Global window/document listeners are isolated by iframe teardown; explicit removal is optional.",
            )
        )

    return issues


def _inspect_html(
    html: str,
    *,
    field: str,
    allow_module_imports: bool,
    doc_kind: str,
) -> List[PreflightIssue]:
    issues: List[PreflightIssue] = []
    html_bytes = len((html or "").encode("utf-8"))
    if _HTML_BLOCK_BYTES > 0 and html_bytes > _HTML_BLOCK_BYTES:
        issues.append(
            _issue(
                "block",
                field,
                f"Generated HTML is too large ({html_bytes} bytes > {_HTML_BLOCK_BYTES} bytes).",
            )
        )
    elif _HTML_WARN_BYTES > 0 and html_bytes > _HTML_WARN_BYTES:
        issues.append(
            _issue(
                "warn",
                field,
                f"Generated HTML is heavy ({html_bytes} bytes > {_HTML_WARN_BYTES} bytes).",
            )
        )
    if doc_kind == "full_page_html":
        if "<!doctype" not in (html or "").lower():
            issues.append(_issue("warn", field, "Full-page HTML should include a doctype."))
        if not re.search(r"<html\b", html or "", re.IGNORECASE):
            issues.append(_issue("block", field, "full_page_html output must include an <html> element."))
        if not re.search(r"<body\b", html or "", re.IGNORECASE):
            issues.append(_issue("block", field, "full_page_html output must include a <body> element."))
        if not re.search(r"\bid\s*=\s*['\"]ndw-content['\"]", html or "", re.IGNORECASE):
            issues.append(_issue("warn", field, "Full-page HTML should include a primary #ndw-content stage."))
    if _IFRAME_RE.search(html or ""):
        issues.append(_issue("block", field, "Generated pages must not create nested iframes."))

    ids = _extract_ids(html)
    classes = _extract_classes(html)
    seen: Set[str] = set()
    duplicates: Set[str] = set()
    for item in ids:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    for dup in sorted(duplicates):
        issues.append(_issue("block", field, f"Duplicate id '{dup}' found in HTML."))

    scripts = _extract_scripts(html)
    for index, script in enumerate(scripts):
        src = script.get("src") or ""
        script_field = f"{field}.scripts[{index}]"
        if src:
            issues.extend(_check_url_reference(src, field=script_field, label="script"))
            if issues and any(item.get("field") == script_field and item.get("severity") == "block" for item in issues):
                continue
            if src.startswith("/") and not (src.startswith("/static/vendor/") or src == "/static/js/ndw.js"):
                issues.append(_issue("block", script_field, f"Local script '{src}' is not an allowed generated-page script."))
            continue
        issues.extend(
            _inspect_js(
                script.get("code") or "",
                field=script_field,
                html_ids=ids,
                html_classes=classes,
                allow_module_imports=allow_module_imports,
                module="module" in (script.get("type") or ""),
                doc_kind=doc_kind,
            )
        )
    for index, attrs_raw in enumerate(_LINK_TAG_RE.findall(html or "")):
        attrs = _parse_script_attrs(attrs_raw)
        href = (attrs.get("href") or "").strip()
        rel = (attrs.get("rel") or "").strip().lower()
        if not href:
            continue
        link_field = f"{field}.links[{index}]"
        issues.extend(_check_url_reference(href, field=link_field, label="link"))
        if rel == "stylesheet" and href.startswith("/") and not (
            href.startswith("/static/design-kit/")
            or href.startswith("/static/vendor/fonts/")
            or href == "/tailwind.css"
        ):
            issues.append(_issue("block", link_field, f"Stylesheet '{href}' is not an allowed generated-page stylesheet."))
    for index, attrs_raw in enumerate(_MEDIA_TAG_RE.findall(html or "")):
        attrs = _parse_script_attrs(attrs_raw)
        src = (attrs.get("src") or "").strip()
        if src:
            issues.extend(_check_url_reference(src, field=f"{field}.media[{index}]", label="media asset"))
    for index, url in enumerate(_STYLE_URL_RE.findall(html or "")):
        issues.extend(_check_url_reference(url, field=f"{field}.style_urls[{index}]", label="CSS asset"))
    if doc_kind == "full_page_html" and _POINTER_ONLY_CONTROL_RE.search(html or ""):
        if not _KEYBOARD_CONTROL_RE.search(html or "") and not _ACCESSIBILITY_ATTR_RE.search(html or ""):
            issues.append(
                _issue(
                    "warn",
                    field,
                    "Pointer-driven custom controls should expose keyboard handling and accessibility semantics.",
                )
            )
    return issues


def preflight_doc(doc: Dict[str, Any]) -> List[PreflightIssue]:
    if not isinstance(doc, dict) or doc.get("error"):
        return []

    issues: List[PreflightIssue] = []
    kind = str(doc.get("kind") or "").lower()
    if kind == "full_page_html":
        html = doc.get("html")
        if isinstance(html, str):
            issues.extend(
                _inspect_html(
                    html,
                    field="html",
                    allow_module_imports=True,
                    doc_kind="full_page_html",
                )
            )
        return issues

    if kind == "ndw_snippet_v1":
        html = doc.get("html")
        if isinstance(html, str) and html.strip():
            issues.extend(
                _inspect_html(
                    html,
                    field="html",
                    allow_module_imports=False,
                    doc_kind="ndw_snippet_v1",
                )
            )
        js_code = doc.get("js")
        if isinstance(js_code, str) and js_code.strip():
            issues.extend(
                _inspect_js(
                    js_code,
                    field="js",
                    html_ids=_extract_ids(html or ""),
                    html_classes=_extract_classes(html or ""),
                    allow_module_imports=False,
                    module=False,
                    doc_kind="ndw_snippet_v1",
                )
            )
        return issues

    components = doc.get("components")
    if isinstance(components, list):
        for index, comp in enumerate(components):
            if not isinstance(comp, dict):
                continue
            props = comp.get("props")
            html = props.get("html") if isinstance(props, dict) else None
            if isinstance(html, str) and html.strip():
                issues.extend(
                    _inspect_html(
                        html,
                        field=f"components[{index}].props.html",
                        allow_module_imports=False,
                        doc_kind="component_html",
                    )
                )
        return issues

    return issues


def has_blocking_issues(issues: Iterable[PreflightIssue]) -> bool:
    for issue in issues:
        if str(issue.get("severity", "")).lower() == "block":
            return True
    return False


def annotate_doc(doc: Dict[str, Any], issues: Sequence[PreflightIssue]) -> Dict[str, Any]:
    if not isinstance(doc, dict) or not issues:
        return doc
    debug = doc.get("ndw_debug")
    if not isinstance(debug, dict):
        debug = {}
    existing = debug.get("preflight_issues")
    merged: List[PreflightIssue] = list(existing) if isinstance(existing, list) else []
    merged.extend(dict(item) for item in issues if isinstance(item, dict))
    debug["preflight_issues"] = merged
    out = dict(doc)
    out["ndw_debug"] = debug
    return out


def first_js_syntax_error(doc: Dict[str, Any]) -> Optional[str]:
    if not isinstance(doc, dict):
        return None
    kind = str(doc.get("kind") or "").lower()
    if kind == "full_page_html" and isinstance(doc.get("html"), str):
        for script in _extract_scripts(doc["html"]):
            if script.get("src"):
                continue
            err = _check_js_syntax(script.get("code") or "", module="module" in (script.get("type") or ""))
            if err:
                return err
    if kind == "ndw_snippet_v1" and isinstance(doc.get("js"), str):
        return _check_js_syntax(doc["js"], module=False)
    return None
