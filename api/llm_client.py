from __future__ import annotations
import json
import logging
import os
import random
import re
import time
from typing import Any, Dict, Iterable, Optional, Tuple, List, Set
import requests
from api import dedupe
from api.design_kit import compact_design_kit_manifest
from api.generation.experience_quality import score_experience
from api.generation.prompts import (
    FINAL_HTML_OUTPUT_FORMAT,
    HARD_RUNTIME_RULES,
    PAGE_SHAPE_HINT as _PAGE_SHAPE_HINT,
    PREMIUM_PLAN_SCHEMA,
    PREMIUM_RUNTIME_GUIDANCE,
    PREMIUM_STYLE_GUIDANCE,
)
from api.llm_parsing import (
    _json_from_text,
    _normalize_doc,
)
from api.generation.novelty import novelty_summary
from api.preflight import annotate_doc as _annotate_preflight_doc
from api.preflight import first_js_syntax_error as _first_js_syntax_error
from api.preflight import has_blocking_issues as _preflight_has_blocking_issues
from api.preflight import preflight_doc as _preflight_doc
from api.quality import PREMIUM_SCORE_THRESHOLD, score_page_doc
from api.generation.redis_diversity import choose_experience_cell
from api.generation.semantic_anchors import select_semantic_anchors


def _testing_stub_enabled() -> bool:
    """Return True when pytest is running and keys match the original environment values."""
    if not os.getenv("PYTEST_CURRENT_TEST"):
        return False
    if os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}:
        return False
    # If no providers are configured, don't hide failures behind a stub.
    if not GEMINI_API_KEY:
        return False
    if GEMINI_API_KEY != _ENV_GEMINI_API_KEY:
        return False
    return True
log = logging.getLogger(__name__)

try:
    TEMPERATURE = float(os.getenv("TEMPERATURE", "1.5"))
except Exception:
    TEMPERATURE = 1.5

# Premium burst generation: number of sites requested from Gemini in one streaming call.
try:
    BURST_SITE_COUNT = int(os.getenv("BURST_SITE_COUNT", "15"))
except Exception:
    BURST_SITE_COUNT = 15
BURST_SITE_COUNT = max(1, min(BURST_SITE_COUNT, 50))

# Token and timeout configuration
# Defaults favor longer generations; adjust via .env if provider rejects
try:
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "15000"))
except Exception:
    LLM_MAX_TOKENS = 15000
try:
    LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "105"))
except Exception:
    LLM_TIMEOUT_SECS = 105
_DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 64000
try:
    GEMINI_MAX_OUTPUT_TOKENS = int(
        os.getenv("GEMINI_MAX_OUTPUT_TOKENS", str(_DEFAULT_GEMINI_MAX_OUTPUT_TOKENS))
    )
except Exception:
    GEMINI_MAX_OUTPUT_TOKENS = _DEFAULT_GEMINI_MAX_OUTPUT_TOKENS
try:
    GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS = int(
        os.getenv("GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS", "0") or 0
    )
except Exception:
    GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS = 0
try:
    PREMIUM_BURST_MIN_HTML_BYTES = int(os.getenv("PREMIUM_BURST_MIN_HTML_BYTES", "3000"))
except Exception:
    PREMIUM_BURST_MIN_HTML_BYTES = 3000
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "low").strip().lower()
GEMINI_STREAM_DEBUG = os.getenv("GEMINI_STREAM_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
try:
    GEMINI_STREAM_DEBUG_CHARS = int(os.getenv("GEMINI_STREAM_DEBUG_CHARS", "4000"))
except Exception:
    GEMINI_STREAM_DEBUG_CHARS = 4000
GEMINI_STREAM_DEBUG_WRITE = os.getenv("GEMINI_STREAM_DEBUG_WRITE", "0").lower() in {"1", "true", "yes", "on"}
GEMINI_STREAM_DEBUG_DIR = os.getenv("GEMINI_STREAM_DEBUG_DIR", "cache/gemini_stream").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
_ENV_GEMINI_API_KEY = GEMINI_API_KEY

GEMINI_GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-3.5-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview").strip()
GEMINI_GENERATION_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_GENERATION_MODEL}:generateContent"
)
GEMINI_FALLBACK_GENERATION_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_FALLBACK_MODEL}:generateContent"
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_GENERATION_MODEL
    else ""
)
GEMINI_STREAM_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_GENERATION_MODEL}:streamGenerateContent"
)
GEMINI_FALLBACK_STREAM_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_FALLBACK_MODEL}:streamGenerateContent"
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_GENERATION_MODEL
    else ""
)
"""
This module now only calls the LLM. No local library or stub fallbacks.
If generation fails, we return {"error": "..."} and the API returns 200 with that body,
or 503 earlier in the /generate endpoint if credentials are missing.
"""

