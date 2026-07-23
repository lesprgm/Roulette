from __future__ import annotations

import os
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import yaml


_LOCAL_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "layout_topologies.yaml"
_SECRET_CATALOG_PATH = Path("/etc/secrets/layout_topologies.yaml")
_CONFIGURED_CATALOG_PATH = os.getenv("LAYOUT_TOPOLOGY_PATH", "").strip()
_CATALOG_PATH = (
    Path(_CONFIGURED_CATALOG_PATH).expanduser()
    if _CONFIGURED_CATALOG_PATH
    else _SECRET_CATALOG_PATH if _SECRET_CATALOG_PATH.exists() else _LOCAL_CATALOG_PATH
)
_TOPOLOGY_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CATEGORIES = (
    "game",
    "product",
    "commerce",
    "creative_tool",
    "simulation",
    "investigation",
    "app",
)
_CATEGORY_SET = frozenset(_CATEGORIES)
_STRUCTURED_LAYOUT_CATEGORIES = frozenset({"app", "commerce", "investigation"})
_REQUIRED_FIELDS = {
    "id",
    "reference_family",
    "categories",
    "regions",
    "desktop_flow",
    "mobile_transformation",
    "control_placement",
    "result_transition",
    "traits",
}
_SILHOUETTE_FIELDS = {
    "viewport_behavior",
    "root_display",
    "root_columns",
    "root_rows",
    "edge_anchors",
    "scroll_axis",
    "dominant_region",
    "control_region",
    "result_region",
    "forbidden_shells",
}

_VIEWPORT_CONTRACTS = {
    "full_bleed": {
        "root_geometry": "Fill the viewport edge to edge; the primary stage reaches at least two viewport edges and is not wrapped in a centered card.",
        "overflow": "Keep the main interaction in the first viewport; overflow only supporting content when needed.",
    },
    "edge_anchored": {
        "root_geometry": "Anchor the major regions to opposing viewport edges with an intentional split or rail; do not center the combined composition as one card.",
        "overflow": "Keep the principal split visible in the first viewport and stack regions in source order on mobile.",
    },
    "scrolling_document": {
        "root_geometry": "Use a full-width document flow with multiple spatially distinct sections; the page must visibly continue beyond the first viewport.",
        "overflow": "Use vertical document scrolling as part of the composition rather than an internal card scroller.",
    },
    "workspace_fill": {
        "root_geometry": "Fill the available viewport with a working surface, board, grid, or multi-region application; controls attach to that surface rather than a centered wrapper.",
        "overflow": "Prefer region-level overflow inside a viewport-filling workspace when the content requires it.",
    },
    "centered_object": {
        "root_geometry": "Center the primary object or instrument itself, not an enclosing app card; supporting regions must occupy or anchor to the surrounding viewport.",
        "overflow": "Keep the object and its primary control visible together, with supporting content flowing around or below it.",
    },
}

_VIEWPORT_TRAITS = (
    ("full_bleed", frozenset({"full_field", "edge_to_edge", "spatial_canvas", "canvas_stage", "map_stage", "sticky_stage", "side_scroll"})),
    ("edge_anchored", frozenset({"side_region", "editorial_split", "preview_split", "comparison_split", "diptych", "editorial_rail", "master_detail"})),
    ("scrolling_document", frozenset({"vertical_flow", "scrollytelling", "accordion", "editorial_grid", "progressive_disclosure", "continuous_band"})),
    ("workspace_fill", frozenset({"workspace", "workbench", "explicit_grid", "multi_column", "multi_view", "process_flow", "timeline_workspace", "node_graph", "quadrant_grid"})),
)


def _viewport_contract(traits: Iterable[str]) -> Dict[str, str]:
    trait_set = set(traits)
    behavior = next(
        (name for name, matching_traits in _VIEWPORT_TRAITS if trait_set & matching_traits),
        "centered_object",
    )
    return {"behavior": behavior, **_VIEWPORT_CONTRACTS[behavior]}


