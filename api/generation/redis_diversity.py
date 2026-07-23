from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from api.generation.interaction_catalog import format_family_for_id
from api.generation.experience_quality import score_experience
from api.generation.quality_html import extract_doc_html, visible_text
from api.quality import score_page_doc
from api.settings import SETTINGS

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


REDIS_URL = SETTINGS.storage.redis_url
REDIS_DIVERSITY_ENABLED = SETTINGS.storage.diversity_enabled
HTML_CACHE_TTL_SECONDS = SETTINGS.storage.diversity_html_cache_ttl_seconds
FINGERPRINT_TTL_SECONDS = SETTINGS.storage.diversity_fingerprint_ttl_seconds

_CLIENT = None
if redis and REDIS_URL and REDIS_DIVERSITY_ENABLED and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        _CLIENT = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        _CLIENT = None

_WORD_RE = re.compile(r"\b[a-z][a-z0-9-]{3,}\b", re.IGNORECASE)


def _client(client: Any = None) -> Any:
    return client if client is not None else _CLIENT


def _recent_values(redis_client: Any, key: str, legacy_key: str, limit: int) -> List[str]:
    values = list(redis_client.zrevrange(key, 0, max(0, limit - 1)) or [])
    if len(values) < limit:
        values.extend(redis_client.zrevrange(legacy_key, 0, max(0, limit - 1)) or [])
    return list(dict.fromkeys(str(value) for value in values if value))[:limit]


def _empty_recent_memory() -> Dict[str, List[str]]:
    return {
        "format_ids": [],
        "format_families": [],
        "interaction_loops": [],
        "reward_mechanics": [],
        "visual_palettes": [],
        "surface_treatments": [],
        "component_languages": [],
        "component_style_signatures": [],
        "compositions": [],
        "layout_signatures": [],
        "silhouette_families": [],
        "rendered_layout_families": [],
        "primary_renderers": [],
    }


def _slug(value: Any, limit: int = 40) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return (text[:limit].strip("_") or "unknown")


def _hash_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _input_modalities(html: str) -> List[str]:
    found: List[str] = []
    checks = [
        ("keyboard", r"keydown|keyup|<input\b|<textarea\b"),
        ("pointer", r"pointer|mousemove|mousedown|click|drag"),
        ("touch", r"touchstart|touchmove|pointerdown"),
        ("scroll", r"scroll|wheel|IntersectionObserver"),
    ]
    for label, pattern in checks:
        if re.search(pattern, html or "", re.IGNORECASE):
            found.append(label)
    return found or ["passive"]


def _dominant_terms(html: str, limit: int = 8) -> List[str]:
    text = visible_text(html, lowercase=True)
    stop = {"with", "from", "this", "that", "into", "your", "html", "body", "main", "section"}
    counts: Dict[str, int] = {}
    for word in _WORD_RE.findall(text):
        if word in stop:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _rendered_layout_family(html: str) -> str:
    lower = (html or "").lower()
    features: List[str] = []
    if "<aside" in lower or re.search(r"\b(sidebar|side-rail|control-rail)\b", lower):
        features.append("side_region")
    if re.search(r"position\s*:\s*(?:absolute|fixed)", lower):
        features.append("layered")
    if re.search(r"grid-template-areas", lower):
        features.append("named_grid")
    elif re.search(r"grid-template-columns", lower):
        features.append("explicit_grid")
    if re.search(r"flex-direction\s*:\s*column", lower):
        features.append("vertical_flow")
    if re.search(r"flex-direction\s*:\s*row", lower):
        features.append("horizontal_flow")
    if re.search(r"\b(bottom-sheet|bottom-dock|dock)\b", lower):
        features.append("bottom_dock")
    if re.search(r"\b(timeline|journey|progress-path|stepper)\b", lower):
        features.append("progressive_path")
    if re.search(r"\b(gallery|masonry|media-sequence)\b", lower):
        features.append("gallery")
    if re.search(r"\b(map|route-canvas|map-stage)\b", lower):
        features.append("map_stage")
    if re.search(r"\b(modal|dialog)\b", lower):
        features.append("modal_payoff")
    if "<canvas" in lower:
        features.append("canvas_stage")
    narrow_widths = [int(value) for value in re.findall(r"max-width\s*:\s*(\d{2,4})px", lower)]
    if narrow_widths and min(narrow_widths) <= 900:
        features.append("narrow_wrapper")
    section_count = len(re.findall(r"<(?:main|section)\b", lower))
    features.append(f"regions_{min(section_count, 5)}")
    return ":".join(features)


