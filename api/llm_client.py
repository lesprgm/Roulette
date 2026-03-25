from __future__ import annotations
import json
import logging
import os
import random
import threading
import time
from typing import Any, Dict, Optional, Tuple, List, Set
import requests
from api import dedupe
from api.design_kit import DESIGN_KIT_MANIFEST, compact_design_kit_manifest, compact_fast_design_kit_manifest
from api.llm_parsing import (
    _extract_completed_objects_from_array,
    _json_from_text,
    _normalize_doc,
    _repair_json_loose,
)
from api.preflight import annotate_doc as _annotate_preflight_doc
from api.preflight import first_js_syntax_error as _first_js_syntax_error
from api.preflight import has_blocking_issues as _preflight_has_blocking_issues
from api.preflight import preflight_doc as _preflight_doc
from api.llm_prompts import (
    _batch_review_schema,
    _build_batch_review_prompt,
    _build_review_prompt,
    _gemini_batch_review_schema,
    _gemini_review_schema,
    _review_schema,
)
from api.quality import PREMIUM_SCORE_THRESHOLD, score_page_doc

def _openrouter_repair_to_schema(
    raw_text: str,
    schema: Dict[str, Any],
    *,
    name: str,
    label: str,
    max_tokens: int = 16000,
) -> Optional[Dict[str, Any]]:
    """Best-effort JSON repair via OpenRouter Structured Outputs.

    Used when Gemini returns truncated/unparseable JSON for compliance review. We ask a
    separate model to *only* emit a schema-valid JSON object.
    """
    if COMPLIANCE_GEMINI_ONLY:
        return None
    if not OPENROUTER_API_KEY:
        return None
    model = (os.getenv("OPENROUTER_REPAIR_MODEL", "").strip() or OPENROUTER_REVIEW_MODEL or OPENROUTER_MODEL).strip()
    if not model:
        return None
    t = (raw_text or "").strip()
    if not t:
        return None
    # Keep prompts bounded; repair is about structure, not full fidelity.
    if len(t) > 120_000:
        t = t[:80_000] + "\n\n...<snip>...\n\n" + t[-40_000:]

    prompt = (
        "You are a JSON repair/canonicalization tool.\n"
        "You will be given a possibly truncated or malformed JSON-ish response.\n"
        "Your job: output ONE valid JSON object that conforms EXACTLY to the given JSON Schema.\n"
        "- Output JSON only. No markdown. No explanations.\n"
        "- Preserve indices/meaning when present; do not invent new indices.\n"
        "- If parts are missing, use conservative defaults that satisfy the schema.\n\n"
        "RAW INPUT (may be invalid/truncated):\n"
        f"{t}\n"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max(1024, min(int(max_tokens), 60000)),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "schema": schema,
                "strict": True,
            },
        },
    }
    try:
        resp = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=body, timeout=max(LLM_TIMEOUT_SECS, 120))
    except Exception as exc:
        logging.warning("OpenRouter repair request error (%s): %r", label, exc)
        return None
    if resp.status_code != 200:
        try:
            msg = resp.text[:400]
        except Exception:
            msg = str(resp.status_code)
        logging.warning("OpenRouter repair HTTP %s (%s): %s", resp.status_code, label, msg)
        return None
    try:
        payload = resp.json()
    except Exception as exc:
        logging.warning("OpenRouter repair non-JSON HTTP body (%s): %r", label, exc)
        return None
    text = _openrouter_extract_content(payload)
    if not text or not isinstance(text, str):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        try:
            parsed = _json_from_text(text)
        except Exception:
            logging.warning("OpenRouter repair response unparsable (%s): %s", label, text[:200])
            return None
    return parsed if isinstance(parsed, dict) else None


def _testing_stub_enabled() -> bool:
    """Return True when pytest is running and keys match the original environment values."""
    if not os.getenv("PYTEST_CURRENT_TEST"):
        return False
    if os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}:
        return False
    # If no providers are configured, don't hide failures behind a stub.
    if not (OPENROUTER_API_KEY or GROQ_API_KEY or GEMINI_API_KEY):
        return False
    if OPENROUTER_API_KEY != _ENV_OPENROUTER_API_KEY:
        return False
    if GROQ_API_KEY != _ENV_GROQ_API_KEY:
        return False
    if GEMINI_API_KEY != _ENV_GEMINI_API_KEY:
        return False
    return True
log = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-4.7-flash").strip()
OPENROUTER_FALLBACK_MODEL_1 = os.getenv("OPENROUTER_FALLBACK_MODEL_1", "google/gemma-3n-e2b-it:free").strip()
OPENROUTER_FALLBACK_MODEL_2 = os.getenv("OPENROUTER_FALLBACK_MODEL_2", "deepseek/deepseek-chat-v3.1:free").strip()
OPENROUTER_REVIEW_MODEL = os.getenv("OPENROUTER_REVIEW_MODEL", "").strip()
try:
    OPENROUTER_REVIEW_MAX_TOKENS = int(os.getenv("OPENROUTER_REVIEW_MAX_TOKENS", "4096"))
except Exception:
    OPENROUTER_REVIEW_MAX_TOKENS = 4096
_ENV_OPENROUTER_API_KEY = OPENROUTER_API_KEY
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
FORCE_OPENROUTER_ONLY = os.getenv("FORCE_OPENROUTER_ONLY", "0").lower() in {"1", "true", "yes", "on"}
GEMINI_ONLY = os.getenv("GEMINI_ONLY", "0").lower() in {"1", "true", "yes", "on"}
COMPLIANCE_GEMINI_ONLY = os.getenv("COMPLIANCE_GEMINI_ONLY", "0").lower() in {"1", "true", "yes", "on"}

# Groq (OpenAI-compatible) fallback provider
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
_ENV_GROQ_API_KEY = GROQ_API_KEY
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

_OPENROUTER_BACKOFF_LOCK = threading.Lock()
_OPENROUTER_BACKOFF_UNTIL = 0.0
_OPENROUTER_BACKOFF_DELAY = 0.0
try:
    _OPENROUTER_BACKOFF_INITIAL = float(os.getenv("OPENROUTER_BACKOFF_INITIAL", "3.0") or 3.0)
except Exception:
    _OPENROUTER_BACKOFF_INITIAL = 3.0
try:
    _OPENROUTER_BACKOFF_MAX = float(os.getenv("OPENROUTER_BACKOFF_MAX", "45.0") or 45.0)
except Exception:
    _OPENROUTER_BACKOFF_MAX = 45.0
_OPENROUTER_BACKOFF_FACTOR = 1.5





def _openrouter_sleep_if_needed() -> None:
    now = time.time()
    wait_for = 0.0
    with _OPENROUTER_BACKOFF_LOCK:
        if _OPENROUTER_BACKOFF_UNTIL > now:
            wait_for = _OPENROUTER_BACKOFF_UNTIL - now
    if wait_for > 0:
        logging.info("OpenRouter backoff active; waiting %.2fs before next request", wait_for)
        try:
            time.sleep(min(wait_for, _OPENROUTER_BACKOFF_MAX))
        except Exception:
            pass


def _openrouter_register_rate_limit(retry_after: Optional[str]) -> None:
    delay = None
    if retry_after:
        try:
            delay = float(retry_after)
        except Exception:
            delay = None
    global _OPENROUTER_BACKOFF_DELAY, _OPENROUTER_BACKOFF_UNTIL
    with _OPENROUTER_BACKOFF_LOCK:
        base = _OPENROUTER_BACKOFF_DELAY or _OPENROUTER_BACKOFF_INITIAL
        if delay is None:
            delay = base * _OPENROUTER_BACKOFF_FACTOR
        delay = max(_OPENROUTER_BACKOFF_INITIAL, min(delay, _OPENROUTER_BACKOFF_MAX))
        _OPENROUTER_BACKOFF_DELAY = delay
        _OPENROUTER_BACKOFF_UNTIL = time.time() + delay
        logging.warning("OpenRouter rate limited; backing off for %.2fs", delay)


def _openrouter_reset_backoff() -> None:
    global _OPENROUTER_BACKOFF_DELAY, _OPENROUTER_BACKOFF_UNTIL
    with _OPENROUTER_BACKOFF_LOCK:
        _OPENROUTER_BACKOFF_DELAY = 0.0
        _OPENROUTER_BACKOFF_UNTIL = 0.0



try:
    TEMPERATURE = float(os.getenv("TEMPERATURE", "1.5"))
except Exception:
    TEMPERATURE = 1.5

# Burst generation: number of sites requested from Gemini in one streaming call.
# This must match the JSON schema and prompt instructions in generate_page_burst().
try:
    BURST_SITE_COUNT = int(os.getenv("BURST_SITE_COUNT", "20"))
except Exception:
    BURST_SITE_COUNT = 20
BURST_SITE_COUNT = max(1, min(BURST_SITE_COUNT, 50))

# Token and timeout configuration
# Defaults favor longer generations; adjust via .env if provider rejects
try:
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "15000"))
except Exception:
    LLM_MAX_TOKENS = 15000
_openrouter_max_tokens_raw = os.getenv("OPENROUTER_MAX_TOKENS", "").strip()
if _openrouter_max_tokens_raw:
    try:
        OPENROUTER_MAX_TOKENS = int(_openrouter_max_tokens_raw)
    except Exception:
        OPENROUTER_MAX_TOKENS = None
