from __future__ import annotations

import random
from typing import Any, Dict, Iterable, Mapping

from api.generation.layout_model import copy_budget_for_category, layout_model_for_target
from api.generation.task_model import category_for_format


# These are anchor systems, not fixed themes. The builder may derive tonal variations,
# while burst reservations keep neighboring sites from sharing the same color world.
PALETTE_SYSTEMS: Dict[str, Dict[str, str]] = {
    "high_key_pop": {"background": "#F4FF5C", "surface": "#FF5A9D", "ink": "#171717", "surface_ink": "#171717", "action": "#2457FF", "secondary": "#FF6B00"},
    "editorial_contrast": {"background": "#FFF5E5", "surface": "#1947E5", "ink": "#17120F", "surface_ink": "#FFFFFF", "action": "#FF4B24", "secondary": "#00A37A"},
    "primary_blocks": {"background": "#BDEAFF", "surface": "#FFE23F", "ink": "#10233F", "surface_ink": "#10233F", "action": "#E94335", "secondary": "#1457C8"},
    "citrus_cobalt": {"background": "#FFF36D", "surface": "#F7F2E8", "ink": "#16265C", "surface_ink": "#16265C", "action": "#1546D8", "secondary": "#FF5D35"},
    "aqua_coral": {"background": "#B9F4EA", "surface": "#FF725E", "ink": "#153A37", "surface_ink": "#25110E", "action": "#075FD8", "secondary": "#FFE14A"},
    "natural_pigment": {"background": "#F2E8CD", "surface": "#B8D46B", "ink": "#302A21", "surface_ink": "#243019", "action": "#C64A36", "secondary": "#356B68"},
    "candy_plastic": {"background": "#FFD8EF", "surface": "#8DEBFF", "ink": "#322044", "surface_ink": "#172D38", "action": "#F03E72", "secondary": "#7357E6"},
    "graphic_monochrome": {"background": "#F5F5EF", "surface": "#232323", "ink": "#161616", "surface_ink": "#FFFFFF", "action": "#FF3B30", "secondary": "#2D63FF"},
    "poolside_sun": {"background": "#C8F3FF", "surface": "#FFF06A", "ink": "#12364A", "surface_ink": "#24320B", "action": "#F4512A", "secondary": "#008C83"},
    "tomato_leaf": {"background": "#FFE7D6", "surface": "#E94B35", "ink": "#26362A", "surface_ink": "#FFF9F2", "action": "#176B45", "secondary": "#F6C945"},
    "violet_lime": {"background": "#EEE4FF", "surface": "#CFFF48", "ink": "#30254A", "surface_ink": "#26320D", "action": "#6C3CCF", "secondary": "#FF6847"},
    "blueprint_peach": {"background": "#DCEBFF", "surface": "#FFCAA8", "ink": "#17365D", "surface_ink": "#3B2417", "action": "#1C66D6", "secondary": "#EA4B3D"},
}


_CATEGORY_VISUALS = {
    "game": (["canvas_scene", "canvas_scene", "canvas_scene", "inline_svg", "inline_svg"], ["inline_svg", "gsap_motion"], "game board, pieces, targets, and score state"),
    "product": (["inline_svg", "inline_svg", "canvas_scene"], ["paper_surface", "gsap_motion"], "product object, option state, and cart or receipt"),
    "commerce": (["inline_svg", "canvas_scene", "inline_svg"], ["gsap_motion", "alpine_state"], "selected items, route or ticket, and checkout result"),
    "creative_tool": (["canvas_scene", "canvas_scene", "canvas_scene", "inline_svg", "inline_svg"], ["inline_svg", "gsap_motion"], "created artifact, active tool, and export or save result"),
    "simulation": (["canvas_scene", "canvas_scene", "canvas_scene", "inline_svg", "inline_svg"], ["paper_surface", "gsap_motion"], "reactive scene, changed material state, and reset result"),
    "investigation": (["inline_svg", "inline_svg", "inline_svg", "canvas_scene", "canvas_scene"], ["gsap_motion", "alpine_state"], "evidence objects, selected record, and solved or saved state"),
    "app": (["inline_svg", "canvas_scene", "inline_svg"], ["alpine_state", "gsap_motion"], "real starter records, selection, and saved workflow result"),
}


def _first_available(candidates: Iterable[str], reserved: set[str], rng: random.Random) -> str:
    available = [candidate for candidate in candidates if candidate not in reserved]
    return rng.choice(available or list(candidates))


def visual_spec_for_target(
    *,
    seed: int,
    format_category: str,
    format_id: str,
    task_model: Mapping[str, Any],
    reserved: Mapping[str, Iterable[str]] | None = None,
) -> Dict[str, Any]:
    """Build a compact visual specification from the selected format."""
    rng = random.Random(f"{seed}:{format_id}:visual-specification")
    used = {key: set(values) for key, values in (reserved or {}).items()}
    category = category_for_format(format_id, format_category)
    primary_renderers, supporting, fallback_subject = _CATEGORY_VISUALS[category]
    primary = _first_available(primary_renderers, used.get("primary_renderers", set()), rng)
    palette_id = _first_available(PALETTE_SYSTEMS.keys(), used.get("palettes", set()), rng)
    layout_model = layout_model_for_target(
        seed=seed,
        category=category,
        task_model=task_model,
        reserved_signatures=used.get("layout_signatures", used.get("compositions", set())),
        reserved_silhouette_families=used.get("silhouette_families", set()),
        recent_rendered_families=used.get("rendered_layout_families", set()),
    )
    objects = [str(value).replace("_", " ") for value in task_model.get("domain_objects", []) if str(value).strip()]
    subject = ", ".join(objects[:3]) or fallback_subject
    return {
        "palette_id": palette_id,
        "palette": PALETTE_SYSTEMS[palette_id],
        "composition": layout_model["signature"],
        "layout_model": layout_model,
        "copy_budget": copy_budget_for_category(category),
        "primary_renderer": primary,
        "supporting_renderers": supporting,
        "visual_subject": subject,
        "state_binding": "The primary subject must visibly change with task-model state and payoff.",
        "thumbnail_rule": "The page should be identifiable from the primary subject before its body copy is read.",
    }