def _component_style_signature(html: str) -> str:
    css = (html or "").lower()
    values = []
    for property_name in ("border-radius", "border", "box-shadow", "text-transform"):
        declarations = sorted({
            re.sub(r"\s+", " ", value.strip())
            for value in re.findall(rf"{property_name}\s*:\s*([^;}}{{]+)", css)
        })[:4]
        values.append(f"{property_name}={','.join(declarations) or 'none'}")
    class_tokens = re.findall(r"""class\s*=\s*["']([^"']+)["']""", css)
    panel_tokens = sorted({
        token
        for classes in class_tokens
        for token in classes.split()
        if any(term in token for term in ("card", "panel", "tile", "surface"))
    })[:6]
    values.append(f"panel_tokens={','.join(panel_tokens) or 'none'}")
    return _hash_text("|".join(values))[:16]


def build_site_descriptor(doc: Dict[str, Any], *, site_id: str | None = None) -> Dict[str, Any]:
    html = extract_doc_html(doc)
    debug = doc.get("ndw_debug") if isinstance(doc, dict) else None
    plan = debug.get("premium_plan") if isinstance(debug, dict) else None
    if not isinstance(plan, dict):
        plan = {}
    visual_quality = debug.get("quality_score") if isinstance(debug, dict) else None
    if not isinstance(visual_quality, dict):
        visual_quality = score_page_doc(doc)
    experience_quality = score_experience(doc, plan)
    loop = plan.get("primary_loop") if isinstance(plan.get("primary_loop"), dict) else {}
    format_spec = plan.get("format_spec") if isinstance(plan.get("format_spec"), dict) else {}
    if not format_spec and isinstance(plan.get("activity_contract"), dict):
        format_spec = plan["activity_contract"]
    task_model = plan.get("task_model") if isinstance(plan.get("task_model"), dict) else {}
    if not task_model and isinstance(plan.get("task_contract"), dict):
        task_model = plan["task_contract"]
    format_id = format_spec.get("format_id") or format_spec.get("activity_variant") or task_model.get("format") or ""
    reward_mechanic = (
        plan.get("reward_mechanic")
        or task_model.get("reward_mechanic")
        or format_spec.get("reward_mechanic")
        or ""
    )
    genre_contract = plan.get("genre_contract") if isinstance(plan.get("genre_contract"), dict) else {}
    visual_spec = plan.get("visual_spec") if isinstance(plan.get("visual_spec"), dict) else {}
    if not visual_spec and isinstance(plan.get("visual_recipe"), dict):
        visual_spec = plan["visual_recipe"]
    layout_model = visual_spec.get("layout_model") if isinstance(visual_spec.get("layout_model"), dict) else {}
    visual_direction = visual_spec.get("visual_direction") if isinstance(visual_spec.get("visual_direction"), dict) else {}
    surface_treatment = visual_direction.get("surface_treatment") if isinstance(visual_direction.get("surface_treatment"), dict) else {}
    cell = {
        "interaction_pattern": plan.get("interaction_pattern") or plan.get("experience_archetype") or "unknown",
        "interaction_loop": plan.get("interaction_loop") or plan.get("primary_loop_type") or "unknown",
    }
    descriptor = {
        "site_id": site_id or _hash_text(html)[:16],
        "interaction_pattern": cell["interaction_pattern"],
        "visitor_role": plan.get("visitor_role") or "",
        "visitor_goal": plan.get("visitor_goal") or "",
        "format_category": plan.get("format_category") or plan.get("activity_type") or format_spec.get("format_category") or format_spec.get("activity_type") or "",
        "format_id": format_id,
        "format_family": format_family_for_id(str(format_id)),
        "reward_mechanic": reward_mechanic,
        "visual_palette_id": visual_spec.get("palette_id") or "",
        "surface_treatment": surface_treatment.get("mode") or "none",
        "component_language": (visual_spec.get("component_language") or {}).get("id") or "",
        "component_style_signature": _component_style_signature(html),
        "visual_composition": visual_spec.get("composition") or "",
        "layout_signature": layout_model.get("signature") or visual_spec.get("composition") or "",
        "silhouette_family": layout_model.get("silhouette_family") or "",
        "rendered_layout_family": _rendered_layout_family(html),
        "primary_renderer": visual_spec.get("primary_renderer") or "",
        "chrome_policy": genre_contract.get("chrome_policy") or "",
        "task_format": task_model.get("format") or "",
        "task_goal": task_model.get("user_goal") or "",
        "task_domain_objects": task_model.get("domain_objects") if isinstance(task_model.get("domain_objects"), list) else [],
        "task_state_variables": task_model.get("state_variables") if isinstance(task_model.get("state_variables"), list) else [],
        "task_completion_condition": task_model.get("completion_condition") or "",
        "task_allowed_patterns": task_model.get("allowed_patterns") if isinstance(task_model.get("allowed_patterns"), list) else [],
        "interaction_loop": cell["interaction_loop"],
        "state_change_type": _slug(loop.get("state_change") if isinstance(loop, dict) else ""),
        "input_modality": _input_modalities(html),
        "layout_archetype": plan.get("layout_archetype") or plan.get("layout_key") or "",
        "motion_archetype": plan.get("motion_archetype") or plan.get("motion_preset") or "",
        "rendering_mode": plan.get("rendering_mode") or "",
        "quality_score": visual_quality.get("score", 0),
        "experience_score": experience_quality.get("score", 0),
        "terms": _dominant_terms(html),
        "created_at": int(time.time()),
    }
    return descriptor


