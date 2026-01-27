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
from api.llm_parsing import (
    _extract_completed_objects_from_array,
    _json_from_text,
    _normalize_doc,
    _repair_json_loose,
)
from api.llm_prompts import (
    _batch_review_schema,
    _build_batch_review_prompt,
    _build_review_prompt,
    _gemini_batch_review_schema,
    _gemini_review_schema,
    _review_schema,
)


def _testing_stub_enabled() -> bool:
    """Return True when pytest is running and keys match the original environment values."""
    if not os.getenv("PYTEST_CURRENT_TEST"):
        return False
    if os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}:
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
    LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "75"))
except Exception:
    LLM_TIMEOUT_SECS = 75
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
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {
            "provider": "openrouter",
            "model": OPENROUTER_MODEL,
            "has_token": bool(OPENROUTER_API_KEY),
            "using": "openrouter",
            "reviewer": reviewer,
        }
    if GROQ_API_KEY:
        return {
            "provider": "groq",
            "model": GROQ_MODEL,
            "has_token": True,
            "using": "groq",
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
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {"ok": bool(OPENROUTER_API_KEY), "using": "openrouter"}
    if GROQ_API_KEY:
        return {"ok": True, "using": "groq"}
    return {"ok": False, "using": "stub"}


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
        providers: list[str] = []
        if providers_override:
            for p in providers_override:
                if p == "openrouter" and (OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY):
                    providers.append("openrouter")
                elif p == "groq" and GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
                    providers.append("groq")
                elif p == "gemini" and GEMINI_API_KEY and not FORCE_OPENROUTER_ONLY:
                    providers.append("gemini")
        if not providers:
            if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
                providers.append("openrouter")
            if GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
                providers.append("groq")
            # GEMINI is RESERVED for burst generation (generate_page_burst)
            # to maximize the 3x generation per request quota.
            # It is only used here as an absolute last resort if others are failing.
            if GEMINI_API_KEY and not FORCE_OPENROUTER_ONLY and not providers:
                providers.append("gemini")
        
        logging.warning("llm providers_order=%s force_openrouter_only=%s", providers, FORCE_OPENROUTER_ONLY)
        for p in providers:
            logging.warning("llm attempting provider=%s", p)
            if p == "groq":
                doc = _call_groq_for_page(brief_str, seed_val, category_note)
            elif p == "openrouter":
                doc = _call_openrouter_for_page(brief_str, seed_val, category_note)
            elif p == "gemini":
                doc = _call_gemini_for_page(brief_str, seed_val, category_note)
            if doc:
                logging.warning("llm chosen provider=%s", p)
                break
        if not doc:
            logging.warning("All providers failed; returning error doc.")
            return {"error": "Model generation failed"}

        if not doc:
            logging.warning("Model call failed or returned invalid JSON; returning error doc.")
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
        return doc
    return doc or {"error": "Model generation failed"}


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


def _call_gemini_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call Gemini for page generation."""
    matrix_b64 = _get_design_matrix_b64()
    
    vision_note = ""
    parts = []
    
    if matrix_b64:
        vision_note = """
=== VISION GROUNDING: DESIGN MATRIX ATTACHED ===
1. Analyze the attached 'UI Design Matrix'. 
2. Classify the brief into one of the 4 vibes (Professional, Playful, Brutalist, Cozy).
3. YOU MUST USE COLORS FROM THE 'Color Universe' strip. Sampling these exact hex values is MANDATORY.
4. Build the app matching the aesthetics of your selected vibe. FAILURE TO MATCH VIBE COLORS WILL RESULT IN REJECTION.
==============================================
"""
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})

    prompt = f"""
{vision_note}
=== MANDATORY CATEGORY ASSIGNMENT (DO NOT IGNORE) ===
{category_note}
You MUST build ONLY the category specified above. Do NOT build any other category.
=======================================================

You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations. The first non-whitespace character MUST be '{{'.
The JSON MUST include a non-empty "html" field containing the complete <!doctype html> document.

Brief: {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""
    parts.insert(0, {"text": prompt})
    
    response_schema = {
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
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }

    try:
        resp = requests.post(
            GEMINI_GENERATION_ENDPOINT,
            params={"key": GEMINI_API_KEY},
            json=body,
            timeout=LLM_TIMEOUT_SECS
        )
    except Exception as e:
        logging.warning("Gemini generation request error: %r", e)
        return None

    if resp.status_code != 200:
        try:
            msg = resp.text[:400]
        except Exception:
            msg = str(resp.status_code)
        logging.warning("Gemini generation HTTP %s: %s", resp.status_code, msg)
        return None

    try:
        data = resp.json()
        text = _extract_gemini_text(data)
        if not text:
            return None
        return _normalize_doc(_json_from_text(text))
    except Exception as e:
        logging.warning("Gemini generation extraction error: %r", e)
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
    target_docs: int = 10,
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


def generate_page_burst(brief: str, seed: int, user_key: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    """Yield up to 10 sites from a single streaming burst."""
    if not GEMINI_API_KEY:
        yield from _fallback_burst(brief, seed, user_key, target_docs=10)
        return

    # Fetch 10 categories for the burst
    category_notes = [_next_category_note(user_key) for _ in range(10)]
    target_docs = len(category_notes)
    matrix_b64 = _get_design_matrix_b64()
    
    parts = []
    if matrix_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": matrix_b64}})

    prompt = f"""
=== VISION GROUNDING: DESIGN MATRIX ATTACHED ===
1. Analyze the attached 'UI Design Matrix'. 
2. Classify the brief into one of the 4 vibes (Professional, Playful, Brutalist, Cozy).
3. Extract colors from the 'Color Universe' strip.
4. Build the apps matching the aesthetics of your selected vibe.
==============================================

=== MANDATORY CATEGORY ASSIGNMENTS (DO NOT IGNORE) ===
SITE 1 Category: {category_notes[0]}
SITE 2 Category: {category_notes[1]}
SITE 3 Category: {category_notes[2]}
SITE 4 Category: {category_notes[3]}
SITE 5 Category: {category_notes[4]}
SITE 6 Category: {category_notes[5]}
SITE 7 Category: {category_notes[6]}
SITE 8 Category: {category_notes[7]}
SITE 9 Category: {category_notes[8]}
SITE 10 Category: {category_notes[9]}

You MUST build each site following its assigned category.
=========================================================

You generate EXACTLY 10 unique, self-contained interactive web apps as a JSON array.
Each app must be a complete experience with high-quality design.
Output valid JSON only. No backticks. No explanations. The first non-whitespace character MUST be '['.
Every item MUST include a non-empty "html" field containing a complete <!doctype html> document.

Brief: {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""
    parts.insert(0, {"text": prompt})
    
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "array",
                "items": {
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
                                            "height": {"type": "number"}
                                        }
                                    }
                                }
                            }
                        },
                    },
                    "required": ["kind", "html"]
                },
                "minItems": 10,
                "maxItems": 10
            }
        },
    }

    try:
        resp = requests.post(
            GEMINI_STREAM_ENDPOINT,
            params={"key": GEMINI_API_KEY},
            json=body,
            timeout=LLM_TIMEOUT_SECS,
            stream=True
        )
        if resp.status_code != 200:
            logging.warning("Gemini stream HTTP %s: %s", resp.status_code, resp.text[:200])
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
                yield doc
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
                                recovered_docs.append(_normalize_doc(item))
                            except Exception as exc:
                                logging.warning("Gemini stream tolerant parse normalize error: %r", exc)
                    elif isinstance(recovered, dict):
                        recovered_docs.append(_normalize_doc(recovered))
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
            logging.warning("Gemini stream produced no valid pages; falling back to OpenRouter/Groq")
            yield from _fallback_single(brief, seed, user_key, extra=feedback)
                
    except Exception as e:
        logging.warning("Burst generation error: %r", e)
        logging.warning("Gemini burst error; falling back to OpenRouter/Groq")
        yield from _fallback_burst(
            brief,
            seed,
            user_key,
            target_docs=10,
            providers_override=["groq"],
        )


def _call_groq_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call Groq (OpenAI-compatible) and parse a page dict; None on failure."""
    temperature = TEMPERATURE

    prompt = f"""
=== MANDATORY CATEGORY ASSIGNMENT (DO NOT IGNORE) ===
{category_note}
You MUST build ONLY the category specified above. Do NOT build any other category.
=======================================================

You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""

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




_PAGE_SHAPE_HINT = """

FORMATS (prefer #2 for websites/quizzes; only use snippets/components when absolutely necessary):
1. {"kind":"ndw_snippet_v1","title":"...","background":{"style":"css","class":""},"css":"...","html":"...","js":"..."}  ← only use when a self-contained widget fits within the host page.
2. {"kind":"full_page_html","html":"<!doctype html>..."}  ← preferred shape; include complete <head>, <body>, semantic sections, and inline CSS/JS.
3. {"components":[{"id":"hero","type":"custom","props":{"html":"...","height":360}}]}  ← only when multiple iframe-style embeds are unavoidable; ensure each component supplies props.html and props.height (px number).

DESIGN QUALITY (MANDATORY — every output must feel premium):
- Use a cohesive color palette (3-5 colors max, harmonious). Avoid default browser grays.
- Apply modern CSS: border-radius: 12px+ on cards/buttons, subtle box-shadows, gradient backgrounds.
- Use generous whitespace (padding: 24px+, margin between sections, breathing room).
- Add micro-animations: hover effects (scale, color shift), smooth transitions (0.2s ease), subtle motion. Prefer GSAP for complex motion.
- Typography: vary font-weights (400/500/700), proper line-height (1.5+), clear hierarchy (h1 > h2 > p).
- Avoid flat, unstyled elements. Every button, card, and input should look intentionally designed.
- Color contrast: always pair dark text with light backgrounds (or vice versa). NEVER use medium-on-medium colors. Contrast must meet WCAG AA standards (4.5:1).
- PREMIUM ICONOGRAPHY: Lucide icons are provided globally. Use `<i data-lucide="icon-name"></i>` (e.g. `house`, `settings`, `check`) for all UI icons. Avoid raw SVGs.
- ICON STYLING: Make icons feel premium by applying Tailwind classes:
    - Color: Use `text-[color:var(--accent-500)]` or `text-slate-500` to match the theme.
    - Stroke: Adjust weight for elegance (e.g., `stroke-[1.5]` for thin/refined or `stroke-[2.5]` for bold).
    - Containers: Wrap icons in a small, soft-colored div (e.g., `bg-[color:var(--accent-50)] p-2 rounded-lg`) for a standalone 'SaaS' look.
- INITIAL VISUAL STATE (MANDATORY): The experience must NEVER be blank/empty on load. Provide ambient motion, floating particles, or a beautiful 'Click to Start' splash screen immediately. Don't wait for user input to show visual evidence of the theme.
- PREMIUM INTROS: Use GSAP (provided) for a staggered entrance animation of the UI elements.
- No "Tone-on-Tone": Never use pink text on a pink background, even if they are different shades, unless the contrast is extremely high.

GENERAL RULES:
- STRICT: No external scripts or styles via CDN (e.g., no <script src="https://...">). GSAP 3.12, Tailwind CSS, and Lucide Icons are already provided globally. Use them directly without re-importing. No external fonts/images/fetch.
- Tailwind runtime is local; do not include any <script src> tags or CDN imports in output.
- Output HTML without stray prefixes; host injects it directly.
- Provide clear instructions in the HTML (outside canvas).
- Rotate palettes: declare CSS custom properties or utility classes so each experience chooses colors that fit the theme (light, pastel, dark, neon).
- Use the provided examples as inspiration and feel free to remix their spirit, but avoid repeating the exact same names or layouts verbatim run after run.
- Keep the entire experience around 3000 tokens so responses stay snappy; prefer concise layouts, reusable utility classes, and focused copy.
- Every interactive element referenced in JS must already exist in the DOM with matching IDs/classes before scripts run.
- CONTROL CONSISTENCY: UI buttons and keyboard shortcuts (e.g., Spacebar) MUST trigger the exact same function. Do not duplicate logic with slight variations.

LAYOUT STRATEGY (CHOOSE ONE BEST FIT FOR THE CONCEPT):
Do not default to a centered card every time.
A) CONTENT-FIRST (Preferred): Large interactive area in the center, minimal header at the top.
B) SPLIT SCREEN: Best for "Input -> Output" tools (e.g., config on left, live preview on right).
C) BENTO GRID: Best for dashboards or multi-step tools. (Grid of cards).
D) FULL PAGE HERO: Best for immersive art or experiences. (Content spans full viewport).

