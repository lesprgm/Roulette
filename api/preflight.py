from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

PreflightIssue = Dict[str, str]

_NODE_BIN = shutil.which("node")

_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(r'([a-zA-Z_:][\w:.-]*)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))')
_ID_RE = re.compile(r'\bid\s*=\s*("([^"]+)"|\'([^\']+)\')', re.IGNORECASE)
_CLASS_RE = re.compile(r'\bclass\s*=\s*("([^"]+)"|\'([^\']+)\')', re.IGNORECASE)

_GET_BY_ID_RE = re.compile(r"(?:document\.)?getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)")
_QUERY_SELECTOR_RE = re.compile(r"querySelector(?:All)?\(\s*['\"]([#.][^'\"]+)['\"]\s*\)")
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

_ALLOWED_FULL_PAGE_MODULE_IMPORTS = {"three"}
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
    for match in _GET_BY_ID_RE.finditer(js_code or ""):
        target_id = match.group(1)
        if target_id and target_id not in ids and target_id not in created_ids:
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
            if target_id and target_id not in ids and target_id not in created_ids:
                issues.append(
                    _issue(
                        "warn",
                        field,
                        f"Script queries missing selector '{selector}'.",
                    )
                )
        elif selector.startswith("."):
            target_class = selector[1:]
            if target_class and target_class not in html_classes:
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
                "block",
                field,
                "Three.js/WebGL pages must register teardown with NDW.registerCleanup(...).",
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

    return issues


def _inspect_html(
    html: str,
    *,
    field: str,
    allow_module_imports: bool,
    doc_kind: str,
) -> List[PreflightIssue]:
    issues: List[PreflightIssue] = []
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
        if src and src.startswith(("http://", "https://", "//")):
            issues.append(
                _issue(
                    "block",
                    script_field,
                    f"Remote script '{src}' is not allowed.",
                )
            )
            continue
        if src:
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
