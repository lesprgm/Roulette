from __future__ import annotations
import json
import logging
import os
import random
import time
from typing import Any, Dict, Iterable, Optional, Tuple, List, Pattern, Sequence, Set
import requests
from api.generation.activity_quality import score_activity_depth
from api.generation.design_quality import score_design_discipline
from api.generation.experience_quality import score_experience
from api.generation.prompts import (
    PAGE_SHAPE_HINT as _PAGE_SHAPE_HINT,
    PREMIUM_PLAN_SCHEMA,
)
from api.llm_parsing import _normalize_doc
from api.generation.novelty import novelty_summary
from api.generation.output_parsing import (
    extract_completed_premium_burst_sites as _extract_completed_premium_burst_sites,
    extract_final_html_blocks as _extract_final_html_blocks,
    extract_gemini_text as _parse_gemini_text,
    premium_burst_site_pattern as _premium_burst_site_pattern_impl,
)
from api.generation.premium_prompts import (
    build_premium_burst_prompt as _build_premium_burst_prompt_impl,
    build_premium_page_prompt as _build_premium_page_prompt_impl,
    build_premium_plan_prompt as _build_premium_plan_prompt_impl,
)
from api.generation.premium_quality import (
    attach_premium_evaluations as _attach_premium_evaluations_impl,
    attach_quality_score as _attach_quality_score_impl,
    has_full_experience_plan as _has_full_experience_plan_impl,
)
from api.generation.provider_gemini import (
    call_structured as _provider_call_structured,
    call_text as _provider_call_text,
    iter_stream_text as _provider_iter_stream_text,
    was_quota_exhausted,
)
from api.preflight import annotate_doc as _annotate_preflight_doc
from api.preflight import first_js_syntax_error as _first_js_syntax_error
from api.preflight import has_blocking_issues as _preflight_has_blocking_issues
from api.preflight import preflight_doc as _preflight_doc
from api.quality import score_page_doc
from api.generation.experience_grammar import (
    seeded_activity_contract,
    seeded_diverse_format_first_targets,
    seeded_format_first_target,
    seeded_genre_contract,
)
from api.generation.redis_diversity import recent_activity_memory
from api.generation.semantic_anchors import select_semantic_anchors
from api.generation.task_grammar import task_contract_for_variant


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
    BURST_SITE_COUNT = int(os.getenv("BURST_SITE_COUNT", "10"))
except Exception:
    BURST_SITE_COUNT = 10
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
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "medium").strip().lower()
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
    return _attach_quality_score_impl(doc, mode, score_page_doc=score_page_doc)


def _has_full_experience_plan(plan: Dict[str, Any]) -> bool:
    return _has_full_experience_plan_impl(plan)