HIERARCHY & IMPACT (MANDATORY):
- The INTERACTIVE APP is the star. It must be visible immediately. Use the ID `ndw-content` for the main app container.
- Header (Title/Category) must be COMPACT and CENTERED at the top. Never use a giant splash screen/hero that pushes the content below the fold.
- Focus on "Visual Evidence": If it's a calculator, show a dial. If it's a generator, show a beautifully styled card.

BASE HTML BLUEPRINT (ADAPT LAYOUT):
<main id="ndw-shell" class="min-h-screen text-slate-900" style="--bg-100:#f8fafc;--bg-300:#e0f2fe;--accent-500:#2563eb;--text-900:#0f172a;background:linear-gradient(135deg,var(--bg-100),var(--bg-300));">
  <!-- Compact Centered Header -->
  <header class="pt-8 pb-4 text-center">
    <p class="text-[10px] uppercase tracking-[0.4em] text-[color:var(--accent-500)]">[[category]]</p>
    <h1 class="text-xl font-semibold">[[headline]]</h1>
  </header>

  <section class="mx-auto max-w-6xl px-4 pb-12"> 
    <div id="ndw-content" class="min-h-[50vh] transition-all duration-500">
        [[YOUR UNIQUE INTERACTIVE LAYOUT HERE]]
    </div>
  </section>
