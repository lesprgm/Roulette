from __future__ import annotations

import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import yaml

from api.generation.layout_model import copy_budget_for_category, layout_model_for_target
from api.generation.task_model import category_for_format


_LOCAL_COLOR_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "color_strategies.yaml"
_SECRET_COLOR_CATALOG_PATH = Path("/etc/secrets/color_strategies.yaml")
_CONFIGURED_COLOR_CATALOG_PATH = os.getenv("COLOR_STRATEGIES_PATH", "").strip()
_COLOR_CATALOG_PATH = (
    Path(_CONFIGURED_COLOR_CATALOG_PATH).expanduser()
    if _CONFIGURED_COLOR_CATALOG_PATH
    else _SECRET_COLOR_CATALOG_PATH if _SECRET_COLOR_CATALOG_PATH.exists() else _LOCAL_COLOR_CATALOG_PATH
)
_LOCAL_COMPONENT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "component_languages.yaml"
_SECRET_COMPONENT_CATALOG_PATH = Path("/etc/secrets/component_languages.yaml")
_CONFIGURED_COMPONENT_CATALOG_PATH = os.getenv("COMPONENT_LANGUAGES_PATH", "").strip()
_COMPONENT_CATALOG_PATH = (
    Path(_CONFIGURED_COMPONENT_CATALOG_PATH).expanduser()
    if _CONFIGURED_COMPONENT_CATALOG_PATH
    else _SECRET_COMPONENT_CATALOG_PATH if _SECRET_COMPONENT_CATALOG_PATH.exists() else _LOCAL_COMPONENT_CATALOG_PATH
)
_COLOR_ROLES = {"background", "surface", "ink", "surface_ink", "action", "secondary"}
_COMPONENT_FIELDS = ("geometry", "borders", "elevation", "spacing", "typography", "controls")
_COLOR_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_CATEGORIES = {"game", "product", "commerce", "creative_tool", "simulation", "investigation", "app"}