def _nonempty_strings(value: Any, *, field: str, topology_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise RuntimeError(f"Layout topology {topology_id!r} field {field!r} must be a non-empty string list")
    return tuple(item.strip() for item in value)


def _normalize_silhouette(name: str, raw: Mapping[str, Any]) -> Dict[str, Any]:
    missing = _SILHOUETTE_FIELDS - raw.keys()
    if missing:
        raise RuntimeError(f"Layout silhouette {name!r} is missing {sorted(missing)}")
    string_fields = _SILHOUETTE_FIELDS - {"edge_anchors", "forbidden_shells"}
    for field in string_fields:
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise RuntimeError(f"Layout silhouette {name!r} field {field!r} must be a non-empty string")
    return {
        "behavior": raw["viewport_behavior"].strip(),
        "root_display": raw["root_display"].strip(),
        "root_columns": raw["root_columns"].strip(),
        "root_rows": raw["root_rows"].strip(),
        "edge_anchors": list(_nonempty_strings(raw["edge_anchors"], field="edge_anchors", topology_id=name)),
        "scroll_axis": raw["scroll_axis"].strip(),
        "dominant_region": raw["dominant_region"].strip(),
        "control_region": raw["control_region"].strip(),
        "result_region": raw["result_region"].strip(),
        "forbidden_shells": list(
            _nonempty_strings(raw["forbidden_shells"], field="forbidden_shells", topology_id=name)
        ),
    }


def _legacy_silhouette(traits: Iterable[str]) -> tuple[str, Dict[str, Any]]:
    viewport = _viewport_contract(traits)
    behavior = viewport["behavior"]
    return f"legacy_{behavior}", {
        **viewport,
        "root_display": "grid",
        "root_columns": "minmax(0, 1fr)",
        "root_rows": "minmax(0, 1fr)",
        "edge_anchors": ["top", "right", "bottom", "left"],
        "scroll_axis": "block" if behavior == "scrolling_document" else "none",
        "dominant_region": "primary_content",
        "control_region": "attached_to_primary_content",
        "result_region": "in_place_result",
        "forbidden_shells": ["centered_card"],
    }


def _load_silhouettes(
    payload: Mapping[str, Any],
    topologies: Mapping[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    raw_silhouettes = payload.get("silhouettes")
    raw_assignments = payload.get("silhouette_assignments")
    if raw_silhouettes is None and raw_assignments is None:
        silhouettes: Dict[str, Dict[str, Any]] = {}
        for topology in topologies.values():
            name, contract = _legacy_silhouette(topology["traits"])
            silhouettes.setdefault(name, contract)
            topology["silhouette_family"] = name
            topology["viewport_contract"] = contract
        return silhouettes
    if not isinstance(raw_silhouettes, dict) or not raw_silhouettes:
        raise RuntimeError("Layout topology catalog must define a silhouettes mapping")
    if not isinstance(raw_assignments, dict) or not raw_assignments:
        raise RuntimeError("Layout topology catalog must define silhouette_assignments")

    silhouettes = {}
    for name, raw in raw_silhouettes.items():
        if not isinstance(name, str) or not _TOPOLOGY_ID_RE.fullmatch(name) or not isinstance(raw, dict):
            raise RuntimeError(f"Invalid layout silhouette {name!r}")
        silhouettes[name] = _normalize_silhouette(name, raw)

    assigned: Dict[str, str] = {}
    for silhouette_name, topology_ids in raw_assignments.items():
        if silhouette_name not in silhouettes:
            raise RuntimeError(f"Unknown layout silhouette assignment {silhouette_name!r}")
        for topology_id in _nonempty_strings(
            topology_ids,
            field="silhouette_assignments",
            topology_id=str(silhouette_name),
        ):
            if topology_id not in topologies:
                raise RuntimeError(f"Layout silhouette {silhouette_name!r} references unknown topology {topology_id!r}")
            if topology_id in assigned:
                raise RuntimeError(f"Layout topology {topology_id!r} has multiple silhouette assignments")
            assigned[topology_id] = silhouette_name

    unassigned = set(topologies) - assigned.keys()
    if unassigned:
        raise RuntimeError(f"Layout topologies missing silhouette assignments: {sorted(unassigned)}")
    for topology_id, silhouette_name in assigned.items():
        topologies[topology_id]["silhouette_family"] = silhouette_name
        topologies[topology_id]["viewport_contract"] = silhouettes[silhouette_name]
    return silhouettes


def _load_topology_catalog() -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, tuple[str, ...]],
    Dict[str, Dict[str, Any]],
]:
    try:
        payload = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid layout topology catalog {_CATALOG_PATH}: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RuntimeError(f"Layout topology catalog {_CATALOG_PATH} must use version 1")
    records = payload.get("topologies")
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"Layout topology catalog {_CATALOG_PATH} must define a topologies list")
    topologies: Dict[str, Dict[str, Any]] = {}
    by_category: dict[str, list[str]] = defaultdict(list)
    for index, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            raise RuntimeError(f"Layout topology record {index} must be a mapping")
        missing = _REQUIRED_FIELDS - raw.keys()
        if missing:
            raise RuntimeError(f"Layout topology record {index} is missing {sorted(missing)}")

        topology_id = raw["id"]
        if not isinstance(topology_id, str) or not _TOPOLOGY_ID_RE.fullmatch(topology_id):
            raise RuntimeError(f"Layout topology record {index} has invalid id {topology_id!r}")
        if topology_id in topologies:
            raise RuntimeError(f"Layout topology catalog contains duplicate id {topology_id!r}")

        categories = _nonempty_strings(raw["categories"], field="categories", topology_id=topology_id)
        unknown_categories = set(categories) - _CATEGORY_SET
        if unknown_categories:
            raise RuntimeError(f"Layout topology {topology_id!r} has unknown categories {sorted(unknown_categories)}")
        regions = _nonempty_strings(raw["regions"], field="regions", topology_id=topology_id)
        traits = _nonempty_strings(raw["traits"], field="traits", topology_id=topology_id)
        if len(regions) < 4:
            raise RuntimeError(f"Layout topology {topology_id!r} must define at least four regions")
        if len(set(regions)) != len(regions):
            raise RuntimeError(f"Layout topology {topology_id!r} contains duplicate regions")

        string_fields = (
            "reference_family",
            "desktop_flow",
            "mobile_transformation",
            "control_placement",
            "result_transition",
        )
        for field in string_fields:
            if not isinstance(raw[field], str) or not raw[field].strip():
                raise RuntimeError(f"Layout topology {topology_id!r} field {field!r} must be a non-empty string")

        topologies[topology_id] = {
            "reference_family": raw["reference_family"].strip(),
            "categories": categories,
            "regions": regions,
            "desktop_flow": raw["desktop_flow"].strip(),
            "mobile_transformation": raw["mobile_transformation"].strip(),
            "control_placement": raw["control_placement"].strip(),
            "result_transition": raw["result_transition"].strip(),
            "traits": traits,
        }
        for category in categories:
            by_category[category].append(topology_id)

    missing_categories = [category for category in _CATEGORIES if not by_category[category]]
    if missing_categories:
        raise RuntimeError(f"Layout topology catalog has no entries for {missing_categories}")
    silhouettes = _load_silhouettes(payload, topologies)
    return topologies, {category: tuple(by_category[category]) for category in _CATEGORIES}, silhouettes