def status() -> Dict[str, Any]:
    if _testing_stub_enabled():
        return {
            "provider": None,
            "model": None,
            "has_token": False,
            "using": "stub",
            "testing": True,
        }
    if GEMINI_API_KEY:
        return {
            "provider": "gemini",
            "model": GEMINI_GENERATION_MODEL,
            "has_token": True,
            "using": "gemini-premium",
            "primary": GEMINI_GENERATION_MODEL,
            "fallback": GEMINI_FALLBACK_MODEL or None,
        }
    return {
        "provider": None,
        "model": None,
        "has_token": False,
        "using": "stub",
    }


def probe() -> Dict[str, Any]:
    if _testing_stub_enabled():
        return {"ok": False, "using": "stub", "testing": True}
    if GEMINI_API_KEY:
        return {"ok": True, "using": "gemini-premium"}
    return {"ok": False, "using": "stub"}


def premium_available() -> bool:
    return bool(GEMINI_API_KEY)


def _attach_quality_score(doc: Dict[str, Any], mode: str) -> Dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("error"):
        return doc
    quality = score_page_doc(doc)
    out = dict(doc)
    debug = out.get("ndw_debug")
    if not isinstance(debug, dict):
        debug = {}
    debug["generation_mode"] = mode
    debug["quality_score"] = quality
    out["ndw_debug"] = debug
    return out