</main>
NOTE: Replace CSS variables using the 'Color Universe' from the Matrix.

SNIPPET RUNTIME (NDW SDK CHEAT SHEET):
=== FRAME LOOP ===
NDW.loop((dt) => { ... })  // dt = milliseconds since last frame. Required for games/animations.

=== INPUT ===
NDW.isPressed("ArrowUp")  // true only on first frame of keypress (rising edge)
NDW.isDown("ArrowLeft")   // true while key is held
NDW.jump()    // alias: ArrowUp, Space, W
NDW.shot()    // alias: X, Z, mouse click  
NDW.action()  // alias: Enter, Space, mouse click
NDW.pointer   // { x, y, down } - mouse/touch position relative to canvas

=== AUDIO ===
NDW.audio.playTone(freq, durationMs, type, gain)  // e.g., playTone(440, 100, 'sine', 0.1)

=== JUICE (visual feedback) ===
NDW.juice.shake(intensity, durationMs)  // e.g., shake(5, 200) for screen shake
NDW.particles.spawn({x, y, count, spread, color, size, life})  // spawn particles
NDW.particles.update(dt, ctx)  // call in loop to render particles

=== CANVAS ===
const canvas = NDW.makeCanvas({parent: document.getElementById('ndw-content'), width: 800, height: 600});
// returns {ctx, dpr, clear()} - DPI-aware by default