else:
    OPENROUTER_MAX_TOKENS = None
try:
    LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "105"))
except Exception:
    LLM_TIMEOUT_SECS = 105
try:
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", str(LLM_MAX_TOKENS)))
except Exception:
    GROQ_MAX_TOKENS = LLM_MAX_TOKENS
_DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 140000
try:
    GEMINI_MAX_OUTPUT_TOKENS = int(
        os.getenv("GEMINI_MAX_OUTPUT_TOKENS", str(_DEFAULT_GEMINI_MAX_OUTPUT_TOKENS))
    )
except Exception:
    GEMINI_MAX_OUTPUT_TOKENS = _DEFAULT_GEMINI_MAX_OUTPUT_TOKENS
GEMINI_STREAM_DEBUG = os.getenv("GEMINI_STREAM_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
try:
    GEMINI_STREAM_DEBUG_CHARS = int(os.getenv("GEMINI_STREAM_DEBUG_CHARS", "4000"))
except Exception:
    GEMINI_STREAM_DEBUG_CHARS = 4000
GEMINI_STREAM_DEBUG_WRITE = os.getenv("GEMINI_STREAM_DEBUG_WRITE", "0").lower() in {"1", "true", "yes", "on"}
GEMINI_STREAM_DEBUG_DIR = os.getenv("GEMINI_STREAM_DEBUG_DIR", "cache/gemini_stream").strip()
try:
    GEMINI_REVIEW_RETRY_ATTEMPTS = int(os.getenv("GEMINI_REVIEW_RETRY_ATTEMPTS", "2"))
except Exception:
    GEMINI_REVIEW_RETRY_ATTEMPTS = 2
try:
    GEMINI_REVIEW_RETRY_DELAY = float(os.getenv("GEMINI_REVIEW_RETRY_DELAY", "1.5"))
except Exception:
    GEMINI_REVIEW_RETRY_DELAY = 1.5
try:
    GEMINI_REVIEW_BACKOFF_SECS = int(os.getenv("GEMINI_REVIEW_BACKOFF_SECS", "300"))
except Exception:
    GEMINI_REVIEW_BACKOFF_SECS = 300
_GEMINI_REVIEW_BACKOFF_UNTIL = 0.0
_GEMINI_REVIEW_BACKOFF_LOCK = threading.Lock()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_REVIEW_API_KEY = os.getenv("GEMINI_REVIEW_API_KEY", "").strip()
_ENV_GEMINI_API_KEY = GEMINI_API_KEY
GEMINI_REVIEW_MODEL = os.getenv("GEMINI_REVIEW_MODEL", "gemini-1.5-flash-latest").strip()
GEMINI_REVIEW_ENABLED = os.getenv("GEMINI_REVIEW_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
GEMINI_REVIEW_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_REVIEW_MODEL}:generateContent"
    if GEMINI_REVIEW_MODEL
    else ""
)

GEMINI_GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-3-flash-preview").strip()
GEMINI_GENERATION_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_GENERATION_MODEL}:generateContent"
)
GEMINI_STREAM_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_GENERATION_MODEL}:streamGenerateContent"
)
"""
This module now only calls the LLM. No local library or stub fallbacks.
If generation fails, we return {"error": "..."} and the API returns 200 with that body,
or 503 earlier in the /generate endpoint if credentials are missing.
"""

def status() -> Dict[str, Any]:
    reviewer = None
    provider = _review_provider()
    if provider == "openrouter" and _openrouter_review_active():
        reviewer = "openrouter"
    elif provider == "gemini" and _gemini_review_active():
        reviewer = "gemini"
    if _testing_stub_enabled():
        return {
            "provider": None,
            "model": None,
            "has_token": False,
            "using": "stub",
            "testing": True,
            "reviewer": reviewer,
        }
    fallback_providers = _fast_fallback_providers()
    if GEMINI_API_KEY and not FORCE_OPENROUTER_ONLY:
        return {
            "provider": "gemini",
            "model": GEMINI_GENERATION_MODEL,
            "has_token": True,
            "using": "gemini-fast",
            "fast_primary": "gemini-burst",
            "fast_fallbacks": fallback_providers,
            "reviewer": reviewer,
        }
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {
            "provider": "openrouter",
            "model": OPENROUTER_MODEL,
            "has_token": bool(OPENROUTER_API_KEY),
            "using": "openrouter-fallback",
            "fast_primary": "fallback-only",
            "fast_fallbacks": fallback_providers,
            "reviewer": reviewer,
        }
    if GROQ_API_KEY:
        return {
            "provider": "groq",
            "model": GROQ_MODEL,
            "has_token": True,
            "using": "groq-fallback",
            "fast_primary": "fallback-only",
            "fast_fallbacks": fallback_providers,
            "reviewer": reviewer,
        }
    return {
        "provider": None,
        "model": None,
        "has_token": False,
        "using": "stub",
        "reviewer": reviewer,
    }


def probe() -> Dict[str, Any]:
    if _testing_stub_enabled():
        return {"ok": False, "using": "stub", "testing": True}
    if GEMINI_API_KEY and not FORCE_OPENROUTER_ONLY:
        return {"ok": True, "using": "gemini-fast"}
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {"ok": bool(OPENROUTER_API_KEY), "using": "openrouter-fallback"}
    if GROQ_API_KEY:
        return {"ok": True, "using": "groq-fallback"}
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