def _semantic_translation_from_anchors(anchors: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    readable_format = str(task.get("format") or "the selected activity").replace("_", " ")
    translation: Dict[str, Dict[str, str]] = {}
    for key, value in (anchors or {}).items():
        anchor = str(value or "").strip()
        if not anchor:
            continue
        if key == "material":
            visual_role = (
                f"Embody {anchor} as a material system for {readable_format}: synthesize texture, surface, "
                "shape, border, shadow, or generated pattern with CSS gradients, pseudo-elements, inline SVG, "
                "Canvas, or Three.js material when appropriate."
            )
            interaction_role = (
                f"Let {anchor} affect interaction feedback, such as compression, spring, scrape, stitch, shine, "
                "grain, reflection, or other tactile response tied to state changes."
            )
            content_role = (
                f"Do not put {anchor} in the title or major labels unless the UI visibly embodies it. "
                f"The recognizable format name for {readable_format} should remain dominant."
            )
            motion_role = (
                f"Translate {anchor} into restrained material motion only when useful: thread sweep, dust, "
                "polish, grain drift, soft rebound, shimmer, crack, or surface reveal."
            )
        elif key == "everyday_object":
            visual_role = f"Use {anchor} as a UI metaphor, affordance shape, icon idea, control object, or content prop for {readable_format}."
            interaction_role = f"Let {anchor} influence how the user manipulates the interface, without replacing the {readable_format} behavior."
            content_role = f"Use {anchor} in copy only if it clarifies the product/task; otherwise keep it implicit in component design."
            motion_role = f"Translate {anchor} into small object-like feedback tied to the primary action."
        elif key == "layout_metaphor":
            visual_role = f"Use {anchor} to shape composition, grouping, navigation, or information flow for {readable_format}."
            interaction_role = f"Let {anchor} guide how sections open, move, sort, or connect."
            content_role = f"Use {anchor} as structure, not as random title wording."
            motion_role = f"Translate {anchor} into transitions between regions or states."
        elif key == "interaction_verb":
            visual_role = f"Make the main affordance visually support the action '{anchor}'."
            interaction_role = f"The primary action or feedback should feel like '{anchor}' while preserving the {readable_format} mechanic."
            content_role = f"Use action copy related to '{anchor}' only if it helps the user know what to do."
            motion_role = f"Use motion that communicates '{anchor}' after input."
        else:
            visual_role = f"Use {anchor} as a subtle surface, palette, or object-detail flavor for {readable_format}."
            interaction_role = f"Let {anchor} influence small feedback moments without replacing the {readable_format} behavior."
            content_role = f"Use {anchor} only in labels or microcopy when it clarifies the task."
            motion_role = f"Translate {anchor} into restrained motion accents tied to state changes."
        translation[key] = {
            "visual_role": visual_role,
            "interaction_role": interaction_role,
            "content_role": content_role,
            "motion_role": motion_role,
        }
    return translation


def _experience_fields_from_task(target: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
    controls = task.get("controls") if isinstance(task.get("controls"), list) else []
    first_control = controls[0] if controls and isinstance(controls[0], dict) else {}
    first_label = str(first_control.get("label") or "Try the main action").strip()
    user_goal = str(task.get("user_goal") or target.get("activity_contract", {}).get("activity_goal") or "Try the activity.").strip()
    completion = str(task.get("completion_condition") or target.get("activity_contract", {}).get("payoff") or "a visible result updates").strip()
    payoff_scene = task.get("payoff_scene") if isinstance(task.get("payoff_scene"), dict) else {}
    payoff_scene_text = str(payoff_scene.get("scene") or completion).strip()
    payoff_continue = str(payoff_scene.get("continue_action") or f"Improve, complete, compare, or replay the {str(task.get('format') or 'activity').replace('_', ' ')}.").strip()
    state_vars = task.get("state_variables") if isinstance(task.get("state_variables"), list) else []
    state_change = ", ".join(str(item) for item in state_vars[:3]) or "the visible state"
    activity_type = str(target.get("activity_type") or "")
    if activity_type in {"microgame", "platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game"}:
        visitor_role = "player"
    elif activity_type == "product_or_storefront":
        visitor_role = "shopper"
    elif activity_type in {"saas_replica", "commerce_or_booking_flow", "fake_os_app"}:
        visitor_role = "operator"
    elif activity_type == "creative_tool":
        visitor_role = "creator"
    else:
        visitor_role = "visitor"
    return {
        "visitor_role": visitor_role,
        "visitor_goal": user_goal,
        "first_interaction": first_label,
        "primary_loop": {
            "user_action": first_label,
            "visible_response": f"The page updates visible state and then shows: {payoff_scene_text}.",
            "state_change": f"Updates {state_change}.",
            "reward_or_payoff": payoff_scene_text,
            "continue_reason": payoff_continue,
        },
        "secondary_interactions": [str(control.get("label")) for control in controls[1:3] if isinstance(control, dict) and control.get("label")],
        "feedback_contract": f"Every control must visibly change {state_change} or advance the payoff scene: {payoff_scene_text}.",
        "progression_model": payoff_scene_text,
        "reset_or_replay": "Provide a Reset, Restart, Edit, or Try again affordance when the format needs replay.",
        "onboarding_cue": first_label,
        "mobile_interaction": "Support touch/click controls on mobile; keep keyboard controls as an enhancement for games.",
    }


def _attach_premium_evaluations(
    scored: Dict[str, Any],
    plan: Dict[str, Any],
    *,
    include_experience: Optional[bool] = None,
) -> Dict[str, Any]:
    return _attach_premium_evaluations_impl(
        scored,
        plan,
        score_experience=score_experience,
        score_design_discipline=score_design_discipline,
        score_activity_depth=score_activity_depth,
        include_experience=include_experience,
    )


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
        if was_quota_exhausted():
            return {"error": "model_quota_exhausted"}
        return {"error": "Premium planner failed"}

    raw_doc = _call_gemini_premium_build(brief_str, seed_val, plan)
    if not isinstance(raw_doc, dict):
        if was_quota_exhausted():
            return {"error": "model_quota_exhausted"}
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
    scored = _attach_premium_evaluations(scored, plan, include_experience=True)
    return scored


def _call_testing_stub(brief: str, seed: int, category_note: str) -> Dict[str, Any]:
    """Fallback stub for local development and testing."""
    return {
        "kind": "full_page_html",
        "html": f"<!doctype html><html><body><h1>{brief or 'Stub App'}</h1><p>Seed: {seed}</p><p>Category: {category_note}</p></body></html>"
    }


def _call_gemini_structured(
    parts: List[Dict[str, Any]],
    schema: Dict[str, Any],
    *,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    endpoint: Optional[str] = None,
    retry_without_thinking: bool = True,
) -> Optional[Any]:
    return _provider_call_structured(
        parts=parts,
        schema=schema,
        api_key=GEMINI_API_KEY,
        endpoint=endpoint or GEMINI_GENERATION_ENDPOINT,
        fallback_endpoint="" if endpoint else GEMINI_FALLBACK_GENERATION_ENDPOINT,
        temperature=TEMPERATURE if temperature is None else temperature,
        max_output_tokens=max_output_tokens or GEMINI_MAX_OUTPUT_TOKENS,
        timeout_secs=LLM_TIMEOUT_SECS,
        thinking_level=GEMINI_THINKING_LEVEL,
        extract_text=_extract_gemini_text,
        retry_without_thinking=retry_without_thinking,
    )


def _call_gemini_text(
    parts: List[Dict[str, Any]],
    *,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    endpoint: Optional[str] = None,
    retry_without_thinking: bool = True,
) -> Optional[str]:
    return _provider_call_text(
        parts=parts,
        api_key=GEMINI_API_KEY,
        endpoint=endpoint or GEMINI_GENERATION_ENDPOINT,
        fallback_endpoint="" if endpoint else GEMINI_FALLBACK_GENERATION_ENDPOINT,
        temperature=TEMPERATURE if temperature is None else temperature,
        max_output_tokens=max_output_tokens or GEMINI_MAX_OUTPUT_TOKENS,
        timeout_secs=LLM_TIMEOUT_SECS,
        thinking_level=GEMINI_THINKING_LEVEL,
        extract_text=_extract_gemini_text,
        retry_without_thinking=retry_without_thinking,
    )


def _iter_gemini_stream_text(resp: requests.Response) -> Iterable[str]:
    yield from _provider_iter_stream_text(resp, extract_text=_extract_gemini_text)


def extract_final_html_blocks(text: str) -> List[str]:
    return _extract_final_html_blocks(text)


def _premium_burst_site_pattern() -> Pattern[str]:
    return _premium_burst_site_pattern_impl()


def extract_completed_premium_burst_sites(text: str) -> List[Tuple[int, str]]:
    return _extract_completed_premium_burst_sites(text)


def _premium_burst_rejection(doc: Dict[str, Any], quality: Dict[str, Any]) -> Optional[str]:
    del quality
    html = str(doc.get("html") or "")
    html_bytes = len(html.encode("utf-8"))
    if html_bytes < PREMIUM_BURST_MIN_HTML_BYTES:
        return f"html too small ({html_bytes}B < {PREMIUM_BURST_MIN_HTML_BYTES}B)"
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




def _build_premium_burst_prompt(brief: str, seed: int, targets: List[Dict[str, Any]]) -> str:
    return _build_premium_burst_prompt_impl(brief, seed, targets)

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

    memory = recent_activity_memory(limit=20)
    base_targets = seeded_diverse_format_first_targets(
        seed_val,
        target_count,
        recent_variants=memory.get("variants"),
        recent_families=memory.get("families"),
    )
    targets = []
    for idx, base_target in enumerate(base_targets):
        site_seed = seed_val + ((idx + 1) * 7919)
        target = _premium_experience_target(site_seed, base_target=base_target)
        target["site_index"] = idx + 1
        target["seed"] = site_seed
        targets.append(target)

    parts: List[Dict[str, Any]] = [{"text": _build_premium_burst_prompt(brief or "", seed_val, targets)}]
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

    all_429 = True
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
            all_429 = False
            continue
        if resp.status_code == 400 and "thinkingConfig" in generation_config:
            retry_config = dict(generation_config)
            retry_config.pop("thinkingConfig", None)
            retry_body = dict(body)
            retry_body["generationConfig"] = retry_config
            try:
                resp = requests.post(
                    endpoint,
                    params={"key": GEMINI_API_KEY},
                    json=retry_body,
                    timeout=LLM_TIMEOUT_SECS,
                    stream=True,
                )
                if resp.status_code == 200:
                    logging.info("Gemini premium burst %s succeeded after removing thinkingConfig", label)
            except Exception as exc:
                logging.warning("Gemini premium burst %s retry without thinkingConfig error: %r", label, exc)
                all_429 = False
                continue
        if resp.status_code != 200:
            logging.warning("Gemini premium burst %s HTTP %s: %s", label, resp.status_code, resp.text[:400])
            if resp.status_code != 429:
                all_429 = False
            continue
        all_429 = False  # endpoint responded, not all-429
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
                plan = targets[index - 1] if 0 < index <= len(targets) else {}
                scored = _attach_premium_evaluations(scored, plan)
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
                debug = dict(scored.get("ndw_debug") or {})
                debug["generation_mode"] = "premium_burst"
                debug["premium_burst_index"] = index
                scored["ndw_debug"] = debug
                yield scored
                emitted_count += 1
                if emitted_count >= target_count:
                    return
        if emitted_count:
            return
        logging.warning("Gemini premium burst %s produced no valid sites; text_len=%d", label, len(full_text))
    if all_429:
        yield {"error": "model_quota_exhausted"}
    else:
        yield {"error": "Premium burst failed"}


def _premium_experience_target(seed: int, base_target: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    target = base_target if isinstance(base_target, dict) else seeded_format_first_target(seed)
    archetype = str(target["experience_archetype"])
    loop_type = str(target["primary_loop_type"])
    cell_key = f"{target['activity_contract']['activity_variant']}:{archetype}:{loop_type}"
    anchors = select_semantic_anchors(seed, cell_key)
    task = task_contract_for_variant(
        str(target["activity_contract"]["activity_variant"]),
        str(target["activity_type"]),
    )
    experience_fields = _experience_fields_from_task(target, task)
    return {
        **target,
        **experience_fields,
        "semantic_anchors": anchors,
        "semantic_translation": _semantic_translation_from_anchors(anchors, task),
        "task_contract": task,
        "genre_contract": seeded_genre_contract(seed, archetype, loop_type),
        "title_policy": "Semantic anchor words must be embodied or hidden. Do not put anchor words in <title>, <h1>, or major labels unless the UI expresses them through material, texture, shape, motion, interaction feedback, or metaphor. The concrete format name remains dominant.",
    }


def _build_premium_plan_prompt(brief: str, seed: int, experience_target: Optional[Dict[str, Any]] = None) -> str:
    target = experience_target if isinstance(experience_target, dict) else _premium_experience_target(seed)
    return _build_premium_plan_prompt_impl(brief, seed, experience_target=target, novelty=novelty_summary())


def _build_premium_page_prompt(
    brief: str,
    seed: int,
    plan: Dict[str, Any],
    retry_note: str = "",
) -> str:
    return _build_premium_page_prompt_impl(brief, seed, plan, retry_note)

def _call_gemini_premium_plan(
    brief: str,
    seed: int,
    user_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    del user_key
    experience_target = _premium_experience_target(seed)
    parts: List[Dict[str, Any]] = [{"text": _build_premium_plan_prompt(brief, seed, experience_target)}]
    out = _call_gemini_structured(parts, PREMIUM_PLAN_SCHEMA, temperature=0.8, max_output_tokens=4096)
    if isinstance(out, dict):
        # The model owns art direction; the backend owns the concrete product contract.
        # This prevents the planner from drifting a Snake/booking/tool target into abstract FUI.
        out["experience_archetype"] = experience_target["experience_archetype"]
        out["primary_loop_type"] = experience_target["primary_loop_type"]
        out["semantic_anchors"] = experience_target["semantic_anchors"]
        out["activity_type"] = experience_target["activity_type"]
        out["activity_contract"] = experience_target["activity_contract"]
        out["task_contract"] = experience_target["task_contract"]
        out["genre_contract"] = experience_target["genre_contract"]
    return out if isinstance(out, dict) else None


def _call_gemini_premium_build(
    brief: str,
    seed: int,
    plan: Dict[str, Any],
    *,
    retry_note: str = "",
) -> Optional[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = [{"text": _build_premium_page_prompt(brief, seed, plan, retry_note)}]
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
    return _parse_gemini_text(payload)


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