def _load_color_catalog() -> tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]], Dict[str, tuple[str, ...]]]:
    try:
        payload = yaml.safe_load(_COLOR_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid color strategy catalog {_COLOR_CATALOG_PATH}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RuntimeError("Color strategy catalog must use version 1")
    raw_strategies = payload.get("strategies")
    raw_compatibility = payload.get("compatibility")
    if not isinstance(raw_strategies, dict) or not raw_strategies:
        raise RuntimeError("Color strategy catalog must define strategies")
    if not isinstance(raw_compatibility, dict) or set(raw_compatibility) != _CATEGORIES:
        raise RuntimeError("Color strategy compatibility must cover every format category")

    systems: Dict[str, Dict[str, str]] = {}
    behaviors: Dict[str, Dict[str, str]] = {}
    for strategy_id, raw in raw_strategies.items():
        if not isinstance(strategy_id, str) or not _COLOR_ID_RE.fullmatch(strategy_id) or not isinstance(raw, dict):
            raise RuntimeError(f"Invalid color strategy {strategy_id!r}")
        colors = raw.get("colors")
        if not isinstance(colors, dict) or set(colors) != _COLOR_ROLES:
            raise RuntimeError(f"Color strategy {strategy_id!r} must define {_COLOR_ROLES}")
        if not all(isinstance(value, str) and _HEX_RE.fullmatch(value) for value in colors.values()):
            raise RuntimeError(f"Color strategy {strategy_id!r} contains an invalid color")
        if not all(isinstance(raw.get(key), str) and raw[key].strip() for key in ("hierarchy", "surface")):
            raise RuntimeError(f"Color strategy {strategy_id!r} must define hierarchy and surface guidance")
        systems[strategy_id] = dict(colors)
        behaviors[strategy_id] = {"hierarchy": raw["hierarchy"].strip(), "surface": raw["surface"].strip()}

    compatibility: Dict[str, tuple[str, ...]] = {}
    for category, weights in raw_compatibility.items():
        if not isinstance(weights, dict) or not weights:
            raise RuntimeError(f"Color compatibility {category!r} must define weighted strategies")
        unknown = set(weights) - systems.keys()
        if unknown or not all(isinstance(weight, int) and weight > 0 for weight in weights.values()):
            raise RuntimeError(f"Color compatibility {category!r} has invalid entries: {sorted(unknown)}")
        compatibility[category] = tuple(
            strategy_id
            for strategy_id, weight in weights.items()
            for _ in range(weight)
        )
    return systems, behaviors, compatibility


PALETTE_SYSTEMS, PALETTE_BEHAVIOR, PALETTE_COMPATIBILITY = _load_color_catalog()


def _load_component_catalog() -> tuple[Dict[str, Dict[str, str]], Dict[str, tuple[str, ...]]]:
    try:
        payload = yaml.safe_load(_COMPONENT_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid component language catalog {_COMPONENT_CATALOG_PATH}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RuntimeError("Component language catalog must use version 1")
    raw_languages = payload.get("languages")
    raw_compatibility = payload.get("compatibility")
    if not isinstance(raw_languages, dict) or not raw_languages:
        raise RuntimeError("Component language catalog must define languages")
    if not isinstance(raw_compatibility, dict) or set(raw_compatibility) != _CATEGORIES:
        raise RuntimeError("Component language compatibility must cover every format category")

    languages: Dict[str, Dict[str, str]] = {}
    for language_id, guidance in raw_languages.items():
        if (
            not isinstance(language_id, str)
            or not _COLOR_ID_RE.fullmatch(language_id)
            or not isinstance(guidance, dict)
            or set(guidance) != set(_COMPONENT_FIELDS)
            or not all(isinstance(value, str) and value.strip() for value in guidance.values())
        ):
            raise RuntimeError(f"Invalid component language {language_id!r}")
        languages[language_id] = {key: guidance[key].strip() for key in _COMPONENT_FIELDS}

    compatibility: Dict[str, tuple[str, ...]] = {}
    for category, language_ids in raw_compatibility.items():
        if not isinstance(language_ids, list) or len(language_ids) < 7 or len(set(language_ids)) != len(language_ids):
            raise RuntimeError(f"Component compatibility {category!r} must define at least seven unique languages")
        unknown = set(language_ids) - languages.keys()
        if unknown:
            raise RuntimeError(f"Component compatibility {category!r} has unknown languages: {sorted(unknown)}")
        compatibility[category] = tuple(language_ids)
    return languages, compatibility


COMPONENT_LANGUAGES, COMPONENT_LANGUAGE_COMPATIBILITY = _load_component_catalog()


_SUBJECTS = {
    "game": "game board, pieces, targets, and score state",
    "product": "product object, option state, and cart or receipt",
    "commerce": "selected items, route or ticket, and checkout result",
    "creative_tool": "created artifact, active tool, and export or save result",
    "simulation": "reactive scene, changed material state, and reset result",
    "investigation": "evidence objects, selected record, and solved or saved state",
    "app": "real starter records, selection, and saved workflow result",
}

_CANVAS_TOOLS = {"falling_sand_lab", "drawing_studio", "room_layout_builder"}
_SVG_TOOLS = {"map_route_planner", "poster_generator", "avatar_customizer"}


def _artwork_strategy(category: str, subject: str) -> str:
    strategies = {
        "game": f"Make {subject} a complete visible play scene with recognizable pieces, spatial relationships, and state feedback.",
        "product": f"Depict {subject} as recognizable product or collection artwork through original SVG, CSS illustration, or task-native 3D; swatches and icons alone do not count.",
        "commerce": f"Make {subject} visually browsable through appropriate item, destination, route, ticket, dish, or order imagery; text-only listings and icons do not count.",
        "creative_tool": f"Keep the evolving {subject} artifact or preview visually dominant, with tools attached to what they change.",
        "simulation": f"Render {subject} as an interpretable scene whose objects visibly react to input and preserve changed state.",
        "investigation": f"Turn {subject} into evidence imagery, annotated comparisons, charts, maps, or document previews that support the actual conclusion.",
        "app": f"Represent {subject} through task-native records plus meaningful charts, previews, avatars, diagrams, thumbnails, or status imagery instead of text panels alone.",
    }
    return strategies[category]


_SURFACE_TREATMENTS: Dict[str, tuple[str, ...]] = {
    "game": ("none", "none", "none", "css_material", "inline_svg_texture", "paper_shader"),
    "product": ("none", "none", "none", "none", "css_material", "inline_svg_texture", "paper_shader"),
    "commerce": ("none", "none", "none", "none", "css_material", "inline_svg_texture", "paper_shader"),
    "creative_tool": ("none", "none", "none", "css_material", "inline_svg_texture", "paper_shader", "paper_shader"),
    "simulation": ("none", "none", "none", "css_material", "inline_svg_texture", "paper_shader", "paper_shader"),
    "investigation": ("none", "none", "none", "none", "css_material", "inline_svg_texture", "paper_shader"),
    "app": ("none", "none", "none", "none", "none", "css_material", "inline_svg_texture", "paper_shader"),
}

PAPER_SHADER_PRESETS = (
    "paperTexture",
    "staticMeshGradient",
    "voronoi",
    "metaballs",
    "flutedGlass",
    "liquidMetal",
    "halftoneDots",
    "halftoneCMYK",
    "godRays",
)

_SURFACE_GUIDANCE = {
    "none": "Do not add a decorative texture treatment; let task-native content, type, spacing, and state carry the surface.",
    "css_material": "Use restrained CSS gradients, shadows, borders, or pseudo-elements on the named subject where material depth supports it.",
    "inline_svg_texture": "Use an original inline SVG pattern, mask, or filter on the named subject; it must clarify material or state rather than become wallpaper.",
    "paper_shader": "Mount one local Paper Shader on the named subject with a CSS fallback and bounded pixel budget; it must respond to or reinforce visible state and must not cover the whole page.",
}

def _surface_treatment(
    category: str,
    subject: str,
    rng: random.Random,
    required_preset: str = "",
    paper_shader_allowed: bool = True,
) -> Dict[str, str]:
    candidates = list(_SURFACE_TREATMENTS[category])
    if not paper_shader_allowed:
        candidates = [candidate for candidate in candidates if candidate != "paper_shader"]
    mode = "paper_shader" if required_preset else rng.choice(candidates)
    return {
        "mode": mode,
        "preset": required_preset if mode == "paper_shader" else "",
        "target": subject if mode != "none" else "",
        "guidance": (
            f"{_SURFACE_GUIDANCE[mode]} Use the `{required_preset}` preset."
            if required_preset
            else _SURFACE_GUIDANCE[mode]
        ),
    }


def _renderer_profile(
    format_id: str,
    category: str,
    library_profile: str,
    capabilities: Iterable[str],
) -> tuple[str, list[str]]:
    capability_set = set(capabilities)
    if not capability_set:
        if library_profile == "matter_physics_game":
            capability_set.add("physics_2d")
        elif library_profile in {"three_orbit_scene", "three_bloom_scene"}:
            capability_set.add("spatial_3d")
        if category in {"app", "commerce", "product", "investigation"}:
            capability_set.update({"reactive_state", "app_iconography", "sequenced_motion"})
        elif library_profile in {"alpine_ui_state", "dom_css_state_machine"}:
            capability_set.add("reactive_state")
        if library_profile in {"gsap_state_transition", "gsap_timeline_dom"}:
            capability_set.add("sequenced_motion")
    if "physics_2d" in capability_set:
        primary = "matter_scene"
    elif "spatial_3d" in capability_set:
        primary = "three_scene"
    elif category == "creative_tool" and format_id in _CANVAS_TOOLS:
        primary = "canvas_scene"
    elif category == "creative_tool" and format_id in _SVG_TOOLS:
        primary = "inline_svg"
    elif category in {"app", "commerce", "product", "investigation", "creative_tool"}:
        primary = "semantic_dom"
    elif library_profile in {"dom_css_state_machine", "alpine_ui_state", "gsap_state_transition", "gsap_timeline_dom"}:
        primary = "semantic_dom"
    else:
        primary = "canvas_scene"

    supporting = ["semantic_dom"] if primary != "semantic_dom" else ["inline_svg"]
    if "reactive_state" in capability_set:
        supporting.append("alpine_state")
    if "direct_manipulation" in capability_set:
        supporting.append("draggable_motion")
    if "sequenced_motion" in capability_set:
        supporting.append("gsap_motion")
    if "app_iconography" in capability_set:
        supporting.append("lucide_icons")
    return primary, list(dict.fromkeys(supporting))


def _first_available(candidates: Iterable[str], reserved: set[str], rng: random.Random) -> str:
    available = [candidate for candidate in candidates if candidate not in reserved]
    return rng.choice(available or list(candidates))


def visual_spec_for_target(
    *,
    seed: int,
    format_category: str,
    format_id: str,
    task_model: Mapping[str, Any],
    library_profile: str = "",
    capabilities: Iterable[str] = (),
    authorship_mode: str = "guided",
    reserved: Mapping[str, Iterable[str]] | None = None,
    paper_shader_preset: str = "",
    paper_shader_allowed: bool = True,
) -> Dict[str, Any]:
    """Build a compact visual specification from the selected format."""
    rng = random.Random(f"{seed}:{format_id}:visual-specification")
    used = {key: set(values) for key, values in (reserved or {}).items()}
    category = category_for_format(format_id, format_category)
    primary, supporting = _renderer_profile(format_id, category, library_profile, capabilities)
    guided = authorship_mode != "authored"
    palette_id = rng.choice(PALETTE_COMPATIBILITY[category]) if guided else ""
    layout_model = layout_model_for_target(
        seed=seed,
        category=category,
        task_model=task_model,
        reserved_signatures=used.get("layout_signatures", used.get("compositions", set())),
        reserved_silhouette_families=used.get("silhouette_families", set()),
        recent_rendered_families=used.get("rendered_layout_families", set()),
    )
    if not guided:
        layout_model = {**layout_model, "composition_mode": "authored"}
    objects = [str(value).replace("_", " ") for value in task_model.get("domain_objects", []) if str(value).strip()]
    subject = ", ".join(objects[:3]) or _SUBJECTS[category]
    surface_treatment = _surface_treatment(
        category,
        subject,
        rng,
        paper_shader_preset,
        paper_shader_allowed,
    )
    component_language_id = (
        _first_available(
            COMPONENT_LANGUAGE_COMPATIBILITY[category],
            used.get("component_languages", set()),
            rng,
        )
        if guided
        else ""
    )
    if surface_treatment["mode"] == "paper_shader" and "paper_surface" not in supporting:
        supporting.append("paper_surface")
    return {
        "authorship_mode": authorship_mode,
        "capabilities": sorted(set(capabilities)),
        "palette_id": palette_id,
        "palette": PALETTE_SYSTEMS[palette_id] if guided else {},
        "composition": layout_model["signature"],
        "layout_model": layout_model,
        "copy_budget": copy_budget_for_category(category),
        "primary_renderer": primary,
        "supporting_renderers": supporting,
        "visual_subject": subject,
        "component_language": (
            {"id": component_language_id, **COMPONENT_LANGUAGES[component_language_id]}
            if guided
            else {}
        ),
        "visual_direction": {
            "palette_behavior": (
                PALETTE_BEHAVIOR[palette_id]
                if guided
                else "Author a coherent light-first palette appropriate to the concrete format. Choose restrained tonal relationships and purposeful contrast; do not imitate another site in the burst."
            ),
            "subject_artwork": _artwork_strategy(category, subject),
            "surface_treatment": surface_treatment,
        },
        "state_binding": "The primary subject must visibly change with task-model state and payoff.",
        "thumbnail_rule": "The page should be identifiable from the primary subject before its body copy is read.",
    }