def _call_fast_gemini_page(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the first valid Gemini burst page for fast mode, or None."""
    if not GEMINI_API_KEY:
        return None
    try:
        burst_iter = generate_page_burst(brief, seed, user_key=user_key, gemini_only=True)
        page = next(burst_iter, None)
    except Exception as exc:
        logging.warning("Gemini fast path failed before first page: %r", exc)
        return None
    if not isinstance(page, dict) or page.get("error"):
        return None
    return page


def _fast_fallback_providers(providers_override: Optional[List[str]] = None) -> List[str]:
    providers: List[str] = []
    explicit = [p for p in (providers_override or []) if p in {"openrouter", "groq"}]
    if explicit:
        candidates = explicit
    else:
        candidates = []
        if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
            candidates.append("openrouter")
        if GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
            candidates.append("groq")
    for provider in candidates:
        if provider == "openrouter" and (OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY):
            providers.append("openrouter")
        elif provider == "groq" and GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
            providers.append("groq")
    return providers


def _call_fast_fallback_page(
    brief: str,
    seed: int,
    category_note: str,
    *,
    providers_override: Optional[List[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    providers = _fast_fallback_providers(providers_override)
    for provider in providers:
        logging.warning("llm attempting fallback provider=%s", provider)
        if provider == "openrouter":
            doc = _call_openrouter_for_page(brief, seed, category_note)
        else:
            doc = _call_groq_for_page(brief, seed, category_note)
        if doc:
            logging.warning("llm chosen fallback provider=%s", provider)
            return doc, provider
    return None, None


def _explicit_gemini_requested(providers_override: Optional[List[str]]) -> bool:
    if FORCE_OPENROUTER_ONLY:
        return False
    if not providers_override:
        return True
    return "gemini" in providers_override


def _fetch_fast_candidate(
    brief: str,
    seed: int,
    category_note: str,
    *,
    user_key: Optional[str] = None,
    providers_override: Optional[List[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    route_labels: List[str] = []
    if _explicit_gemini_requested(providers_override):
        route_labels.append("gemini-burst")
    route_labels.extend(_fast_fallback_providers(providers_override))
    logging.warning("llm fast_route=%s force_openrouter_only=%s", route_labels, FORCE_OPENROUTER_ONLY)

    if _explicit_gemini_requested(providers_override):
        logging.warning("llm attempting provider=gemini-burst")
        doc = _call_fast_gemini_page(brief, seed, user_key=user_key)
        if doc:
            logging.warning("llm chosen provider=gemini-burst")
            return doc, "gemini-burst"

    return _call_fast_fallback_page(
        brief,
        seed,
        category_note,
        providers_override=providers_override,
    )


def generate_page(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
    run_review: bool = True,
    providers_override: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return a doc in one of the two accepted shapes or {error}.

    Behaviors:
    - Empty or auto brief lets the model invent a theme.
    - Seed only used for palette/layout hinting; not required.
    """
    auto_cues = {"", "auto", "random", "surprise me"}
    brief_str = (brief or "").strip()
    is_auto = brief_str.lower() in auto_cues
    if not brief_str or is_auto:
        brief_str = ""  
    seed_val = int(seed or 0)
    if not seed_val:
        seed_val = random.randint(1, 10_000_000)

    category_note = _next_category_note(user_key)

    if _testing_stub_enabled():
        return _call_testing_stub(brief_str, seed_val, category_note)

    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        attempts += 1
        doc: Optional[Dict[str, Any]] = None
        doc, _provider = _fetch_fast_candidate(
            brief_str,
            seed_val,
            category_note,
            user_key=user_key,
            providers_override=providers_override,
        )
        if not doc:
            logging.warning("All providers failed; returning error doc.")
            return {"error": "Model generation failed"}

        skip_dedupe = bool(os.getenv("PYTEST_CURRENT_TEST"))
        initial_sig = ""
        if not skip_dedupe:
            initial_sig = dedupe.signature_for_doc(doc)
            if initial_sig and dedupe.has(initial_sig):
                logging.info("Duplicate app signature encountered; retrying another generation (attempt %d)", attempts)
                doc = None
                seed_val = (seed_val + 7919) % 10_000_019
                continue

        review_data: Optional[Dict[str, Any]] = None
        if run_review:
            review_data, corrected_doc, review_ok = _maybe_run_compliance_review(doc, brief_str, category_note)
            if corrected_doc is not None:
                try:
                    doc = _normalize_doc(corrected_doc)
                except Exception as exc:
                    logging.warning("Compliance review returned invalid corrected doc: %r", exc)
                    doc = None
                    seed_val = (seed_val + 7919) % 10_000_019
                    continue
                logging.info("Compliance review applied corrections to doc (attempt %d)", attempts)
            if review_data:
                logging.info(
                    "Compliance review summary ok=%s issues=%s",
                    review_data.get("ok"),
                    len(review_data.get("issues", [])),
                )
            if not review_ok:
                logging.info("Compliance review rejected doc; retrying another generation (attempt %d)", attempts)
                doc = None
                seed_val = (seed_val + 7919) % 10_000_019
                continue
            if review_data:
                doc = dict(doc)
                doc["review"] = review_data
        preflight_issues = _preflight_doc(doc)
        if preflight_issues:
            doc = _annotate_preflight_doc(doc, preflight_issues)
        if _preflight_has_blocking_issues(preflight_issues):
            logging.info("Preflight rejected doc; retrying another generation (attempt %d)", attempts)
            doc = None
            seed_val = (seed_val + 7919) % 10_000_019
            continue
        final_sig = ""
        if not skip_dedupe:
            final_sig = dedupe.signature_for_doc(doc)
            if final_sig and dedupe.has(final_sig):
                duplicate_msg = "Compliance-adjusted doc duplicate" if run_review else "Unreviewed doc duplicate"
                logging.info("%s; retrying another generation (attempt %d)", duplicate_msg, attempts)
                doc = None
                seed_val = (seed_val + 7919) % 10_000_019
                continue
        if final_sig:
            dedupe.add(final_sig)
        return _attach_quality_score(doc, "fast")
    return doc or {"error": "Model generation failed"}


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

    best_doc: Optional[Dict[str, Any]] = None
    best_score = -1
    retry_note = ""
    for _attempt in range(2):
        raw_doc = _call_gemini_premium_build(brief_str, seed_val, plan, retry_note=retry_note)
        if not isinstance(raw_doc, dict):
            retry_note = (
                "The previous build was invalid or empty. Keep the same plan, "
                "but simplify brittle code and make first paint more visually obvious."
            )
            continue
        try:
            doc = _normalize_doc(raw_doc)
        except Exception as exc:
            logging.warning("Premium build normalization failed: %r", exc)
            retry_note = (
                "The previous build failed normalization. Keep the same plan, but return one clean "
                "renderable doc with a complete html field and valid JSON only."
            )
            continue

        preflight_issues = _preflight_doc(doc)
        if preflight_issues:
            doc = _annotate_preflight_doc(doc, preflight_issues)
        scored = _attach_quality_score(doc, "premium")
        debug = dict(scored.get("ndw_debug") or {})
        debug["premium_plan"] = plan
        scored["ndw_debug"] = debug
        score = int(debug.get("quality_score", {}).get("score", 0))
        if score > best_score:
            best_doc = scored
            best_score = score

        if not _preflight_has_blocking_issues(preflight_issues) and score >= PREMIUM_SCORE_THRESHOLD:
            return scored

        retry_note = (
            "Keep the same plan, but improve reliability and visual depth. Fix any blocked selectors or cleanup issues. "
            "Avoid a generic centered card, make the hero more distinctive, and use the selected local design-kit assets more clearly."
        )

    return best_doc or {"error": "Premium generation failed"}


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


def _build_page_response_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string"},
            "title": {"type": "string"},
            "html": {"type": "string"},
            "css": {"type": "string"},
            "js": {"type": "string"},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "props": {
                            "type": "object",
                            "properties": {
                                "html": {"type": "string"},
                                "height": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "required": ["kind", "html"],
    }


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
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": TEMPERATURE if temperature is None else temperature,
            "maxOutputTokens": max_output_tokens or GEMINI_MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    try:
        resp = requests.post(
            endpoint or GEMINI_GENERATION_ENDPOINT,
            params={"key": GEMINI_API_KEY},
            json=body,
            timeout=LLM_TIMEOUT_SECS,
        )
    except Exception as exc:
        logging.warning("Gemini structured request error: %r", exc)
        return None

    if resp.status_code != 200:
        try:
            msg = resp.text[:400]
        except Exception:
            msg = str(resp.status_code)
        logging.warning("Gemini structured HTTP %s: %s", resp.status_code, msg)
        return None

    try:
        data = resp.json()
        text = _extract_gemini_text(data)
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return _json_from_text(text)
    except Exception as exc:
        logging.warning("Gemini structured extraction error: %r", exc)
        return None


def _build_fast_page_prompt(brief: str, seed: int, assignment_note: str) -> str:
    return f"""
{_vision_grounding_note()}
=== FAST MODE ASSIGNMENT ===
{assignment_note}
Follow the assignment axes exactly. Do not collapse back into a generic centered card.
================================

You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations. The first non-whitespace character MUST be '{{'.
The JSON MUST include a non-empty "html" field containing the complete <!doctype html> document.

Brief: {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""


def _build_fast_burst_prompt(brief: str, seed: int, assignments_text: str, target_docs: int) -> str:
    return f"""
{_vision_grounding_note()}
=== FAST MODE ASSIGNMENTS ===
{assignments_text}
Each site MUST follow its own assignment axes. Keep the sites visibly distinct in layout, motion grammar, and tone.
================================

You generate EXACTLY {target_docs} unique, self-contained interactive web apps as a JSON array.
Output valid JSON only. No backticks. No explanations. The first non-whitespace character MUST be '['.
Every item MUST include a non-empty "html" field containing a complete <!doctype html> document.

Brief: {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""


def _build_premium_plan_prompt(brief: str, seed: int) -> str:
    return f"""
{_vision_grounding_note()}
Plan one premium interactive web experience.
Return JSON only matching the provided schema.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}

Goals:
- Choose one strong art direction instead of averaging multiple styles.
- Use the local design kit manifest below. Select concrete keys from it.
- Your output must explicitly choose palette_key, layout_key, motion_preset, overlay_key, display_font_key, and body_font_key.
- Pick one signature interaction and one signature motion system.
- Favor depth, atmosphere, and intentional hierarchy over generic product UI.
- Avoid a single centered card unless the chosen layout explicitly calls for it.

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
Output valid JSON only. No backticks. No explanations. The first non-whitespace character MUST be '{{'.
Return a single renderable document. `full_page_html` is strongly preferred.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}

Approved premium plan (follow exactly):
{json.dumps(plan, indent=2)}

Local design kit manifest:
{compact_design_kit_manifest()}

Premium build requirements:
- Use at least one local design-kit asset or font selection from the approved plan.
- A visible first paint is mandatory. The page must look alive before interaction.
- Deliver one signature motion moment such as parallax drift, layered reveal, kinetic meter motion, or a restrained Three.js scene.
- Keep controls readable and intentional; do not revert to a generic marketing-site shell.
- If you include local fonts, use `<link rel="stylesheet" href="/static/design-kit/fonts.css">`.
- If you use overlays, reference `/static/design-kit/overlays/...` paths exactly.
{retry_block}

{OUTPUT_FORMATS}

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
    parts: List[Dict[str, Any]] = [{"text": _build_premium_plan_prompt(brief, seed)}]
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})
    out = _call_gemini_structured(parts, PREMIUM_PLAN_SCHEMA, temperature=0.8, max_output_tokens=4096)
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
    out = _call_gemini_structured(parts, _build_page_response_schema(), temperature=1.0)
    return out if isinstance(out, dict) else None


def _call_gemini_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call Gemini for page generation."""
    matrix_b64 = _get_design_matrix_b64()
    parts: List[Dict[str, Any]] = [{"text": _build_fast_page_prompt(brief, seed, category_note)}]
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})
    out = _call_gemini_structured(parts, _build_page_response_schema())
    if not isinstance(out, dict):
        return None
    try:
        return _normalize_doc(out)
    except Exception as exc:
        logging.warning("Gemini generation normalization error: %r", exc)
        return None


def _fallback_single(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    providers_override: Optional[List[str]] = None,
) -> Iterable[Dict[str, Any]]:
    doc = generate_page(brief, seed, user_key, providers_override=providers_override)
    if isinstance(doc, dict) and not doc.get("error"):
        if extra:
            debug = doc.get("ndw_debug")
            if not isinstance(debug, dict):
                debug = {}
            debug["gemini_feedback"] = extra
            doc["ndw_debug"] = debug
        yield doc
        return
    err = {"error": "Model generation failed"}
    if extra:
        err["ndw_debug"] = {"gemini_feedback": extra}
    yield err


def _fallback_burst(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
    target_docs: int = 20,
    providers_override: Optional[List[str]] = None,
) -> Iterable[Dict[str, Any]]:
    """Generate multiple docs when burst streaming is unavailable."""
    generated = 0
    attempts = 0
    max_attempts = max(target_docs, 1) * 2
    while generated < target_docs and attempts < max_attempts:
        attempts += 1
        doc = generate_page(
            brief,
            seed + attempts,
            user_key,
            providers_override=providers_override,
        )
        if not isinstance(doc, dict) or doc.get("error"):
            break
        yield doc
        generated += 1
    if generated == 0:
        yield {"error": "Model generation failed"}


def generate_page_burst(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
    gemini_only: bool = False,
) -> Iterable[Dict[str, Any]]:
    """Yield up to BURST_SITE_COUNT sites from a single Gemini streaming burst."""
    gemini_only = gemini_only or GEMINI_ONLY
    gemini_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    model = os.getenv("GEMINI_GENERATION_MODEL", GEMINI_GENERATION_MODEL).strip() or GEMINI_GENERATION_MODEL
    stream_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"

    if not gemini_key:
        if gemini_only:
            yield {"error": "Gemini-only mode: GEMINI_API_KEY missing"}
            return
        yield from _fallback_burst(brief, seed, user_key, target_docs=BURST_SITE_COUNT)
        return

    category_notes = [_next_category_note(user_key) for _ in range(BURST_SITE_COUNT)]
    target_docs = len(category_notes)
    matrix_b64 = _get_design_matrix_b64()
    
    parts: List[Dict[str, Any]] = []
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})

    assignments = "\n\n".join(
        f"SITE {i + 1}\n{category_notes[i]}" for i in range(len(category_notes))
    )
    parts.insert(0, {"text": _build_fast_burst_prompt(brief, seed, assignments, target_docs)})
    
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "array",
                "items": _build_page_response_schema(),
                "minItems": target_docs,
                "maxItems": target_docs,
            },
        },
    }

    try:
        resp = requests.post(
            stream_endpoint,
            params={"key": gemini_key},
            json=body,
            timeout=LLM_TIMEOUT_SECS,
            stream=True
        )
        if resp.status_code != 200:
            logging.warning("Gemini stream HTTP %s: %s", resp.status_code, resp.text[:200])
            if gemini_only:
                yield {"error": f"Gemini-only mode: stream HTTP {resp.status_code}"}
                return
            logging.warning("Gemini stream failed; falling back to OpenRouter/Groq")
            providers_override = None
            if resp.status_code in {429, 503}:
                providers_override = ["groq"]
            yield from _fallback_burst(
                brief,
                seed,
                user_key,
                target_docs=target_docs,
                providers_override=providers_override,
            )
            return

        full_text = ""
        last_obj_count = 0
        yielded_docs = 0
        prompt_feedback: Optional[Dict[str, Any]] = None
        finish_reasons: Set[str] = set()
        safety_ratings: List[Any] = []
        stop_stream = False
        
        # Buffer for accumulating multi-line JSON chunks
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
            
            # Simple state machine to find complete top-level objects in the stream array
            for char in chunk:
                buffer += char
                if char == '"' and not escape:
                    in_string = not in_string
                if in_string:
                    escape = (char == "\\") and not escape
                else:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        # If we closed a top-level object
                        if brace_count == 0 and buffer.strip():
                            # Clean up leading commas/brackets if present
                            clean_buf = buffer.strip()
                            if clean_buf.startswith(','): clean_buf = clean_buf[1:].strip()
                            if clean_buf.startswith('['): clean_buf = clean_buf[1:].strip()
                            if clean_buf.endswith(','): clean_buf = clean_buf[:-1].strip()
                            if clean_buf.endswith(']'): clean_buf = clean_buf[:-1].strip()
                            
                            try:
                                data = json.loads(clean_buf)
                                if isinstance(data, dict):
                                    pf = data.get("promptFeedback")
                                    if isinstance(pf, dict) and prompt_feedback is None:
                                        prompt_feedback = pf
                                    for cand in data.get("candidates") or []:
                                        fr = cand.get("finishReason")
                                        if isinstance(fr, str) and fr:
                                            finish_reasons.add(fr)
                                        sr = cand.get("safetyRatings")
                                        if sr:
                                            safety_ratings.append(sr)
                                t = _extract_gemini_text(data)
                                if t:
                                    full_text += t
                                else:
                                    logging.debug("Gemini chunk has no text: keys=%s", list(data.keys()))
                            except Exception as e:
                                logging.warning("Buffer parse error: %r | buf: %s", e, clean_buf[:200])
                                pass
                            
                            buffer = ""

            # Stream-parse objects from the array
            sites = _extract_completed_objects_from_array(full_text)
            for i in range(last_obj_count, len(sites)):
                try:
                    doc = _normalize_doc(sites[i])
                except Exception as exc:
                    logging.warning("Gemini stream skipped invalid doc: %r", exc)
                    last_obj_count += 1
                    continue
                preflight_issues = _preflight_doc(doc)
                if _preflight_has_blocking_issues(preflight_issues):
                    logging.warning("Gemini stream skipped preflight-blocked doc (%d issues)", len(preflight_issues))
                    last_obj_count += 1
                    continue
                if preflight_issues:
                    doc = _annotate_preflight_doc(doc, preflight_issues)
                yield _attach_quality_score(doc, "fast")
                last_obj_count += 1
                yielded_docs += 1
                if yielded_docs >= target_docs:
                    stop_stream = True
                    break
            if stop_stream:
                break

        _log_gemini_stream_debug(full_text, yielded_docs, finish_reasons, prompt_feedback, safety_ratings)
        if last_obj_count > target_docs:
            logging.warning(
                "Gemini stream produced %d items; expected %d",
                last_obj_count,
                target_docs,
            )
                
        if yielded_docs == 0:
            logging.warning("Gemini stream finished but 0 valid objects found. full_text len=%d", len(full_text))
            recovered_docs: List[Dict[str, Any]] = []
            if full_text.strip():
                try:
                    recovered = _json_from_text(full_text)
                    if isinstance(recovered, list):
                        for item in recovered:
                            try:
                                doc = _normalize_doc(item)
                                issues = _preflight_doc(doc)
                                if _preflight_has_blocking_issues(issues):
                                    continue
                                if issues:
                                    doc = _annotate_preflight_doc(doc, issues)
                                recovered_docs.append(_attach_quality_score(doc, "fast"))
                            except Exception as exc:
                                logging.warning("Gemini stream tolerant parse normalize error: %r", exc)
                    elif isinstance(recovered, dict):
                        doc = _normalize_doc(recovered)
                        issues = _preflight_doc(doc)
                        if not _preflight_has_blocking_issues(issues):
                            if issues:
                                doc = _annotate_preflight_doc(doc, issues)
                            recovered_docs.append(_attach_quality_score(doc, "fast"))
                except Exception as exc:
                    logging.warning("Gemini stream tolerant parse failed: %r", exc)
            if recovered_docs:
                logging.warning("Gemini stream tolerant parse recovered %d docs", len(recovered_docs))
                for doc in recovered_docs[:target_docs]:
                    yield doc
                return
            feedback = {
                "reason": "empty_stream",
                "blockReason": prompt_feedback.get("blockReason") if isinstance(prompt_feedback, dict) else None,
                "promptSafetyRatings": prompt_feedback.get("safetyRatings") if isinstance(prompt_feedback, dict) else None,
                "finishReasons": sorted(finish_reasons),
                "candidateSafetyRatings": safety_ratings[:3],
            }
            if prompt_feedback:
                logging.warning(
                    "Gemini stream promptFeedback blockReason=%s safetyRatings=%s",
                    prompt_feedback.get("blockReason"),
                    prompt_feedback.get("safetyRatings"),
                )
            if finish_reasons:
                logging.warning("Gemini stream finishReasons=%s", sorted(finish_reasons))
            if safety_ratings:
                logging.warning("Gemini stream candidate safetyRatings=%s", safety_ratings[:3])
            if gemini_only:
                yield {"error": "Gemini-only mode: stream produced no valid pages", "meta": feedback}
                return
            logging.warning("Gemini stream produced no valid pages; falling back to OpenRouter/Groq")
            yield from _fallback_single(brief, seed, user_key, extra=feedback)
                
    except Exception as e:
        logging.warning("Burst generation error: %r", e)
        if gemini_only:
            yield {"error": "Gemini-only mode: burst error"}
            return
        logging.warning("Gemini burst error; falling back to OpenRouter/Groq")
        yield from _fallback_burst(
            brief,
            seed,
            user_key,
            target_docs=BURST_SITE_COUNT,
            providers_override=["groq"],
        )