def generate_page(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
    run_review: bool = True,
    providers_override: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Premium-only generation helper retained for script/API compatibility."""
    del run_review, providers_override
    seed_val = int(seed or 0) or random.randint(1, 10_000_000)
    doc = generate_page_premium(brief, seed_val, user_key=user_key)
    if isinstance(doc, dict) and not doc.get("error"):
        return doc
    return doc if isinstance(doc, dict) and doc.get("error") else {"error": "Model generation failed"}


def generate_page_premium(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
) -> Dict[str, Any]:
    auto_cues = {"", "auto", "random", "surprise me"}
    brief_str = (brief or "").strip()
    if brief_str.lower() in auto_cues:
        brief_str = ""
    seed_val = int(seed or 0) or random.randint(1, 10_000_000)

    if _testing_stub_enabled():
        return _attach_quality_score(
            _call_testing_stub(brief_str, seed_val, "PREMIUM MODE TEST STUB"),
            "premium",
        )
    if not GEMINI_API_KEY:
        return {"error": "Premium mode requires GEMINI_API_KEY"}

    plan = _call_gemini_premium_plan(brief_str, seed_val, user_key)
    if not isinstance(plan, dict):
        return {"error": "Premium planner failed"}

    raw_doc = _call_gemini_premium_build(brief_str, seed_val, plan)
    if not isinstance(raw_doc, dict):
        return {"error": "Premium build failed"}
    try:
        doc = _normalize_doc(raw_doc)
    except Exception as exc:
        logging.warning("Premium build normalization failed: %r", exc)
        return {"error": "Premium build returned invalid HTML"}

    preflight_issues = _preflight_doc(doc)
    if preflight_issues:
        doc = _annotate_preflight_doc(doc, preflight_issues)
    if _preflight_has_blocking_issues(preflight_issues):
        return {"error": "Premium build failed local preflight", "issues": preflight_issues}
    scored = _attach_quality_score(doc, "premium")
    debug = dict(scored.get("ndw_debug") or {})
    debug["premium_plan"] = plan
    debug["experience_quality"] = score_experience(scored, plan)
    scored["ndw_debug"] = debug
    return scored


def _call_testing_stub(brief: str, seed: int, category_note: str) -> Dict[str, Any]:
    """Fallback stub for local development and testing."""
    return {
        "kind": "full_page_html",
        "html": f"<!doctype html><html><body><h1>{brief or 'Stub App'}</h1><p>Seed: {seed}</p><p>Category: {category_note}</p></body></html>"
    }


def _get_design_matrix_b64() -> Optional[str]:
    """Load the design matrix blueprint and return base64 string."""
    # Use the stable repo path
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "design_matrix.jpg")
    if not os.path.exists(path):
        # Fallback to any file in brain dir if name changed, or return None
        return None
    try:
        import base64
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logging.warning("Failed to encode design matrix: %r", e)
        return None


def _vision_grounding_note() -> str:
    return """
=== VISION GROUNDING: DESIGN MATRIX ATTACHED ===
1. Analyze the attached UI Design Matrix.
2. Use it as a reference for composition, palette energy, and atmosphere.
3. The matrix still includes the classic lenses Professional, Playful, Brutalist, Cozy; you may borrow from them,
   but the assignment axes below are the actual source of truth.
4. Prefer colors and contrast relationships that feel sampled from the matrix rather than generic defaults.
==============================================
""".strip()


def _call_gemini_structured(
    parts: List[Dict[str, Any]],
    schema: Dict[str, Any],
    *,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    endpoint: Optional[str] = None,
) -> Optional[Any]:
    generation_config = {
        "temperature": TEMPERATURE if temperature is None else temperature,
        "maxOutputTokens": max_output_tokens or GEMINI_MAX_OUTPUT_TOKENS,
        "responseMimeType": "application/json",
        "responseSchema": schema,
    }
    if GEMINI_THINKING_LEVEL:
        generation_config["thinkingConfig"] = {"thinkingLevel": GEMINI_THINKING_LEVEL}
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config,
    }
    endpoints = [endpoint or GEMINI_GENERATION_ENDPOINT]
    if endpoint is None and GEMINI_FALLBACK_GENERATION_ENDPOINT:
        endpoints.append(GEMINI_FALLBACK_GENERATION_ENDPOINT)
    for idx, target_endpoint in enumerate(endpoints):
        label = "primary" if idx == 0 else "fallback"
        try:
            resp = requests.post(
                target_endpoint,
                params={"key": GEMINI_API_KEY},
                json=body,
                timeout=LLM_TIMEOUT_SECS,
            )
        except Exception as exc:
            logging.warning("Gemini structured %s request error: %r", label, exc)
            continue

        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Gemini structured %s HTTP %s: %s", label, resp.status_code, msg)
            continue

        try:
            data = resp.json()
            text = _extract_gemini_text(data)
            if not text:
                continue
            try:
                return json.loads(text)
            except Exception:
                return _json_from_text(text)
        except Exception as exc:
            logging.warning("Gemini structured %s extraction error: %r", label, exc)
            continue
    return None


def _call_gemini_text(
    parts: List[Dict[str, Any]],
    *,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    endpoint: Optional[str] = None,
) -> Optional[str]:
    generation_config: Dict[str, Any] = {
        "temperature": TEMPERATURE if temperature is None else temperature,
        "maxOutputTokens": max_output_tokens or GEMINI_MAX_OUTPUT_TOKENS,
    }
    if GEMINI_THINKING_LEVEL:
        generation_config["thinkingConfig"] = {"thinkingLevel": GEMINI_THINKING_LEVEL}
    body = {"contents": [{"parts": parts}], "generationConfig": generation_config}
    endpoints = [endpoint or GEMINI_GENERATION_ENDPOINT]
    if endpoint is None and GEMINI_FALLBACK_GENERATION_ENDPOINT:
        endpoints.append(GEMINI_FALLBACK_GENERATION_ENDPOINT)
    for idx, target_endpoint in enumerate(endpoints):
        label = "primary" if idx == 0 else "fallback"
        try:
            resp = requests.post(
                target_endpoint,
                params={"key": GEMINI_API_KEY},
                json=body,
                timeout=LLM_TIMEOUT_SECS,
            )
        except Exception as exc:
            logging.warning("Gemini text %s request error: %r", label, exc)
            continue
        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Gemini text %s HTTP %s: %s", label, resp.status_code, msg)
            continue
        try:
            payload = resp.json()
            text = _extract_gemini_text(payload)
            if isinstance(text, str) and text.strip():
                return text
        except Exception as exc:
            logging.warning("Gemini text %s extraction error: %r", label, exc)
    return None


def _iter_gemini_stream_text(resp: requests.Response) -> Iterable[str]:
    buffer = ""
    brace_count = 0
    in_string = False
    escape = False
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = line.decode("utf-8")
        raw = chunk.strip()
        if raw.startswith("event:") or raw.startswith(":"):
            continue
        if raw.startswith("data:"):
            raw = raw[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            chunk = raw
        for char in chunk:
            buffer += char
            if char == '"' and not escape:
                in_string = not in_string
            if in_string:
                escape = (char == "\\") and not escape
            else:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0 and buffer.strip():
                        clean_buf = buffer.strip()
                        if clean_buf.startswith(","):
                            clean_buf = clean_buf[1:].strip()
                        if clean_buf.startswith("["):
                            clean_buf = clean_buf[1:].strip()
                        if clean_buf.endswith(","):
                            clean_buf = clean_buf[:-1].strip()
                        if clean_buf.endswith("]"):
                            clean_buf = clean_buf[:-1].strip()
                        try:
                            data = json.loads(clean_buf)
                            text = _extract_gemini_text(data)
                            if text:
                                yield text
                        except Exception as exc:
                            logging.debug("Gemini stream text parse skipped chunk: %r", exc)
                        buffer = ""


def extract_final_html_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    if not isinstance(text, str) or not text.strip():
        return blocks
    pattern = re.compile(r"````html\s*(.*?)````|```html\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(text):
        html = (match.group(1) or match.group(2) or "").strip()
        if html:
            blocks.append(html)
    if blocks:
        return blocks
    lowered = text.lower()
    start = lowered.find("<!doctype html")
    if start < 0:
        start = lowered.find("<html")
    if start >= 0:
        blocks.append(text[start:].strip())
    return blocks


def _premium_burst_site_pattern() -> re.Pattern[str]:
    return re.compile(
        r"===NDW_SITE_(\d+)_START===(.*?)===NDW_SITE_\1_END===",
        re.IGNORECASE | re.DOTALL,
    )


def extract_completed_premium_burst_sites(text: str) -> List[Tuple[int, str]]:
    sites: List[Tuple[int, str]] = []
    seen: Set[int] = set()
    for match in _premium_burst_site_pattern().finditer(text or ""):
        try:
            index = int(match.group(1))
        except Exception:
            continue
        if index in seen:
            continue
        blocks = extract_final_html_blocks(match.group(2) or "")
        if not blocks:
            continue
        seen.add(index)
        sites.append((index, blocks[-1]))
    return sorted(sites, key=lambda item: item[0])


def _premium_burst_rejection(doc: Dict[str, Any], quality: Dict[str, Any]) -> Optional[str]:
    html = str(doc.get("html") or "")
    html_bytes = len(html.encode("utf-8"))
    if html_bytes < PREMIUM_BURST_MIN_HTML_BYTES:
        return f"html too small ({html_bytes}B < {PREMIUM_BURST_MIN_HTML_BYTES}B)"
    if not quality.get("passes"):
        return f"quality score below threshold ({quality.get('score')}/{quality.get('threshold')})"
    return None


def _premium_burst_rejected_payload(
    *,
    index: int,
    reason: str,
    doc: Optional[Dict[str, Any]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
    quality: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "rejected": True,
        "error": reason,
        "premium_burst_index": index,
        "doc": doc,
        "issues": issues or [],
        "quality_score": quality or {},
    }


def _summarize_preflight_issues(issues: Sequence[Dict[str, Any]], limit: int = 4) -> str:
    parts: List[str] = []
    for issue in list(issues or [])[:limit]:
        severity = str(issue.get("severity") or "issue")
        field = str(issue.get("field") or "unknown")
        message = str(issue.get("message") or "").strip()
        parts.append(f"{severity}:{field}:{message}")
    extra = len(issues or []) - len(parts)
    if extra > 0:
        parts.append(f"+{extra} more")
    return " | ".join(parts) if parts else "none"


PREMIUM_SELF_REVIEW_CHECKLIST = f"""
Before writing the final fenced HTML, the <self_review> block must explicitly verify:
- Forbidden APIs used? no. Do not use fetch, XMLHttpRequest, WebSocket, Worker, SharedWorker, eval, Function, or document.write.
- Remote resources used? no. No remote scripts, styles, images, media, fonts, or CSS url() assets.
- Script tags valid? yes. The only allowed script src values are `/static/vendor/tailwind-play.js`, `/static/vendor/gsap.min.js`, `/static/vendor/ScrollTrigger.min.js`, `/static/vendor/lucide.min.js`, and `/static/js/ndw.js`; do not invent plugin paths such as Draggable.
- Module imports local and iframe-safe? yes. Three.js must use `/static/vendor/three.module.js`; addons may only use `/static/vendor/three-addons/controls/OrbitControls.js`, `/static/vendor/three-addons/postprocessing/EffectComposer.js`, `/static/vendor/three-addons/postprocessing/RenderPass.js`, or `/static/vendor/three-addons/postprocessing/UnrealBloomPass.js`.
- DOM references safe? yes. Every getElementById/querySelector target exists, is created before use, or uses defensive optional access.
- Complete document? yes. Include doctype, html, head, body, and a visible #ndw-content stage.
- Substantial premium page? yes. Final HTML must be at least {PREMIUM_BURST_MIN_HTML_BYTES} bytes, not a stub or tiny shell.
- Composition strong? yes. Use at least two major regions or one immersive full-viewport stage; do not ship a generic centered-card shell.
- First action and state change visible? yes. The visitor sees what to do, and input visibly changes page state.
If any answer is not exactly safe/yes/no as required, rewrite the draft before the final HTML block.
""".strip()


def _build_premium_burst_prompt(brief: str, seed: int, targets: List[Dict[str, Any]]) -> str:
    return f"""
{_vision_grounding_note()}
Build {len(targets)} distinct premium interactive web experiences in one streaming response.

Output format is mandatory and repeated once per site:
===NDW_SITE_1_START===
	<thinking>One short semantic plan for site 1.</thinking>
	<draft>Initial complete HTML draft.</draft>
	<self_review>Answer the hard reject checklist below, then list concrete fixes applied before final HTML.</self_review>
```html
<!doctype html>
...
```
===NDW_SITE_1_END===

Then site 2, site 3, etc. Use matching numbers in START and END markers.
Do not output JSON. Do not include prose outside site markers.

Brief: {brief or 'Surprise me with bold, replayable mini-experiences.'}
Seed: {seed}

Per-site creative targets. Each site must feel unrelated to the others:
{json.dumps(targets, indent=2)}

Experience contract for every site:
- Make the visitor role, visitor goal, onboarding cue, and first interaction visible.
- Implement a primary loop: user action -> visible response -> state change -> reward/payoff -> continue reason.
- Use semantic anchors as interaction/content/motion logic, not just labels or colors.
- Include reset/replay when appropriate.
- Include mobile-friendly pointer/touch/keyboard fallback.

Local design kit manifest:
{compact_design_kit_manifest()}

	Premium burst requirements:
- Each site must include a complete final fenced html block inside its markers.
- Each site must be a complete document with `<html>`, `<head>`, and `<body>`.
- Each site must have a different layout/composition and primary interaction model.
- Use at least one local design-kit asset or font in each site.
- If you include local fonts, use `<link rel="stylesheet" href="/static/design-kit/fonts.css">`.
- If you use overlays, reference `/static/design-kit/overlays/...` paths exactly.
- Three.js must use: `import * as THREE from '/static/vendor/three.module.js';`.
	- The app renders this HTML in an iframe, so no host cleanup code is required.

	Hard reject self-review checklist for every site:
	{PREMIUM_SELF_REVIEW_CHECKLIST}
	
	{HARD_RUNTIME_RULES}

{PREMIUM_STYLE_GUIDANCE}
"""


def generate_page_premium_burst(
    brief: str,
    seed: int,
    *,
    count: int = 5,
    user_key: Optional[str] = None,
    include_rejected: bool = False,
) -> Iterable[Dict[str, Any]]:
    del user_key
    seed_val = int(seed or 0) or random.randint(1, 10_000_000)
    target_count = max(1, min(25, int(count or 1)))
    if _testing_stub_enabled():
        for idx in range(target_count):
            yield _attach_quality_score(
                _call_testing_stub(brief or "Premium burst", seed_val + idx, f"PREMIUM BURST TEST STUB {idx + 1}"),
                "premium_burst",
            )
        return
    if not GEMINI_API_KEY:
        yield {"error": "Premium burst requires GEMINI_API_KEY"}
        return

    targets = []
    for idx in range(target_count):
        site_seed = seed_val + ((idx + 1) * 7919)
        target = _premium_experience_target(site_seed)
        target["site_index"] = idx + 1
        target["seed"] = site_seed
        targets.append(target)

    matrix_b64 = _get_design_matrix_b64()
    parts: List[Dict[str, Any]] = [{"text": _build_premium_burst_prompt(brief or "", seed_val, targets)}]
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})
    generation_config: Dict[str, Any] = {
        "temperature": 1.0,
        "maxOutputTokens": GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS or GEMINI_MAX_OUTPUT_TOKENS,
    }
    if GEMINI_THINKING_LEVEL:
        generation_config["thinkingConfig"] = {"thinkingLevel": GEMINI_THINKING_LEVEL}
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config,
    }
    endpoints = [GEMINI_STREAM_ENDPOINT]
    if GEMINI_FALLBACK_STREAM_ENDPOINT:
        endpoints.append(GEMINI_FALLBACK_STREAM_ENDPOINT)

    for endpoint_idx, endpoint in enumerate(endpoints):
        label = "primary" if endpoint_idx == 0 else "fallback"
        try:
            resp = requests.post(
                endpoint,
                params={"key": GEMINI_API_KEY},
                json=body,
                timeout=LLM_TIMEOUT_SECS,
                stream=True,
            )
        except Exception as exc:
            logging.warning("Gemini premium burst %s request error: %r", label, exc)
            continue
        if resp.status_code != 200:
            logging.warning("Gemini premium burst %s HTTP %s: %s", label, resp.status_code, resp.text[:400])
            continue
        full_text = ""
        emitted: Set[int] = set()
        emitted_count = 0
        for text_chunk in _iter_gemini_stream_text(resp):
            full_text += text_chunk
            for index, html_block in extract_completed_premium_burst_sites(full_text):
                if index in emitted:
                    continue
                emitted.add(index)
                try:
                    doc = _normalize_doc({"kind": "full_page_html", "html": html_block})
                except Exception as exc:
                    logging.warning("Premium burst skipped invalid site %s: %r", index, exc)
                    if include_rejected:
                        yield _premium_burst_rejected_payload(index=index, reason=f"invalid doc: {exc!r}")
                    continue
                issues = _preflight_doc(doc)
                if _preflight_has_blocking_issues(issues):
                    logging.warning(
                        "Premium burst skipped preflight-blocked site %s (%d issues): %s",
                        index,
                        len(issues),
                        _summarize_preflight_issues(issues),
                    )
                    if include_rejected:
                        yield _premium_burst_rejected_payload(
                            index=index,
                            reason="preflight blocked",
                            doc=_annotate_preflight_doc(doc, issues),
                            issues=issues,
                        )
                    continue
                if issues:
                    doc = _annotate_preflight_doc(doc, issues)
                scored = _attach_quality_score(doc, "premium_burst")
                quality = (scored.get("ndw_debug") or {}).get("quality_score") or {}
                rejection = _premium_burst_rejection(scored, quality)
                if rejection:
                    logging.warning("Premium burst skipped low-quality site %s: %s", index, rejection)
                    if include_rejected:
                        yield _premium_burst_rejected_payload(
                            index=index,
                            reason=rejection,
                            doc=scored,
                            quality=quality,
                        )
                    continue
                plan = targets[index - 1] if 0 < index <= len(targets) else {}
                debug = dict(scored.get("ndw_debug") or {})
                debug["generation_mode"] = "premium_burst"
                debug["premium_burst_index"] = index
                debug["premium_plan"] = plan
                debug["experience_quality"] = score_experience(scored, plan)
                scored["ndw_debug"] = debug
                yield scored
                emitted_count += 1
                if emitted_count >= target_count:
                    return
        if emitted_count:
            return
        logging.warning("Gemini premium burst %s produced no valid sites; text_len=%d", label, len(full_text))
    yield {"error": "Premium burst failed"}


def _premium_experience_target(seed: int) -> Dict[str, Any]:
    cell = choose_experience_cell(seed)
    cell_key = f"{cell['experience_archetype']}:{cell['primary_loop_type']}"
    return {
        **cell,
        "semantic_anchors": select_semantic_anchors(seed, cell_key),
    }


def _build_premium_plan_prompt(brief: str, seed: int, experience_target: Optional[Dict[str, Any]] = None) -> str:
    novelty = novelty_summary()
    target = experience_target if isinstance(experience_target, dict) else _premium_experience_target(seed)
    return f"""
{_vision_grounding_note()}
Plan one premium random interactive world/artifact.
Return JSON only matching the provided schema.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}

