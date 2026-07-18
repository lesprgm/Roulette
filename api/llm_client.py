from __future__ import annotations
import logging
import os
import random
from typing import Any, Dict, Iterable, Optional, Tuple, List, Sequence, Set
import requests
from api.generation.task_quality import score_task_quality
from api.generation.design_quality import score_design_discipline
from api.generation.experience_quality import score_experience
from api.generation.prompts import PREMIUM_PLAN_SCHEMA
from api.llm_parsing import _normalize_doc
from api.generation.novelty import novelty_summary
from api.generation.output_parsing import (
    extract_completed_premium_burst_sites as _extract_completed_premium_burst_sites,
    extract_final_html_blocks as _extract_final_html_blocks,
    extract_gemini_text as _parse_gemini_text,
)
from api.generation.premium_prompts import (
    build_premium_burst_prompt as _build_premium_burst_prompt_impl,
    build_premium_page_prompt as _build_premium_page_prompt_impl,
    build_premium_plan_prompt as _build_premium_plan_prompt_impl,
)
from api.generation.premium_quality import (
    attach_premium_evaluations as _attach_premium_evaluations_impl,
    attach_quality_score as _attach_quality_score_impl,
)
from api.generation.provider_gemini import (
    call_structured as _provider_call_structured,
    call_text as _provider_call_text,
    high_demand_retry_after_seconds as _gemini_high_demand_retry_after_seconds,
    is_high_demand_response as _gemini_is_high_demand_response,
    is_high_demand_blocked as _gemini_high_demand_blocked,
    iter_stream_text as _provider_iter_stream_text,
    mark_high_demand as _gemini_mark_high_demand,
    was_quota_exhausted,
)
from api.preflight import annotate_doc as _annotate_preflight_doc
from api.preflight import has_blocking_issues as _preflight_has_blocking_issues
from api.preflight import preflight_doc as _preflight_doc
from api.quality import score_page_doc
from api.generation.interaction_catalog import (
    seeded_diverse_format_first_targets,
    seeded_format_first_target,
    seeded_genre_contract,
)
from api.generation.redis_diversity import recent_format_memory
from api.generation.task_model import task_model_for_format
from api.generation.visual_spec import visual_spec_for_target
from api.settings import SETTINGS


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

TEMPERATURE = SETTINGS.llm.temperature
BURST_SITE_COUNT = SETTINGS.llm.burst_site_count
LLM_MAX_TOKENS = SETTINGS.llm.max_tokens
LLM_TIMEOUT_SECS = SETTINGS.llm.timeout_seconds
GEMINI_MAX_OUTPUT_TOKENS = SETTINGS.llm.gemini_max_output_tokens
GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS = SETTINGS.llm.premium_build_max_output_tokens
PREMIUM_BURST_MIN_HTML_BYTES = SETTINGS.llm.premium_burst_min_html_bytes
GEMINI_THINKING_LEVEL = SETTINGS.llm.thinking_level
GEMINI_API_KEY = SETTINGS.llm.api_key
_ENV_GEMINI_API_KEY = GEMINI_API_KEY

GEMINI_GENERATION_MODEL = SETTINGS.llm.generation_model
GEMINI_FALLBACK_MODEL = SETTINGS.llm.fallback_model
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