def _call_groq_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call Groq (OpenAI-compatible) and parse a page dict; None on failure."""
    temperature = TEMPERATURE
    prompt = _build_fast_page_prompt(brief, seed, category_note)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": max(1.1, min(1.3, float(temperature))),
        "top_p": 0.95,
        "max_tokens": GROQ_MAX_TOKENS,
    }
    # Try JSON mode if supported; retry without on 400
    wants_json_mode = True
    body_with_json = dict(body)
    body_with_json["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(GROQ_ENDPOINT, headers=headers, json=body_with_json, timeout=LLM_TIMEOUT_SECS)
    except Exception as e:
        logging.warning("Groq request error: %r", e)
        return None

    if resp.status_code == 400:
        # Retry without json mode
        try:
            resp = requests.post(GROQ_ENDPOINT, headers=headers, json=body, timeout=LLM_TIMEOUT_SECS)
        except Exception as e:
            logging.warning("Groq retry (no json mode) error: %r", e)
            return None

    if resp.status_code != 200:
        # Attempt a single fallback model on common failure modes
        fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
        raw = None
        try:
            raw = resp.text
        except Exception:
            raw = None

        lower = (raw or "").lower()
        should_try_fallback = False
        reason = None
        # 1) Explicit model issues (invalid/not found)
        if ("model" in lower) and (("not found" in lower) or ("invalid" in lower)):
            should_try_fallback = True
            reason = "model rejected"
        # 2) Rate limited — try a different model if configured
        elif resp.status_code == 429:
            should_try_fallback = True
            reason = "rate limited"

        if fallback_model and GROQ_MODEL != fallback_model and should_try_fallback:
            logging.warning("Groq model '%s' %s; retrying with fallback '%s'", GROQ_MODEL, reason or "failed", fallback_model)
            body_fallback = dict(body)
            body_fallback["model"] = fallback_model
            try:
                resp_fb = requests.post(GROQ_ENDPOINT, headers=headers, json=body_fallback, timeout=LLM_TIMEOUT_SECS)
            except Exception as e:
                logging.warning("Groq fallback model request error: %r", e)
                return None
            if resp_fb.status_code != 200:
                try:
                    msg = resp_fb.text[:400]
                except Exception:
                    msg = str(resp_fb.status_code)
                logging.warning("Groq HTTP %s after fallback: %s", resp_fb.status_code, msg)
                return None
            # Use fallback response as success
            resp = resp_fb
        else:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Groq HTTP %s: %s", resp.status_code, msg)
            return None

    try:
        data = resp.json()
    except Exception:
        logging.warning("Groq: non-JSON HTTP body")
        return None

    text: Optional[str]
    try:
        text = (data.get("choices", [{}])[0].get("message", {}).get("content"))
    except Exception:
        text = None
    if not text or not isinstance(text, str):
        logging.warning("Groq: empty response text")
        return None

    try:
        page = _json_from_text(text)
    except Exception as e:
        logging.warning("Groq: failed to extract JSON: %r", e)
        return None

    try:
        norm = _normalize_doc(page)
        if isinstance(norm, dict):
            return norm
    except Exception as e:
        logging.warning("Groq: normalization error: %r", e)
    return None




OUTPUT_FORMATS = """
FORMATS (prefer #2 for most outputs):
1. {"kind":"ndw_snippet_v1","title":"...","background":{"style":"css","class":""},"css":"...","html":"...","js":"..."}  Use only when a compact widget is clearly the best fit.
2. {"kind":"full_page_html","html":"<!doctype html>..."}  Preferred. Include complete head/body and inline CSS/JS.
3. {"components":[{"id":"hero","type":"custom","props":{"html":"...","height":360}}]}  Only when multiple iframe-style islands are unavoidable.
4. For immersive 3D or WebGL concepts, use full_page_html with `<script type="module">import * as THREE from 'three'; ...</script>`.
""".strip()

FAST_STYLE_GUIDANCE = """
FAST BUILD GUIDANCE:
- Start from the assigned layout, background token, motion token, and font pair before inventing extras.
- Ship a visible first paint immediately with a strong hero composition and one signature interaction.
- Avoid the generic centered-card shell and avoid falling back to bland dashboard chrome.
- Use layered surfaces, strong contrast, and at least two visual regions or one immersive full-viewport stage.
- Lucide is available globally. Use `<i data-lucide="icon-name"></i>` instead of raw SVG icon markup when you need icons.
""".strip()

PREMIUM_STYLE_GUIDANCE = """
PREMIUM BUILD GUIDANCE:
- Treat the approved plan as a creative director's brief.
- Use the selected layout, palette, motion preset, and overlay intentionally.
- Favor cinematic depth, layered parallax, responsive canvases, or restrained Three.js over flat static UI.
- Preserve clarity: strong hierarchy, readable controls, and no tone-on-tone text.
""".strip()

HARD_RUNTIME_RULES = """
GENERAL RULES:
- STRICT: No external scripts or styles via CDN. No external fonts/images/fetch. No iframes or document.write.
- Tailwind runtime is local; do not include CDN imports. GSAP and Lucide are already provided globally.
- Three.js is available locally in module scripts via `import * as THREE from 'three'`. Never import remote modules.
- Use the ID `ndw-content` for the main app container when you need a primary stage.
- Every interactive element referenced in JS must already exist in the DOM before scripts run.
- CONTROL CONSISTENCY: buttons and keyboard shortcuts must trigger the same function, not near-duplicates.
- If you create requestAnimationFrame loops, timers, observers, or Three.js renderers outside NDW.loop, call `NDW.registerCleanup(() => { ... })`.

DO NOT:
- Do not use inline event handlers (`onclick=""`, etc.) or global window timers.
- Do not reference external fonts, CDNs, or fetch remote data.
- Do not leave empty containers or placeholder text like TODO.
- Do not create duplicate IDs or register duplicate NDW.onPointer/onKey handlers inside loops.

SELF QA:
1. Pretend to click every button and verify the described behavior occurs.
2. Verify headings, instructions, and controls are visible on first paint.
3. Ensure result text never becomes `undefined`.
4. Check contrast and readability. No white-on-white, black-on-black, or muddy medium-on-medium text.
""".strip()

NDW_SDK_CHEAT_SHEET = """
NDW SDK CHEAT SHEET
=== FRAME LOOP ===
NDW.loop((dt) => { ... })  // dt = milliseconds since last frame. Required for games/animations.

=== INPUT ===
NDW.isPressed("ArrowUp")
NDW.isDown("ArrowLeft")
NDW.jump()    // alias: ArrowUp, Space, W
NDW.shot()    // alias: X, Z, mouse click
NDW.action()  // alias: Enter, Space, mouse click
NDW.pointer   // { x, y, down } - mouse/touch pointer state

=== AUDIO ===
NDW.audio.playTone(freq, durationMs, type, gain)

=== JUICE ===
NDW.juice.shake(intensity, durationMs)
NDW.particles.spawn({x, y, count, spread, color, size, life})
NDW.particles.update(dt, ctx)

=== CANVAS ===
const canvas = NDW.makeCanvas({parent: document.getElementById('ndw-content'), width: 800, height: 600});

=== MATH ===
NDW.utils.dist(x1, y1, x2, y2)
NDW.utils.angle(x1, y1, x2, y2)
NDW.utils.overlaps(objA, objB)
NDW.utils.lerp(a, b, t)
NDW.utils.clamp(v, min, max)
NDW.utils.rng(seed)

=== PERSISTENCE ===
NDW.utils.store.get("key")
NDW.utils.store.set("key", value)

=== HANDLERS ===
NDW.onKey((e) => { if (e.key === 'ArrowUp') jump(); });
NDW.onPointer((e) => { if (e.down) shoot(e.x, e.y); });
NDW.registerCleanup(() => { /* cancel timers, dispose renderers, remove observers */ });

JS GUARDRAILS:
- Wrap DOM queries inside DOMContentLoaded if scripts appear before the HTML.
- Declare every variable with const/let.
- Avoid setInterval/setTimeout for animation; use NDW.loop and dt.
- Keep physics frame-independent by using velocity * (dt / 1000).
""".strip()

FAST_DESIGN_KIT_GUIDANCE = f"""
FAST DESIGN-KIT MANIFEST:
{compact_fast_design_kit_manifest()}
- Select exactly one assigned background_token and exactly one assigned motion_token.
- If you use the font pair, include `<link rel="stylesheet" href="/static/design-kit/fonts.css">`.
- If you use the overlay implied by the background_token, reference `/static/design-kit/overlays/...` exactly.
""".strip()

_PAGE_SHAPE_HINT = "\n\n".join(
    [OUTPUT_FORMATS, FAST_STYLE_GUIDANCE, FAST_DESIGN_KIT_GUIDANCE, HARD_RUNTIME_RULES, NDW_SDK_CHEAT_SHEET]
)

PREMIUM_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "layout_archetype": {"type": "string", "enum": ["split_lens", "stage_focus", "bento_magazine", "immersive_poster"]},
        "motion_archetype": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["motion_presets"].keys())},
        "visual_density": {"type": "string", "enum": ["airy", "layered", "dense"]},
        "interaction_model": {"type": "string", "enum": ["pointer_reactive", "scroll_story", "tool_driven", "playful_loop"]},
        "rendering_mode": {"type": "string", "enum": ["dom", "canvas", "three", "hybrid"]},
        "tone": {"type": "string", "enum": ["luminous", "editorial", "playful", "brutalist_softened", "cinematic"]},
        "signature_interaction": {"type": "string"},
        "hero_treatment": {"type": "string"},
        "palette_key": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["palettes"].keys())},
        "layout_key": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["layouts"].keys())},
        "motion_preset": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["motion_presets"].keys())},
        "overlay_key": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["overlays"].keys())},
        "display_font_key": {"type": "string", "enum": ["display_orbit", "display_editorial", "display_grotesk"]},
        "body_font_key": {"type": "string", "enum": ["body_clean", "body_soft"]},
        "three_scene_key": {"type": "string", "enum": ["glass_orbit", "particle_ribbon", "terrain_glow"]},
        "art_direction": {"type": "string", "minLength": 12, "maxLength": 180},
    },
    "required": [
        "layout_archetype",
        "motion_archetype",
        "visual_density",
        "interaction_model",
        "rendering_mode",
        "tone",
        "signature_interaction",
        "hero_treatment",
        "palette_key",
        "layout_key",
        "motion_preset",
        "overlay_key",
        "display_font_key",
        "body_font_key",
        "three_scene_key",
        "art_direction",
    ],
}

_FAST_ASSIGNMENT_PRESETS = [
    {
        "heading": "FAST ASSIGNMENT (1/6): stage_focus + parallax_drift",
        "layout_archetype": "stage_focus",
        "motion_archetype": "parallax_drift",
        "visual_density": "layered",
        "interaction_model": "pointer_reactive",
        "rendering_mode": "dom",
        "tone": "luminous",
        "palette_key": "solar_pop",
        "layout_key": "stage_focus",
        "overlay_key": "noise_grid",
        "motion_preset": "parallax_drift",
        "background_token": "aurora_stage",
        "display_font_key": "display_orbit",
        "body_font_key": "body_clean",
        "hero_direction": "Build one large luminous stage with a floating control rail instead of stacked cards.",
        "interaction_signature": "Let the pointer tilt or shift layered planes while one hero control changes the scene.",
    },
    {
        "heading": "FAST ASSIGNMENT (2/6): split_lens + kinetic_meter",
        "layout_archetype": "split_lens",
        "motion_archetype": "kinetic_meter",
        "visual_density": "airy",
        "interaction_model": "tool_driven",
        "rendering_mode": "hybrid",
        "tone": "editorial",
        "palette_key": "mint_signal",
        "layout_key": "split_lens",
        "overlay_key": "mesh_wave",
        "motion_preset": "kinetic_meter",
        "background_token": "paper_mesh",
        "display_font_key": "display_editorial",
        "body_font_key": "body_soft",
        "hero_direction": "Use an asymmetrical split with one dramatic content pane and one precise utility pane.",
        "interaction_signature": "Expose one kinetic dial, meter, or slider that visibly animates the composition.",
    },
    {
        "heading": "FAST ASSIGNMENT (3/6): immersive_poster + orbital_float",
        "layout_archetype": "immersive_poster",
        "motion_archetype": "orbital_float",
        "visual_density": "dense",
        "interaction_model": "playful_loop",
        "rendering_mode": "canvas",
        "tone": "playful",
        "palette_key": "acid_arcade",
        "layout_key": "immersive_poster",
        "overlay_key": "orbital_dots",
        "motion_preset": "orbital_float",
        "background_token": "festival_dust",
        "display_font_key": "display_orbit",
        "body_font_key": "body_soft",
        "hero_direction": "Favor a poster-like full-viewport composition with bold type and floating ornaments.",
        "interaction_signature": "Make one playful loop or hover reaction feel central to the page identity.",
    },
    {
        "heading": "FAST ASSIGNMENT (4/6): bento_magazine + stagger_reveal",
        "layout_archetype": "bento_magazine",
        "motion_archetype": "stagger_reveal",
        "visual_density": "layered",
        "interaction_model": "tool_driven",
        "rendering_mode": "dom",
        "tone": "editorial",
        "palette_key": "rose_oxide",
        "layout_key": "bento_magazine",
        "overlay_key": "diagonal_hatch",
        "motion_preset": "stagger_reveal",
        "background_token": "rose_fog",
        "display_font_key": "display_editorial",
        "body_font_key": "body_clean",
        "hero_direction": "Use a magazine rhythm with uneven blocks, not equal cards in a neat dashboard.",
        "interaction_signature": "Introduce one reveal-driven panel, filter, or expandable editorial detail.",
    },
    {
        "heading": "FAST ASSIGNMENT (5/6): stage_focus + tilt_pointer",
        "layout_archetype": "stage_focus",
        "motion_archetype": "tilt_pointer",
        "visual_density": "airy",
        "interaction_model": "pointer_reactive",
        "rendering_mode": "three",
        "tone": "cinematic",
        "palette_key": "midnight_luxe",
        "layout_key": "stage_focus",
        "overlay_key": "contour_lines",
        "motion_preset": "tilt_pointer",
        "background_token": "night_grid",
        "display_font_key": "display_grotesk",
        "body_font_key": "body_clean",
        "hero_direction": "Keep the page dark, glossy, and stage-led, with one dominant scene and compact controls.",
        "interaction_signature": "Make pointer motion, camera tilt, or lighting response the main interactive flourish.",
    },
    {
        "heading": "FAST ASSIGNMENT (6/6): split_lens + scroll_shutter",
        "layout_archetype": "split_lens",
        "motion_archetype": "scroll_shutter",
        "visual_density": "dense",
        "interaction_model": "scroll_story",
        "rendering_mode": "hybrid",
        "tone": "brutalist_softened",
        "palette_key": "lavender_fog",
        "layout_key": "split_lens",
        "overlay_key": "grain_speckle",
        "motion_preset": "scroll_shutter",
        "background_token": "lacquer_shadow",
        "display_font_key": "display_grotesk",
        "body_font_key": "body_soft",
        "hero_direction": "Use a blunt split layout with tension between a dramatic stage and compact narrative blocks.",
        "interaction_signature": "Let scrolling or one manual scrubber trigger the signature transition.",
    },
]


def _format_fast_assignment(preset: Dict[str, str]) -> str:
    return f"""{preset['heading']}
- layout_archetype: {preset['layout_archetype']}
- motion_archetype: {preset['motion_archetype']}
- visual_density: {preset['visual_density']}
- interaction_model: {preset['interaction_model']}
- rendering_mode: {preset['rendering_mode']}
- tone: {preset['tone']}
- palette_key: {preset['palette_key']}
- layout_key: {preset['layout_key']}
- background_token: {preset['background_token']}
- motion_token: {preset['motion_preset']}
- overlay_key: {preset['overlay_key']}
- display_font_key: {preset['display_font_key']}
- body_font_key: {preset['body_font_key']}
- hero_direction: {preset['hero_direction']}
- interaction_signature: {preset['interaction_signature']}
Use these assignment axes as the main source of diversity.
Use exactly the assigned background_token and motion_token as the default visual system.
If useful, reference `/static/design-kit/fonts.css` and `/static/design-kit/overlays/...` local assets.
"""


_CATEGORY_ROTATION_NOTES = [
    (preset["heading"], _format_fast_assignment(preset)) for preset in _FAST_ASSIGNMENT_PRESETS
]

_category_lock = threading.Lock()
_category_indices: Dict[str, int] = {}


def _next_category_note(user_key: Optional[str] = None) -> str:
    key = (user_key or "").strip() or "__global__"
    with _category_lock:
        idx = (_category_indices.get(key, -1) + 1) % len(_CATEGORY_ROTATION_NOTES)
        _category_indices[key] = idx
        # Avoid unbounded growth if many unique keys appear
        if len(_category_indices) > 4096:
            # Drop oldest half excluding the active key to keep footprint bounded
            for stale in list(_category_indices.keys()):
                if stale == key:
                    continue
                _category_indices.pop(stale, None)
                if len(_category_indices) <= 2048:
                    break
        heading, note = _CATEGORY_ROTATION_NOTES[idx]
    logging.info("llm category_assignment=%s index=%d key=%s", heading, idx + 1, key)
    return note

def _call_openrouter_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call OpenRouter Chat Completions and parse a page dict; None on failure."""
    temperature = TEMPERATURE
    prompt = _build_fast_page_prompt(brief, seed, category_note)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "non-deterministic-website",
    }
    # Prefer JSON mode first; if rejected by provider, we'll retry without it.
    wants_json_mode = True

    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": max(1.1, min(1.3, float(temperature))),
        "top_p": 0.95,
    }
    if OPENROUTER_MAX_TOKENS is not None:
        body["max_tokens"] = OPENROUTER_MAX_TOKENS
    if wants_json_mode:
        body["response_format"] = {"type": "json_object"}

    def _send_openrouter(payload: Dict[str, Any]):
        _openrouter_sleep_if_needed()
        try:
            response = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, timeout=LLM_TIMEOUT_SECS)
        except Exception as exc:
            logging.warning("OpenRouter request error: %r", exc)
            return None
        if response.status_code == 429:
            _openrouter_register_rate_limit(response.headers.get("Retry-After"))
        elif response.status_code == 200:
            _openrouter_reset_backoff()
        return response

    resp = _send_openrouter(body)
    if resp is None:
        return None

    if resp.status_code != 200:
        # If JSON mode not supported, retry once without response_format
        txt = None
        try:
            txt = resp.text
        except Exception:
            txt = None
        msg = (txt or "")[:400]
        if wants_json_mode and ("JSON mode is not enabled" in (txt or "") or "response_format" in (txt or "")):
            body.pop("response_format", None)
            resp = _send_openrouter(body)
            if resp is None:
                return None
            if resp.status_code != 200:
                try:
                    msg = resp.text[:400]
                except Exception:
                    msg = str(resp.status_code)
                logging.warning("OpenRouter HTTP %s after retry: %s", resp.status_code, msg)
                # Try fallback models before giving up
                fallback_models = [OPENROUTER_FALLBACK_MODEL_1, OPENROUTER_FALLBACK_MODEL_2]
                for fallback_model in fallback_models:
                    if fallback_model and fallback_model != OPENROUTER_MODEL:
                        logging.warning("OpenRouter model '%s' failed; retrying with fallback '%s'", OPENROUTER_MODEL, fallback_model)
                        body_fallback = dict(body)
                        body_fallback["model"] = fallback_model
                        resp_fb = _send_openrouter(body_fallback)
                        if resp_fb is None:
                            continue
                        if resp_fb.status_code != 200:
                            try:
                                msg_fb = resp_fb.text[:400]
                            except Exception:
                                msg_fb = str(resp_fb.status_code)
                            logging.warning("OpenRouter HTTP %s with fallback '%s': %s", resp_fb.status_code, fallback_model, msg_fb)
                            continue
                        # Use fallback response as success
                        resp = resp_fb
                        break
                else:
                    # All fallbacks failed
                    return None
        else:
            logging.warning("OpenRouter HTTP %s: %s", resp.status_code, msg)
            # Try fallback models before giving up
            fallback_models = [OPENROUTER_FALLBACK_MODEL_1, OPENROUTER_FALLBACK_MODEL_2]
            for fallback_model in fallback_models:
                if fallback_model and fallback_model != OPENROUTER_MODEL:
                    logging.warning("OpenRouter model '%s' failed; retrying with fallback '%s'", OPENROUTER_MODEL, fallback_model)
                    body_fallback = dict(body)
                    body_fallback["model"] = fallback_model
                    resp_fb = _send_openrouter(body_fallback)
                    if resp_fb is None:
                        continue
                    if resp_fb.status_code != 200:
                        try:
                            msg_fb = resp_fb.text[:400]
                        except Exception:
                            msg_fb = str(resp_fb.status_code)
                        logging.warning("OpenRouter HTTP %s with fallback '%s': %s", resp_fb.status_code, fallback_model, msg_fb)
                        continue
                    # Use fallback response as success
                    resp = resp_fb
                    break
            else:
                # All fallbacks failed
                return None

    try:
        data = resp.json()
    except Exception:
        logging.warning("OpenRouter: non-JSON HTTP body")
        return None

    try:
        message = data.get("choices", [{}])[0].get("message", {}) or {}
        text = message.get("content")
    except Exception:
        message = {}
        text = None
    if not text or not isinstance(text, str) or not text.strip():
        reasoning = message.get("reasoning")
        if isinstance(reasoning, str):
            trimmed = reasoning.strip()
            if trimmed.startswith("{") or trimmed.startswith("[") or "<html" in trimmed.lower() or "<!doctype" in trimmed.lower():
                text = reasoning
    if not text or not isinstance(text, str):
        try:
            text = resp.text
        except Exception:
            text = None
        if not text or not isinstance(text, str):
            logging.warning("OpenRouter: empty response text")
            return None

    try:
        page = _json_from_text(text)
    except Exception as e:
        logging.warning("OpenRouter: failed to extract JSON/HTML: %r", e)
        tl = (text or "")
        if isinstance(tl, str) and ("<html" in tl.lower() or "<!doctype" in tl.lower() or "<div" in tl.lower() or "<body" in tl.lower()):
            page = {"kind": "full_page_html", "html": tl}
        else:
            return None

    try:
        norm = _normalize_doc(page)
        if isinstance(norm, dict):
            return norm
    except Exception as e:
        logging.warning("OpenRouter: normalization error: %r", e)
    return None


