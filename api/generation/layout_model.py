from __future__ import annotations

import random
from typing import Any, Dict, Iterable, Mapping


_REGIONS = {
    "game": ("playfield", "score", "controls", "result"),
    "product": ("product", "options", "purchase", "confirmation"),
    "commerce": ("catalog_or_map", "filters", "selection", "confirmation"),
    "creative_tool": ("artifact", "tools", "settings", "export_result"),
    "simulation": ("scene", "controls", "state_readout", "result"),
    "investigation": ("evidence", "filters", "detail", "resolved_state"),
    "app": ("workspace", "command_bar", "records", "saved_result"),
}

_PRIMARY_GEOMETRIES = {
    "full_bleed": {
        "mobile": "edge_to_edge_bottom_sheet",
        "implementation": "Use an edge-to-edge 100vw x 100dvh composition. The primary subject occupies at least 70vw and 65dvh. No centered app-card wrapper.",
    },
    "vertical_journey": {
        "mobile": "compact_single_column",
        "implementation": "Use three full-width vertical zones with distinct scale and spacing. The primary zone spans at least 80vw; this is a page journey, not one centered card.",
    },
    "offset_canvas": {
        "mobile": "remove_overlap_then_stack",
        "implementation": "Place the primary subject off-center across at least 65vw with one overlapping edge region. Preserve visible negative space on the opposite side; no symmetric card shell.",
    },
    "mosaic_focus": {
        "mobile": "primary_then_compact_grid",
        "implementation": "Use an asymmetric 12-column mosaic: one dominant 7-9 column subject and 2-3 smaller regions with unequal spans. Do not reduce it to a uniform card grid.",
    },
    "poster_field": {
        "mobile": "poster_with_anchored_tray",
        "implementation": "Use the full viewport as one poster field with at least three independently positioned zones and a dominant visual covering roughly half the field. No enclosing card.",
    },
}

_CONTROL_RELATIONS = ("floating_tray", "bottom_dock", "top_ribbon", "inline_cluster", "collapsible_sheet")

_RESULT_RELATIONS = ("replace_controls", "bottom_sheet", "stage_overlay", "inline_after", "focused_modal")

_VIEWPORT_CONTRACT = {
    "root_width": "100vw",
    "root_min_height": "100dvh",
    "min_composed_width": "88vw",
    "min_composed_height": "78dvh",
    "max_blank_area": "40%",
    "single_card_shell": False,
}

_COPY_BUDGETS = {
    "game": (50, "Use labels, score, and one micro-cue; rules should be learned through play."),
    "product": (105, "Keep only product identity, essential value, options, price, and purchase confirmation."),
    "commerce": (90, "Use concise item, route, booking, total, and confirmation copy."),
    "creative_tool": (70, "Let tools and the artifact explain the workflow; avoid tutorial paragraphs."),
    "simulation": (55, "Use one micro-cue and visible state labels; cause and effect should explain the experience."),
    "investigation": (100, "Keep evidence readable but remove atmospheric filler and repeated instructions."),
    "app": (90, "Use realistic records and action labels instead of explanatory product copy."),
}


def _pick(values: Iterable[str], reserved: set[str], rng: random.Random) -> str:
    candidates = list(values)
    available = [value for value in candidates if value not in reserved]
    return rng.choice(available or candidates)


def layout_model_for_target(
    *,
    seed: int,
    category: str,
    task_model: Mapping[str, Any],
    reserved_signatures: Iterable[str] = (),
    recent_rendered_families: Iterable[str] = (),
) -> Dict[str, Any]:
    """Compose a concrete spatial graph from reusable regions and relations."""
    rng = random.Random(f"{seed}:{task_model.get('format')}:{category}:layout")
    reserved = set(reserved_signatures)
    recent = " ".join(recent_rendered_families)
    combinations = [
        (geometry, controls, result)
        for geometry in _PRIMARY_GEOMETRIES
        for controls in _CONTROL_RELATIONS
        for result in _RESULT_RELATIONS
        if not (geometry == "vertical_journey" and controls == "floating_tray")
        and not (geometry == "full_bleed" and controls == "inline_cluster")
        and not ("bottom_dock" in recent and controls == "bottom_dock")
        and not ("fixed_layer" in recent and controls in {"floating_tray", "collapsible_sheet"})
        and not ("explicit_grid" in recent and geometry == "mosaic_focus")
        and not ("side_region" in recent and geometry == "offset_canvas")
    ]
    if not combinations:
        combinations = [("vertical_journey", "inline_cluster", "inline_after")]
    signatures = [":".join(combo) for combo in combinations]
    signature = _pick(signatures, reserved, rng)
    geometry, controls, result = signature.split(":")
    regions = _REGIONS.get(category, _REGIONS["app"])
    return {
        "signature": signature,
        "nodes": {"primary": regions[0], "controls": regions[1], "state": regions[2], "result": regions[3]},
        "edges": [
            ["controls", "primary", controls],
            ["state", "primary", "visibly_bound"],
            ["result", "primary", result],
        ],
        "desktop_geometry": geometry,
        "geometry_contract": _PRIMARY_GEOMETRIES[geometry]["implementation"],
        "viewport_contract": dict(_VIEWPORT_CONTRACT),
        "control_geometry": controls,
        "result_geometry": result,
        "mobile_transformation": _PRIMARY_GEOMETRIES[geometry]["mobile"],
    }


def copy_budget_for_category(category: str) -> Dict[str, Any]:
    maximum, guidance = _COPY_BUDGETS.get(category, _COPY_BUDGETS["app"])
    return {
        "max_visible_words": maximum,
        "max_heading_words": 6,
        "max_instruction_words": 12,
        "guidance": guidance,
    }