def _experience_fields_from_task(target: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
    controls = task.get("controls") if isinstance(task.get("controls"), list) else []
    first_control = controls[0] if controls and isinstance(controls[0], dict) else {}
    first_label = str(first_control.get("label") or "Try the main action").strip()
    user_goal = str(task.get("user_goal") or target.get("format_spec", {}).get("implementation_goal") or "Try the activity.").strip()
    completion = str(task.get("completion_condition") or target.get("format_spec", {}).get("payoff") or "a visible result updates").strip()
    payoff_scene = task.get("payoff_scene") if isinstance(task.get("payoff_scene"), dict) else {}
    payoff_scene_text = str(payoff_scene.get("scene") or completion).strip()
    payoff_continue = str(payoff_scene.get("continue_action") or f"Improve, complete, compare, or replay the {str(task.get('format') or 'activity').replace('_', ' ')}.").strip()
    state_vars = task.get("state_variables") if isinstance(task.get("state_variables"), list) else []
    state_change = ", ".join(str(item) for item in state_vars[:3]) or "the visible state"
    format_category = str(target.get("format_category") or "")
    if format_category in {"microgame", "platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game"}:
        visitor_role = "player"
    elif format_category == "product_or_storefront":
        visitor_role = "shopper"
    elif format_category in {"saas_replica", "commerce_or_booking_flow", "fake_os_app"}:
        visitor_role = "operator"
    elif format_category == "creative_tool":
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
        score_task_quality=score_task_quality,
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
    if _gemini_high_demand_blocked():
        return {
            "error": "model_temporarily_unavailable",
            "retry_after_seconds": _gemini_high_demand_retry_after_seconds(),
        }

    plan = _call_gemini_premium_plan(brief_str, seed_val, user_key)
    if not isinstance(plan, dict):
        if was_quota_exhausted():
            return {"error": "model_quota_exhausted"}
        if _gemini_high_demand_blocked():
            return {
                "error": "model_temporarily_unavailable",
                "retry_after_seconds": _gemini_high_demand_retry_after_seconds(),
            }
        return {"error": "Premium planner failed"}

    raw_doc = _call_gemini_premium_build(brief_str, seed_val, plan)
    if not isinstance(raw_doc, dict):
        if was_quota_exhausted():
            return {"error": "model_quota_exhausted"}
        if _gemini_high_demand_blocked():
            return {
                "error": "model_temporarily_unavailable",
                "retry_after_seconds": _gemini_high_demand_retry_after_seconds(),
            }
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
    if _gemini_high_demand_blocked():
        yield {
            "error": "model_temporarily_unavailable",
            "retry_after_seconds": _gemini_high_demand_retry_after_seconds(),
        }
        return

    memory = recent_format_memory(limit=20)
    base_targets = seeded_diverse_format_first_targets(
        seed_val,
        target_count,
        recent_format_ids=memory.get("format_ids"),
        recent_format_families=memory.get("format_families"),
        recent_interaction_loops=memory.get("interaction_loops"),
        recent_reward_mechanics=memory.get("reward_mechanics"),
    )
    targets = []
    visual_reservations: Dict[str, List[str]] = {
        "palettes": list(memory.get("visual_palettes") or [])[:4],
        "layout_signatures": list(memory.get("layout_signatures") or memory.get("compositions") or [])[:12],
        "silhouette_families": [],
        "rendered_layout_families": list(memory.get("rendered_layout_families") or [])[:8],
    }
    for idx, base_target in enumerate(base_targets):
        site_seed = seed_val + ((idx + 1) * 7919)
        base_target["_visual_reservations"] = visual_reservations
        target = _premium_experience_target(site_seed, base_target=base_target)
        target["site_index"] = idx + 1
        target["seed"] = site_seed
        targets.append(target)
        spec = target.get("visual_spec") if isinstance(target.get("visual_spec"), dict) else {}
        for key, spec_key in (("palettes", "palette_id"), ("layout_signatures", "composition")):
            value = str(spec.get(spec_key) or "").strip()
            if value and value not in visual_reservations[key]:
                visual_reservations[key].append(value)
        silhouette_family = str((spec.get("layout_model") or {}).get("silhouette_family") or "").strip()
        if silhouette_family and silhouette_family not in visual_reservations["silhouette_families"]:
            visual_reservations["silhouette_families"].append(silhouette_family)

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
            if _gemini_is_high_demand_response(resp):
                _gemini_mark_high_demand(f"premium burst {label}")
                all_429 = False
                break
            if resp.status_code != 429:
                all_429 = False
            continue
        all_429 = False  # endpoint responded, not all-429
        full_text = ""
        emitted: Set[int] = set()
        emitted_count = 0
        try:
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
        except requests.exceptions.RequestException as exc:
            logging.warning(
                "Gemini premium burst %s stream interrupted after %d accepted sites: %r",
                label,
                emitted_count,
                exc,
            )
            if emitted_count:
                return
            all_429 = False
            continue
        if emitted_count:
            return
        logging.warning("Gemini premium burst %s produced no valid sites; text_len=%d", label, len(full_text))
    if all_429:
        yield {"error": "model_quota_exhausted"}
    elif _gemini_high_demand_blocked():
        yield {
            "error": "model_temporarily_unavailable",
            "retry_after_seconds": _gemini_high_demand_retry_after_seconds(),
        }
    else:
        yield {"error": "Premium burst failed"}


def _premium_experience_target(seed: int, base_target: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    memory: Dict[str, Any] = {}
    visual_reservations: Dict[str, Any] = {}
    if isinstance(base_target, dict):
        target = dict(base_target)
        visual_reservations = target.pop("_visual_reservations", {})
    else:
        memory = recent_format_memory(limit=20)
        visual_reservations = {
            "palettes": memory.get("visual_palettes") or [],
            "layout_signatures": memory.get("layout_signatures") or memory.get("compositions") or [],
            "rendered_layout_families": memory.get("rendered_layout_families") or [],
        }
        target = seeded_format_first_target(
            seed,
            recent_format_ids=memory.get("format_ids"),
            recent_format_families=memory.get("format_families"),
            recent_interaction_loops=memory.get("interaction_loops"),
            recent_reward_mechanics=memory.get("reward_mechanics"),
        )
    archetype = str(target["interaction_pattern"])
    loop_type = str(target["interaction_loop"])
    task = task_model_for_format(
        str(target["format_spec"]["format_id"]),
        str(target["format_category"]),
    )
    experience_fields = _experience_fields_from_task(target, task)
    visual_spec = visual_spec_for_target(
        seed=seed,
        format_category=str(target["format_category"]),
        format_id=str(target["format_spec"]["format_id"]),
        task_model=task,
        library_profile=str(target["format_spec"].get("library_profile") or ""),
        reserved=visual_reservations,
    )
    return {
        **target,
        **experience_fields,
        "reward_mechanic": task.get("reward_mechanic"),
        "reward_contract": task.get("reward_contract"),
        "task_model": task,
        "genre_contract": seeded_genre_contract(seed, archetype, loop_type),
        "visual_spec": visual_spec,
        "title_policy": "The concrete format name remains dominant. If the page itself names a material or object in a title or major label, visibly support that claim through the interface; otherwise keep the claim out of copy.",
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
        # The model only supplies a compact creative brief. Every product, task,
        # reward, and visual-system contract remains deterministic backend state.
        return {**out, **experience_target}
    return None


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
