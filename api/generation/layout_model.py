from __future__ import annotations

import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import yaml


_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "layout_topologies.yaml"
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


def _nonempty_strings(value: Any, *, field: str, topology_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise RuntimeError(f"Layout topology {topology_id!r} field {field!r} must be a non-empty string list")
    return tuple(item.strip() for item in value)


def _load_topology_catalog() -> tuple[Dict[str, Dict[str, Any]], Dict[str, tuple[str, ...]]]:
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
    return topologies, {category: tuple(by_category[category]) for category in _CATEGORIES}


_TOPOLOGIES, _CATEGORY_TOPOLOGIES = _load_topology_catalog()


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
    recent_rendered_families: Iterable[str] = (),
) -> Dict[str, Any]:
    """Select a content-native topology instead of a universal page shell."""
    category = category if category in _CATEGORY_TOPOLOGIES else "app"
    rng = random.Random(f"{seed}:{task_model.get('format')}:{category}:layout")
    names = list(_CATEGORY_TOPOLOGIES[category])
    reserved = set(reserved_signatures)
    reserved_names = {signature.split(":", 1)[-1] for signature in reserved}
    available = [name for name in names if name not in reserved_names] or names
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
        "topology": name,
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