def fingerprint_values(descriptor: Dict[str, Any], plan: Dict[str, Any], html: str) -> Dict[str, str]:
    structure = re.sub(r">[^<]+<", "><", html or "")
    structure = re.sub(r"\s+", " ", structure)
    return {
        "descriptor": _hash_json(descriptor),
        "plan": _hash_json(plan),
        "html_structure": _hash_text(structure[:20000]),
    }


def record_generation_event(event: str, fields: Dict[str, Any], client: Any = None) -> None:
    redis_client = _client(client)
    if redis_client is None:
        return
    try:
        payload = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v) for k, v in fields.items()}
        payload["event"] = event
        payload["ts"] = str(int(time.time()))
        redis_client.xadd("generation:events", payload, maxlen=10000, approximate=True)
    except Exception:
        return


def record_site_descriptor(doc: Dict[str, Any], *, event: str = "site_served", client: Any = None) -> Optional[Dict[str, Any]]:
    if not isinstance(doc, dict) or doc.get("error"):
        return None
    redis_client = _client(client)
    if redis_client is None:
        return build_site_descriptor(doc)
    html = extract_doc_html(doc)
    debug = doc.get("ndw_debug") if isinstance(doc, dict) else None
    plan = debug.get("premium_plan") if isinstance(debug, dict) and isinstance(debug.get("premium_plan"), dict) else {}
    descriptor = build_site_descriptor(doc)
    site_id = str(descriptor["site_id"])
    try:
        pipe = redis_client.pipeline()
        pipe.set(f"site:{site_id}:descriptor", json.dumps(descriptor, ensure_ascii=False, separators=(",", ":")))
        pipe.set(f"site:{site_id}:plan", json.dumps(plan, ensure_ascii=False, separators=(",", ":")))
        pipe.set(f"site:{site_id}:quality", json.dumps({
            "visual": (debug or {}).get("quality_score"),
            "experience": score_experience(doc, plan),
        }, ensure_ascii=False, separators=(",", ":")))
        if HTML_CACHE_TTL_SECONDS > 0 and html:
            pipe.setex(f"site:{site_id}:html", HTML_CACHE_TTL_SECONDS, html)
        pipe.zincrby("qd:count:interaction_pattern", 1, str(descriptor["interaction_pattern"]))
        pipe.zincrby("qd:count:interaction_loop", 1, str(descriptor["interaction_loop"]))
        pipe.zincrby("qd:count:format_id", 1, str(descriptor["format_id"]))
        pipe.zincrby("qd:count:format_family", 1, str(descriptor["format_family"]))
        pipe.zincrby("qd:count:reward_mechanic", 1, str(descriptor["reward_mechanic"]))
        pipe.zincrby("qd:count:visual_palette_id", 1, str(descriptor["visual_palette_id"]))
        pipe.zincrby("qd:count:surface_treatment", 1, str(descriptor["surface_treatment"]))
        pipe.zincrby("qd:count:component_language", 1, str(descriptor["component_language"]))
        pipe.zincrby("qd:count:component_style_signature", 1, str(descriptor["component_style_signature"]))
        pipe.zincrby("qd:count:visual_composition", 1, str(descriptor["visual_composition"]))
        pipe.zincrby("qd:count:layout_signature", 1, str(descriptor["layout_signature"]))
        pipe.zincrby("qd:count:silhouette_family", 1, str(descriptor["silhouette_family"]))
        pipe.zincrby("qd:count:rendered_layout_family", 1, str(descriptor["rendered_layout_family"]))
        pipe.zincrby("qd:count:primary_renderer", 1, str(descriptor["primary_renderer"]))
        pipe.zadd("qd:last_used:interaction_loop", {str(descriptor["interaction_loop"]): int(time.time())})
        pipe.zadd("qd:last_used:format_id", {str(descriptor["format_id"]): int(time.time())})
        pipe.zadd("qd:last_used:format_family", {str(descriptor["format_family"]): int(time.time())})
        pipe.zadd("qd:last_used:reward_mechanic", {str(descriptor["reward_mechanic"]): int(time.time())})
        pipe.zadd("qd:last_used:visual_palette_id", {str(descriptor["visual_palette_id"]): int(time.time())})
        pipe.zadd("qd:last_used:surface_treatment", {str(descriptor["surface_treatment"]): int(time.time())})
        pipe.zadd("qd:last_used:component_language", {str(descriptor["component_language"]): int(time.time())})
        pipe.zadd("qd:last_used:component_style_signature", {str(descriptor["component_style_signature"]): int(time.time())})
        pipe.zadd("qd:last_used:visual_composition", {str(descriptor["visual_composition"]): int(time.time())})
        pipe.zadd("qd:last_used:layout_signature", {str(descriptor["layout_signature"]): int(time.time())})
        pipe.zadd("qd:last_used:silhouette_family", {str(descriptor["silhouette_family"]): int(time.time())})
        pipe.zadd("qd:last_used:rendered_layout_family", {str(descriptor["rendered_layout_family"]): int(time.time())})
        pipe.zadd("qd:last_used:primary_renderer", {str(descriptor["primary_renderer"]): int(time.time())})
        for kind, value in fingerprint_values(descriptor, plan, html).items():
            pipe.setex(f"fingerprint:{kind}:{value}", FINGERPRINT_TTL_SECONDS, site_id)
        pipe.execute()
        record_generation_event(event, {
            "site_id": site_id,
            "interaction_pattern": descriptor["interaction_pattern"],
            "interaction_loop": descriptor["interaction_loop"],
            "reward_mechanic": descriptor["reward_mechanic"],
            "quality_score": descriptor["quality_score"],
            "experience_score": descriptor["experience_score"],
        }, client=redis_client)
    except Exception:
        return descriptor
    return descriptor