Goals:
- Choose one strong art direction instead of averaging multiple styles.
- Use the local design kit manifest below. Select concrete keys from it.
- Your output must explicitly choose palette_key, layout_key, motion_preset, overlay_key, display_font_key, and body_font_key.
- Pick one signature interaction and one signature motion system.
- Favor depth, atmosphere, and intentional hierarchy over generic product UI.
- Avoid recent visual trends from the novelty summary.
- Prefer forms beyond dashboards: spatial maps, playable instruments, living posters, simulators, kinetic editorials, fictional tools, tactile panels, or weird civic systems.
- Avoid a single centered card unless the chosen layout explicitly calls for it.
- Fill prompt_genome with a compact creative mutation for this generation only. Do not mutate runtime rules, output schema, allowed libraries, cleanup rules, or asset policy.
- Fill fingerprint with how this plan should be remembered after serving.
- Treat the experience target below as mandatory positive steering. Do not merely style around it; make it the behavior of the page.
- Fill semantic_translation by translating every semantic anchor into visual_role, interaction_role, content_role, and motion_role.
- The primary_loop is the core product contract: user_action, visible_response, state_change, reward_or_payoff, and continue_reason must be specific.
- The onboarding_cue must be visible in the generated page. The first interaction must visibly change page state.
- Fill mobile_interaction with a specific touch/small-screen fallback. Fill reset_or_replay with a visible replay affordance.