=== MATH ===
NDW.utils.dist(x1, y1, x2, y2)      // distance between points
NDW.utils.angle(x1, y1, x2, y2)     // angle in radians
NDW.utils.overlaps(objA, objB)      // AABB/Circle collision detection
NDW.utils.lerp(a, b, t)             // linear interpolation
NDW.utils.clamp(v, min, max)        // clamp value to range
NDW.utils.rng(seed)                 // seeded random number generator

=== PERSISTENCE ===
NDW.utils.store.get("key")          // get from localStorage
NDW.utils.store.set("key", value)   // save to localStorage

=== HANDLERS (register ONCE outside loop) ===
NDW.onKey((e) => { if (e.key === 'ArrowUp') jump(); });
NDW.onPointer((e) => { if (e.down) shoot(e.x, e.y); });

JS GUARDRAILS:
- Wrap DOM queries inside DOMContentLoaded if scripts appear before the HTML (`document.addEventListener('DOMContentLoaded', () => { ... });`).
- Declare every variable with `const`/`let`; no implicit globals. Initialize counters/arrays with sensible defaults before using them.
- Avoid setInterval/setTimeout for animation; use NDW.loop and the provided `dt`.
- Remove unused listeners on reset paths and ensure buttons update text without referencing undefined nodes.

CONTROLS & INPUT REFERENCE (canvas categories only):
- Keyboard discrete: NDW.onKey((e) => { if (e.key === 'ArrowUp') jump(); });
- Keyboard continuous: if (NDW.isDown('ArrowLeft')) x -= speed * (dt/1000);
- Mouse/touch: NDW.onPointer((e) => { if (e.down) shoot(e.x, e.y); });
- Mouse held: if (NDW.isDown('mouse')) dragObject();

DO NOT:
- Do not use inline event handlers (`onclick=""`, etc.) or global window timers.
- Do not reference external fonts, CDNs, or fetch remote data. No iframes or document.write.
- Do not leave empty containers (e.g., an `#ndw-app` with no children) or placeholder text like "TODO".
- Do not create duplicate IDs or register multiple identical NDW.onPointer/onKey handlers inside loops.
- Do not build a different category than the one explicitly assigned above. Follow the CATEGORY ASSIGNMENT exactly.