def _gemini_review_active() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    with _GEMINI_REVIEW_BACKOFF_LOCK:
        if _GEMINI_REVIEW_BACKOFF_UNTIL and time.time() < _GEMINI_REVIEW_BACKOFF_UNTIL:
            return False
    review_key = GEMINI_REVIEW_API_KEY or GEMINI_API_KEY
    return bool(GEMINI_REVIEW_ENABLED and review_key and GEMINI_REVIEW_ENDPOINT)


def _mark_gemini_review_backoff() -> None:
    if GEMINI_REVIEW_BACKOFF_SECS <= 0:
        return
    with _GEMINI_REVIEW_BACKOFF_LOCK:
        until = time.time() + GEMINI_REVIEW_BACKOFF_SECS
        global _GEMINI_REVIEW_BACKOFF_UNTIL
        _GEMINI_REVIEW_BACKOFF_UNTIL = max(_GEMINI_REVIEW_BACKOFF_UNTIL, until)


def _openrouter_review_active() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return bool(OPENROUTER_API_KEY and OPENROUTER_REVIEW_MODEL)


def _review_provider() -> str:
    provider = os.getenv("COMPLIANCE_PROVIDER", "gemini").strip().lower()
    if provider in {"openrouter", "or"}:
        if _openrouter_review_active():
            return "openrouter"
        if _gemini_review_active():
            return "gemini"
        return "openrouter"
    return "gemini"