Experience target:
{json.dumps(target, separators=(",", ":"), ensure_ascii=True)}

Novelty summary from recently served pages:
{json.dumps(novelty, separators=(",", ":"), ensure_ascii=True)}

Local design kit manifest:
{compact_design_kit_manifest()}
"""


def _build_premium_page_prompt(
    brief: str,
    seed: int,
    plan: Dict[str, Any],
    retry_note: str = "",
) -> str:
    retry_block = f"\nRetry note:\n- {retry_note}\n" if retry_note else ""
    return f"""
{_vision_grounding_note()}
Build one premium interactive web experience.
	Use one-shot meta-correction. Output in this exact order:
	<thinking>Brief semantic plan, selected local libraries/assets, and one risk to avoid.</thinking>
	<draft>Initial complete HTML draft.</draft>
	<self_review>Answer the hard reject checklist below, then list concrete fixes applied before final HTML.</self_review>
```html
<!doctype html>
...
```

Only the final fenced html block will be served. Do not output JSON.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}

Approved premium plan (follow exactly):
{json.dumps(plan, indent=2)}

Experience contract:
- The visitor role, visitor goal, onboarding cue, and first interaction from the plan must be visible in the page.
- The primary loop must be implemented, not just described. User input must update visible state.
- The semantic_translation must drive interaction, content, motion, and visual treatment.
- Include reset/replay if the plan declares it.
- Include a mobile fallback matching mobile_interaction.