_TOPOLOGIES, _CATEGORY_TOPOLOGIES, _SILHOUETTES = _load_topology_catalog()


_COPY_BUDGETS = {
    "game": (50, "Use labels, score, and one micro-cue; rules should be learned through play."),
    "product": (105, "Keep only product identity, essential value, options, price, and purchase confirmation."),
    "commerce": (90, "Use concise item, route, booking, total, and confirmation copy."),
    "creative_tool": (70, "Let tools and the artifact explain the workflow; avoid tutorial paragraphs."),
    "simulation": (55, "Use one micro-cue and visible state labels; cause and effect should explain the experience."),
    "investigation": (100, "Keep evidence readable but remove atmospheric filler and repeated instructions."),
    "app": (90, "Use realistic records and action labels instead of explanatory product copy."),
}


def layout_model_for_target(
    *,
    seed: int,
    category: str,
    task_model: Mapping[str, Any],
    reserved_signatures: Iterable[str] = (),
    reserved_silhouette_families: Iterable[str] = (),
    recent_rendered_families: Iterable[str] = (),
) -> Dict[str, Any]:
    """Select a content-native topology instead of a universal page shell."""
    category = category if category in _CATEGORY_TOPOLOGIES else "app"
    rng = random.Random(f"{seed}:{task_model.get('format')}:{category}:layout")
    names = list(_CATEGORY_TOPOLOGIES[category])
    reserved = set(reserved_signatures)
    reserved_names = {signature.split(":", 1)[-1] for signature in reserved}
    available = [name for name in names if name not in reserved_names] or names
    reserved_silhouettes = set(reserved_silhouette_families)
    if len(reserved_silhouettes) < len(_SILHOUETTES):
        unused_silhouettes = [
            name
            for name in available
            if _TOPOLOGIES[name]["silhouette_family"] not in reserved_silhouettes
        ]
        available = unused_silhouettes or available
    recent_traits = {
        trait
        for family in recent_rendered_families
        for trait in str(family).split(":")
    }
    fresh = [name for name in available if not (set(_TOPOLOGIES[name]["traits"]) & recent_traits)]
    name = rng.choice(fresh or available)
    topology = _TOPOLOGIES[name]
    signature = f"{category}:{name}"
    return {
        "signature": signature,
        "category": category,
        "composition_mode": "structured" if category in _STRUCTURED_LAYOUT_CATEGORIES else "authored",
        "topology": name,
        "reference_family": topology["reference_family"],
        "silhouette_family": topology["silhouette_family"],
        "viewport_contract": dict(topology["viewport_contract"]),
        "regions": list(topology["regions"]),
        "source_order": list(topology["regions"]),
        "desktop_flow": topology["desktop_flow"],
        "control_placement": topology["control_placement"],
        "result_transition": topology["result_transition"],
        "mobile_transformation": topology["mobile_transformation"],
        "traits": list(topology["traits"]),
    }


def copy_budget_for_category(category: str) -> Dict[str, Any]:
    maximum, guidance = _COPY_BUDGETS.get(category, _COPY_BUDGETS["app"])
    return {
        "max_visible_words": maximum,
        "max_heading_words": 6,
        "max_instruction_words": 12,
        "guidance": guidance,
    }