def _call_gemini_review(doc: Dict[str, Any], brief: str, category_note: str) -> Optional[Dict[str, Any]]:
    if not _gemini_review_active():
        return None
    prompt = _build_review_prompt(doc, brief, category_note, allow_null_doc=False, doc_required=False)
    review_schema = _gemini_review_schema()
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 20000,
            "responseMimeType": "application/json",
            "responseSchema": review_schema,
        },
    }
    attempts = max(1, GEMINI_REVIEW_RETRY_ATTEMPTS)
    delay = max(0.5, GEMINI_REVIEW_RETRY_DELAY)
    resp = None
    review_key = GEMINI_REVIEW_API_KEY or GEMINI_API_KEY
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(
                GEMINI_REVIEW_ENDPOINT,
                params={"key": review_key},
                json=body,
                timeout=max(LLM_TIMEOUT_SECS, 120),
            )
        except Exception as exc:
            logging.warning("Gemini review request error: %r", exc)
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
                continue
            return None
        if resp.status_code in {429, 503}:
            logging.warning("Gemini review HTTP %s: %s", resp.status_code, resp.text[:200])
            _mark_gemini_review_backoff()
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
                continue
            return None
        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Gemini review HTTP %s: %s", resp.status_code, msg)
            return None
        break
    if resp is None:
        return None
    try:
        payload = resp.json()
    except Exception as exc:
        logging.warning("Gemini review non-JSON body: %r", exc)
        return None
    text = _extract_gemini_text(payload)
    if not text or not isinstance(text, str):
        try:
            raw = resp.text[:400]
        except Exception:
            raw = "<unavailable>"
        logging.warning("Gemini review empty content; raw response snippet=%s", raw)
        return None
    text = text.strip()
    try:
        review = json.loads(text)
    except Exception:
        try:
            any_json = _json_from_text(text)
            review = any_json if isinstance(any_json, dict) else None
        except Exception:
            review = None
    if not isinstance(review, dict):
        logging.warning("Gemini review response unparsable: %s", text[:200])
        repaired = _openrouter_repair_to_schema(
            text,
            _review_schema(),
            name="compliance_review",
            label="gemini_review_repair",
            max_tokens=OPENROUTER_REVIEW_MAX_TOKENS or 4096,
        )
        if isinstance(repaired, dict):
            logging.info("Gemini review repaired via OpenRouter")
            return repaired
        return None
    return review


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