SELF QA BEFORE RETURNING:
1. Pretend to click every button/toggle and ensure the described behaviour occurs; fix mismatched selectors.
2. Verify headings, instructions, and controls are visible on first paint (no hidden `display:none` wrappers).
3. For quizzes/tools, ensure result text updates and reset flows always set meaningful copy (never `undefined`).
4. Check that colors are harmonious and contrast is readable. No white-on-white or black-on-black.

CANONICAL CANVAS TEMPLATE:
const stage = document.createElement('section');
stage.className = 'mx-auto my-6 w-full max-w-4xl rounded-xl bg-white/85 backdrop-blur p-6 shadow-lg ring-1 ring-slate-200/70';
document.getElementById('ndw-app')?.appendChild(stage);

const canvas = NDW.makeCanvas({ parent: stage, width: 960, height: 560 });
const ctx = canvas.ctx;
const rand = NDW.utils.rng(seed);
let state = { x: ctx.width / 2, vx: 0 };

NDW.onKey((e) => {
     if (e.key === 'ArrowLeft') state.vx = -1;
     if (e.key === 'ArrowRight') state.vx = 1;
});

NDW.loop((dt) => {
     const seconds = dt / 1000;
     const width = ctx.width;
     const height = ctx.height;
     state.x = Math.max(20, Math.min(width - 20, state.x + state.vx * seconds * 200));
     ctx.clearRect(0, 0, width, height);
     ctx.fillStyle = '#10b981';
     ctx.fillRect(state.x - 20, height - 60, 40, 40);
});

OUTPUT CHECKLIST:
✓ Valid JSON in format #1, #2, or #3
✓ Title present (if snippet) and used; or omit cleanly
✓ All vars initialized; listeners bound before use
✓ Canvas flows: clearRect each frame, use dt parameter, no manual timers
✓ Websites/Quizzes: multi-section DOM layout, accessible labels, no canvas usage
✓ No undefined refs or missing elements
✓ Premium design: rounded corners, shadows, gradients, micro-animations
4. Check that colors are harmonious and contrast is readable. No white-on-white or black-on-black. No "blending" font colors with backgrounds.
✓ Varied Layout: Did not just use a centered card if a sidebar or grid was better.
✓ Hard Readability: Font colors do not "blend" into the background. Text is sharp and high-contrast.
"""

_CATEGORY_ROTATION_NOTES = [
    ("CATEGORY ASSIGNMENT (1/5): Interactive Entertainment / Web Toy",
     """CATEGORY ASSIGNMENT (1/5): You MUST build an Interactive Entertainment / Web Toy.

Focus on playful, unexpected interactions that delight users.
SHOW, DON'T TELL: Do not just write a paragraph of text. Create a toy.
Example inspirations (remix freely but make them VISUAL):
- gravity flip stages, whispering pixel terrariums, sparkle vortex dodgers
- mirror maze click escapes, bubble pop orchestras, neon vine twisters
- marshmallow catapults, echo button choirs, kaleidoscope cursor trails
- confetti explosion buttons, rainbow trail painters, mood ring simulators
- click-to-bloom flower gardens, bouncing ball physics toys, pixel pet companions
- sound board mixers, emoji rain makers, firework launchers
- color palette spinners, particle fountain creators, hypnotic spiral generators
- fidget spinner simulators, satisfying click counters, zen sand gardens
- bubble wrap poppers, domino chain reactions, magnetic poetry boards

Use expressive HTML/CSS and light JS—no heavy physics engines—and stay whimsical.
AVOID: Just a button that updates a number."""),

    ("CATEGORY ASSIGNMENT (2/5): Utility Micro-Tool",
     """CATEGORY ASSIGNMENT (2/5): You MUST build a Utility Micro-Tool solving one focused task.
     
SHOW, DON'T TELL: A calculator should show a real-time graph or visual indicator, not just a number result.
Example inspirations (remix freely):
- pet age dashboards (show a growing pet icon), is-it-Friday checkers (giant neon banner)
- caffeine half-life calculators (show decay graph curve), sleep debt trackers (visual battery meter)
- tip calculators (visual split-the-bill pie chart), unit converters (visual size comparison)
- countdown timers (circular progress rings), reading time estimators (animated progress bar)
- password strength checkers (animated un/lock meter), color contrast validators (live preview cards)
- groceries expense splitters (visual stack of coins), savings goal trackers (filling a jar)
- habit streak counters (commit graph grid), focus session timers (visually shrinking circle)
- quick decision makers (spin-the-wheel animation)