def recent_format_memory(limit: int = 20, client: Any = None) -> Dict[str, List[str]]:
    redis_client = _client(client)
    if redis_client is None:
        return _empty_recent_memory()
    try:
        format_ids = _recent_values(redis_client, "qd:last_used:format_id", "qd:last_used:activity_variant", limit)
        format_families = _recent_values(redis_client, "qd:last_used:format_family", "qd:last_used:activity_family", limit)
        interaction_loops = _recent_values(redis_client, "qd:last_used:interaction_loop", "qd:last_used:primary_loop_type", limit)
        reward_mechanics = list(redis_client.zrevrange("qd:last_used:reward_mechanic", 0, max(0, limit - 1)) or [])
        visual_palettes = redis_client.zrevrange("qd:last_used:visual_palette_id", 0, max(0, limit - 1)) or []
        surface_treatments = redis_client.zrevrange("qd:last_used:surface_treatment", 0, max(0, limit - 1)) or []
        component_languages = redis_client.zrevrange("qd:last_used:component_language", 0, max(0, limit - 1)) or []
        component_style_signatures = redis_client.zrevrange("qd:last_used:component_style_signature", 0, max(0, limit - 1)) or []
        compositions = redis_client.zrevrange("qd:last_used:visual_composition", 0, max(0, limit - 1)) or []
        layout_signatures = redis_client.zrevrange("qd:last_used:layout_signature", 0, max(0, limit - 1)) or []
        silhouette_families = redis_client.zrevrange("qd:last_used:silhouette_family", 0, max(0, limit - 1)) or []
        rendered_layout_families = redis_client.zrevrange("qd:last_used:rendered_layout_family", 0, max(0, limit - 1)) or []
        primary_renderers = redis_client.zrevrange("qd:last_used:primary_renderer", 0, max(0, limit - 1)) or []
        return {
            "format_ids": format_ids,
            "format_families": format_families,
            "interaction_loops": interaction_loops,
            "reward_mechanics": [str(item) for item in reward_mechanics if item],
            "visual_palettes": [str(item) for item in visual_palettes if item],
            "surface_treatments": [str(item) for item in surface_treatments if item],
            "component_languages": [str(item) for item in component_languages if item],
            "component_style_signatures": [str(item) for item in component_style_signatures if item],
            "compositions": [str(item) for item in compositions if item],
            "layout_signatures": [str(item) for item in layout_signatures if item],
            "silhouette_families": [str(item) for item in silhouette_families if item],
            "rendered_layout_families": [str(item) for item in rendered_layout_families if item],
            "primary_renderers": [str(item) for item in primary_renderers if item],
        }
    except Exception:
        return _empty_recent_memory()