Local design kit manifest:
{compact_design_kit_manifest()}

Premium build requirements:
- Use at least one local design-kit asset or font selection from the approved plan.
- A visible first paint is mandatory. The page must look alive before interaction.
- Deliver one signature motion moment such as parallax drift, layered reveal, kinetic meter motion, or a restrained Three.js scene.
- Keep controls readable and intentional; do not revert to a generic marketing-site shell.
- If you include local fonts, use `<link rel="stylesheet" href="/static/design-kit/fonts.css">`.
- If you use overlays, reference `/static/design-kit/overlays/...` paths exactly.
	- Three.js must use the local import map style only: `import * as THREE from '/static/vendor/three.module.js';`.
	- Since the app renders this HTML in an iframe, no host cleanup code is required; still avoid memory leaks inside the page.
	- The final fenced block must be a complete document with `<html>`, `<head>`, and `<body>`.
	{retry_block}

	Hard reject self-review checklist:
	{PREMIUM_SELF_REVIEW_CHECKLIST}
	
	{HARD_RUNTIME_RULES}

{PREMIUM_STYLE_GUIDANCE}
"""


def _call_gemini_premium_plan(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    del user_key
    matrix_b64 = _get_design_matrix_b64()
    experience_target = _premium_experience_target(seed)
    parts: List[Dict[str, Any]] = [{"text": _build_premium_plan_prompt(brief, seed, experience_target)}]
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})
    out = _call_gemini_structured(parts, PREMIUM_PLAN_SCHEMA, temperature=0.8, max_output_tokens=4096)
    if isinstance(out, dict):
        out.setdefault("experience_archetype", experience_target["experience_archetype"])
        out.setdefault("primary_loop_type", experience_target["primary_loop_type"])
        out.setdefault("semantic_anchors", experience_target["semantic_anchors"])
    return out if isinstance(out, dict) else None


def _call_gemini_premium_build(
    brief: str,
    seed: int,
    plan: Dict[str, Any],
    *,
    retry_note: str = "",
) -> Optional[Dict[str, Any]]:
    matrix_b64 = _get_design_matrix_b64()
    parts: List[Dict[str, Any]] = [{"text": _build_premium_page_prompt(brief, seed, plan, retry_note)}]
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})
    text = _call_gemini_text(
        parts,
        temperature=1.0,
        max_output_tokens=GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS or None,
    )
    blocks = extract_final_html_blocks(text or "")
    if not blocks:
        return None
    return {"kind": "full_page_html", "html": blocks[-1]}


def _extract_gemini_text(payload: Dict[str, Any]) -> Optional[str]:
    try:
        candidates = payload.get("candidates") or []
        best_text = ""
        for cand in candidates:
            content = cand.get("content") or {}
            parts = content.get("parts") or []
            text_parts: list[str] = []
            for part in parts:
                txt = part.get("text")
                if isinstance(txt, str):
                    text_parts.append(txt)
            if text_parts:
                joined = "".join(text_parts)
                if joined.strip() and len(joined) > len(best_text):
                    best_text = joined
                continue
            for part in parts:
                function_call = part.get("functionCall")
                if isinstance(function_call, dict):
                    args = function_call.get("arguments")
                    if isinstance(args, str) and args.strip():
                        return args
                    try:
                        return json.dumps(function_call, ensure_ascii=False)
                    except Exception:
                        pass
                data_blob = part.get("data") or part.get("json") or part.get("structValue")
                if data_blob:
                    try:
                        return json.dumps(data_blob, ensure_ascii=False)
                    except Exception:
                        pass
        if best_text:
            return best_text
    except Exception:
        pass
    return None


def _log_gemini_stream_debug(
    full_text: str,
    parsed_docs: int,
    finish_reasons: Set[str],
    prompt_feedback: Optional[Dict[str, Any]],
    safety_ratings: List[Any],
) -> None:
    if not GEMINI_STREAM_DEBUG:
        return
    text = full_text or ""
    length = len(text)
    max_chars = max(200, int(GEMINI_STREAM_DEBUG_CHARS or 0))
    head = text[:max_chars]
    tail = text[-max_chars:] if length > max_chars else ""
    block_reason = None
    if isinstance(prompt_feedback, dict):
        block_reason = prompt_feedback.get("blockReason")
    logging.warning(
        "Gemini stream debug: len=%d parsed_docs=%d finishReasons=%s blockReason=%s head=%s",
        length,
        parsed_docs,
        sorted(finish_reasons),
        block_reason,
        head,
    )
    if tail and tail != head:
        logging.warning("Gemini stream debug tail: %s", tail)
    if safety_ratings:
        logging.warning("Gemini stream debug safetyRatings: %s", safety_ratings[:3])
    if GEMINI_STREAM_DEBUG_WRITE:
        try:
            os.makedirs(GEMINI_STREAM_DEBUG_DIR, exist_ok=True)
            path = os.path.join(
                GEMINI_STREAM_DEBUG_DIR,
                f"gemini_stream_{int(time.time() * 1000)}.txt",
            )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            logging.warning("Gemini stream debug saved: %s", path)
        except Exception as exc:
            logging.warning("Gemini stream debug write failed: %r", exc)