Deliver clear inputs AND RICH VISUAL RESULTS. No plain text results."""),
    
    ("CATEGORY ASSIGNMENT (3/5): Playable Simple Game",
     """CATEGORY ASSIGNMENT (3/5): You MUST build a Playable Simple Game.

Use the NDW SDK for frame-independent logic:
- NDW.loop((dt) => { ... }) for the game loop (dt = milliseconds)
- NDW.isPressed("ArrowUp") or NDW.jump() for single-hit input (jumping, shooting)
- NDW.isDown("ArrowLeft") for continuous input (movement)
- NDW.audio.playTone(440, 100) for sound effects
- NDW.juice.shake(5, 200) for screen shake on hits
- NDW.particles.spawn({x, y, count: 10}) for explosions
- NDW.makeCanvas({parent: document.getElementById('ndw-content'), width: 800, height: 600})

Example inspirations (remix freely):
- Snake (collect apples, grow longer, avoid self)
- Breakout/Pong (paddle controls, ball physics)
- Flappy Bird (tap to jump, avoid pipes)
- Asteroid shooter (rotate, thrust, shoot)
- Endless runner (jump over obstacles, collect coins)
- Clicker/idle games (upgrade buttons, progress bars)
- Memory matching (flip cards, find pairs)
- Reaction time testers (click when color changes)
- Maze navigators (arrow key movement)
- Falling blocks (Tetris-style)

MUST HAVE: Score display, game over state, restart button, sound on key actions."""),
    
    ("CATEGORY ASSIGNMENT (4/5): Interactive Art",
     """CATEGORY ASSIGNMENT (4/5): You MUST build Interactive Art with NDW.makeCanvas.
     
Initialize arrays with NDW.utils.rng(seed), create visible motion within 1 second.
Read NDW.pointer inside the loop while handlers stay outside.

Example inspirations (remix palettes and motion patterns):
- prism cascade skylines, nebula ink tides, starlit bloom ribbons
- chroma wind tunnels, velvet glitch tapestries, lumen ripple seas
- aurora borealis waves, fractal tree growers, particle swarm dances
- geometric shape morphers, color field blenders, noise flow visualizers
- constellation connectors, rain drop simulators, firefly jar scenes
- ocean wave generators, smoke trail painters, crystal growth animations
- galaxy spiral spinners, mandala pattern drawers, sound wave visualizers
- terrain heightmap explorers, voronoi cell mosaics, reaction diffusion patterns
- gravity well simulators, magnetic field lines, electromagnetic wave pulses

Include an HTML caption describing the piece."""),
    
    ("CATEGORY ASSIGNMENT (5/5): Quizzes / Learning Cards",
     """CATEGORY ASSIGNMENT (5/5): You MUST build Quizzes / Learning Cards.
     
GAMIFY IT: Use semantic sections, progress bars, streaks, and confetti on correct answers.
Example inspirations (remix freely):
- campus lore lightning rounds (speed timer, flashcard style)
- mythic creature deducers (visual clues reveal the answer)
- flag identification quizzes (large colorful flags)
- periodic table testers (highlighting grid)
- movie quote guessers (kinetic typography)
- historical event timelines (a draggable timeline slider)
- geography boundary drawers, space fact verifiers
- coding concept flash cards (syntax highlighting card flip)
- personality type sorters (interactive sliders for traits)

Prefer rich HTML layouts—no canvas—and keep everything accessible.
AVOID: A simple list of radio buttons. Make it interactive."""),
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

# Removed Gemini provider support completely


def _call_openrouter_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call OpenRouter Chat Completions and parse a page dict; None on failure."""
    temperature = TEMPERATURE

    prompt = f"""
=== MANDATORY CATEGORY ASSIGNMENT (DO NOT IGNORE) ===
{category_note}
You MUST build ONLY the category specified above. Do NOT build any other category.
=======================================================

You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""

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
        if not isinstance(review, dict) and _openrouter_review_active():
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
        if reviews is None and _openrouter_review_active():
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
            "maxOutputTokens": min(20000, 4096 * len(documents)),
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
                    return None
            else:
                logging.warning("Gemini batch review response unparsable: %s", text[:200])
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