def _maybe_run_compliance_review(
    doc: Dict[str, Any], brief: str, category_note: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool]:
    if not isinstance(doc, dict):
        return None, None, True
    provider = _review_provider()
    if provider == "openrouter":
        if not _openrouter_review_active():
            return None, None, True
    elif not _gemini_review_active():
        return None, None, True
    logging.info("Compliance review: submitting doc for %s evaluation", provider)
    review: Optional[Dict[str, Any]]
    if provider == "openrouter":
        review = _call_openrouter_review(doc, brief, category_note)
    else:
        review = _call_gemini_review(doc, brief, category_note)
        if not isinstance(review, dict) and _openrouter_review_active() and not COMPLIANCE_GEMINI_ONLY:
            logging.info("Compliance review: gemini unavailable; falling back to openrouter")
            review = _call_openrouter_review(doc, brief, category_note)
            provider = "openrouter"
    if not isinstance(review, dict):
        logging.info("Compliance review: %s response missing or unusable; skipping", provider)
        return None, None, True
    corrected_doc = None
    for key in ("doc", "fixed_doc", "corrected_doc", "patched_doc"):
        maybe_doc = review.get(key)
        if isinstance(maybe_doc, dict):
            corrected_doc = maybe_doc
            break
    ok_value = review.get("ok")
    has_block = any(
        isinstance(issue, dict) and str(issue.get("severity", "")).lower() == "block"
        for issue in (review.get("issues") or [])
    )
    if ok_value is False or (has_block and corrected_doc is None):
        logging.info(
            "Compliance review: %s blocked doc with %d issues",
            provider,
            len(review.get("issues", [])),
        )
        return review, None, False
    if corrected_doc is not None:
        logging.info("Compliance review: %s returned corrected payload", provider)
        return review, corrected_doc, True
    logging.info("Compliance review: %s approved without changes", provider)
    return review, None, True


def run_compliance_batch(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not documents:
        return None
    provider = _review_provider()
    if provider == "openrouter":
        if not _openrouter_review_active():
            return None
    elif not _gemini_review_active():
        return None
    try:
        if provider == "openrouter":
            return _call_openrouter_review_batch(documents)
        reviews = _call_gemini_review_batch(documents)
        if reviews is None:
            per_doc = _call_gemini_review_per_doc(documents)
            if per_doc is not None:
                return per_doc
        if reviews is None and _openrouter_review_active() and not COMPLIANCE_GEMINI_ONLY:
            logging.info("Compliance batch: gemini unavailable; falling back to openrouter")
            return _call_openrouter_review_batch(documents)
        return reviews
    except Exception as exc:
        logging.warning("Compliance batch review error: %r", exc)
        return None


def _call_gemini_review_batch(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not documents:
        return None
    prompt = _build_batch_review_prompt(documents, allow_null_doc=False, doc_required=False)
    batch_review_schema = _gemini_batch_review_schema()
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            # Batch reviews can be verbose when returning per-doc issues + optional corrected docs.
            # Keep a high ceiling so a 20-item batch doesn't get truncated.
            "maxOutputTokens": min(60000, 4096 * len(documents)),
            "responseMimeType": "application/json",
            "responseSchema": batch_review_schema,
        },
    }
    attempts = max(1, GEMINI_REVIEW_RETRY_ATTEMPTS)
    delay = max(0.5, GEMINI_REVIEW_RETRY_DELAY)
    resp = None
    review_key = GEMINI_REVIEW_API_KEY or GEMINI_API_KEY
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(
                GEMINI_REVIEW_ENDPOINT,
                params={"key": review_key},
                json=body,
                timeout=max(LLM_TIMEOUT_SECS, 120),
            )
        except Exception as exc:
            logging.warning("Gemini batch review request error: %r", exc)
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
                continue
            return None
        if resp.status_code in {429, 503}:
            logging.warning("Gemini batch review HTTP %s: %s", resp.status_code, resp.text[:200])
            _mark_gemini_review_backoff()
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
                continue
            return None
        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Gemini batch review HTTP %s: %s", resp.status_code, msg)
            return None
        break
    if resp is None:
        return None
    try:
        payload = resp.json()
    except Exception as exc:
        logging.warning("Gemini batch review non-JSON body: %r", exc)
        return None
    text = _extract_gemini_text(payload)
    if not text or not isinstance(text, str):
        try:
            raw = resp.text[:400]
        except Exception:
            raw = "<unavailable>"
        logging.warning("Gemini batch review empty content; raw response snippet=%s", raw)
        return None
    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        try:
            data = _json_from_text(text)
        except Exception:
            repaired = _repair_json_loose(text)
            if repaired != text:
                try:
                    data = json.loads(repaired)
                except Exception:
                    logging.warning("Gemini batch review response unparsable: %s", text[:200])
                    repaired_obj = _openrouter_repair_to_schema(
                        text,
                        _batch_review_schema(),
                        name="compliance_review_batch",
                        label="gemini_batch_review_repair",
                        max_tokens=max(OPENROUTER_REVIEW_MAX_TOKENS, 16000),
                    )
                    if isinstance(repaired_obj, dict):
                        repaired_list = repaired_obj.get("results") or repaired_obj.get("reviews")
                        if isinstance(repaired_list, list):
                            logging.info("Gemini batch review repaired via OpenRouter")
                            return repaired_list
                    return None
            else:
                logging.warning("Gemini batch review response unparsable: %s", text[:200])
                repaired_obj = _openrouter_repair_to_schema(
                    text,
                    _batch_review_schema(),
                    name="compliance_review_batch",
                    label="gemini_batch_review_repair",
                    max_tokens=max(OPENROUTER_REVIEW_MAX_TOKENS, 16000),
                )
                if isinstance(repaired_obj, dict):
                    repaired_list = repaired_obj.get("results") or repaired_obj.get("reviews")
                    if isinstance(repaired_list, list):
                        logging.info("Gemini batch review repaired via OpenRouter")
                        return repaired_list
                return None
    if isinstance(data, dict):
        data = data.get("results") or data.get("reviews")
    if not isinstance(data, list):
        logging.warning("Gemini batch review invalid payload type: %s", type(data))
        return None
    return data


def _call_gemini_review_per_doc(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not documents or not _gemini_review_active():
        return None
    reviews: List[Dict[str, Any]] = []
    for idx, doc in enumerate(documents):
        review = _call_gemini_review(doc, "", "")
        if not isinstance(review, dict):
            return None
        if "index" not in review:
            review["index"] = idx
        reviews.append(review)
    return reviews


def _openrouter_extract_content(payload: Dict[str, Any]) -> Optional[str]:
    try:
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, dict):
            for key in ("text", "content", "arguments"):
                val = content.get(key)
                if isinstance(val, str) and val.strip():
                    return val
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "".join(parts)
        tool_calls = msg.get("tool_calls") or msg.get("toolCalls") or []
        for call in tool_calls:
            fn = call.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str) and args.strip():
                return args
            if isinstance(args, dict):
                return json.dumps(args)
        function_call = msg.get("function_call") or msg.get("functionCall")
        if isinstance(function_call, dict):
            args = function_call.get("arguments")
            if isinstance(args, str) and args.strip():
                return args
            if isinstance(args, dict):
                return json.dumps(args)
        for key in ("text", "output_text", "output"):
            val = choice.get(key) or msg.get(key)
            if isinstance(val, str) and val.strip():
                return val
    except Exception:
        return None
    return None


def _call_openrouter_review(doc: Dict[str, Any], brief: str, category_note: str) -> Optional[Dict[str, Any]]:
    if not _openrouter_review_active():
        return None
    prompt = _build_review_prompt(doc, brief, category_note, allow_null_doc=True, doc_required=True)
    schema = _review_schema()
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENROUTER_REVIEW_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": OPENROUTER_REVIEW_MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "compliance_review",
                "schema": schema,
                "strict": True,
            },
        },
    }
    def _send_review(req_body: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=req_body, timeout=LLM_TIMEOUT_SECS)
        except Exception as exc:
            logging.warning("OpenRouter review request error (%s): %r", label, exc)
            return None
        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("OpenRouter review HTTP %s (%s): %s", resp.status_code, label, msg)
            return None
        try:
            payload = resp.json()
        except Exception as exc:
            logging.warning("OpenRouter review non-JSON HTTP body (%s): %r", label, exc)
            return None
        if isinstance(payload, dict) and payload.get("error"):
            logging.warning("OpenRouter review error payload (%s): %s", label, payload.get("error"))
            return None
        text = _openrouter_extract_content(payload)
        if not text or not isinstance(text, str):
            snippet = ""
            try:
                snippet = json.dumps(payload)[:400]
            except Exception:
                snippet = str(payload)[:400]
            logging.warning("OpenRouter review empty response text (%s). payload=%s", label, snippet)
            return None
        try:
            parsed = json.loads(text)
        except Exception:
            try:
                parsed = _json_from_text(text)
            except Exception:
                logging.warning("OpenRouter review response unparsable (%s): %s", label, text[:200])
                return None
        return parsed if isinstance(parsed, dict) else None

    resp_body = _send_review(body, "schema")
    if resp_body is None and body.get("response_format"):
        body_no_schema = dict(body)
        body_no_schema.pop("response_format", None)
        resp_body = _send_review(body_no_schema, "noschema")
    if resp_body is None:
        return None
    return resp_body


def _call_openrouter_review_batch(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not documents:
        return None
    if not _openrouter_review_active():
        return None
    prompt = _build_batch_review_prompt(documents, allow_null_doc=True, doc_required=True)
    schema = _batch_review_schema()
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENROUTER_REVIEW_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": OPENROUTER_REVIEW_MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "compliance_review_batch",
                "schema": schema,
                "strict": True,
            },
        },
    }
    def _send_review(req_body: Dict[str, Any], label: str) -> Optional[List[Dict[str, Any]]]:
        try:
            resp = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=req_body, timeout=LLM_TIMEOUT_SECS)
        except Exception as exc:
            logging.warning("OpenRouter batch review request error (%s): %r", label, exc)
            return None
        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("OpenRouter batch review HTTP %s (%s): %s", resp.status_code, label, msg)
            return None
        try:
            payload = resp.json()
        except Exception as exc:
            logging.warning("OpenRouter batch review non-JSON HTTP body (%s): %r", label, exc)
            return None
        if isinstance(payload, dict) and payload.get("error"):
            logging.warning("OpenRouter batch review error payload (%s): %s", label, payload.get("error"))
            return None
        text = _openrouter_extract_content(payload)
        if not text or not isinstance(text, str):
            snippet = ""
            try:
                snippet = json.dumps(payload)[:400]
            except Exception:
                snippet = str(payload)[:400]
            logging.warning("OpenRouter batch review empty response text (%s). payload=%s", label, snippet)
            return None
        try:
            data = json.loads(text)
        except Exception:
            try:
                data = _json_from_text(text)
            except Exception:
                logging.warning("OpenRouter batch review response unparsable (%s): %s", label, text[:200])
                return None
        if isinstance(data, dict):
            data = data.get("results") or data.get("reviews")
        if not isinstance(data, list):
            logging.warning("OpenRouter batch review invalid payload type (%s): %s", label, type(data))
            return None
        return data

    data = _send_review(body, "schema")
    if data is None and body.get("response_format"):
        body_no_schema = dict(body)
        body_no_schema.pop("response_format", None)
        data = _send_review(body_no_schema, "noschema")
    if data is None:
        return None
    return data


def _seeded_palette_hint(seed: int) -> Dict[str, str]:
    random.seed(seed)
    colors = ["slate", "indigo", "rose", "emerald", "amber", "violet", "cyan"]
    primaries = colors
    accents = colors
    return {"primary": random.choice(primaries), "accent": random.choice(accents)}

def _seeded_layout_hint(seed: int) -> str:
    random.seed(seed + 1337)
    return "grid" if random.random() < 0.3 else "stack"

def _make_request_id() -> str:
    return f"{random.randint(0, 16**8):08x}"
