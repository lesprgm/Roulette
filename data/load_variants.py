from __future__ import annotations

import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import yaml


_VARIANTS_DIR = Path(__file__).resolve().parent / "variants"
_WEIGHTS_PATH = Path(__file__).resolve().parent / "variant_weights.yaml"
_DEFAULT_SECRET_CATALOG_PATH = Path("/etc/secrets/variant_catalog.yaml")
_CONFIGURED_CATALOG_PATH = os.getenv("VARIANT_CATALOG_PATH", "").strip()
_CATEGORY_WEIGHTS_ENV = "VARIANT_CATEGORY_WEIGHTS"
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RETIRED_CATEGORIES = {"apps_heavy_workflow"}


def _load_combined_catalog() -> tuple[Dict[str, Any] | None, Path | None]:
    path = Path(_CONFIGURED_CATALOG_PATH).expanduser() if _CONFIGURED_CATALOG_PATH else None
    if path is None and _DEFAULT_SECRET_CATALOG_PATH.exists():
        path = _DEFAULT_SECRET_CATALOG_PATH
    if path is None:
        return None, None

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid private generation catalog {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Private generation catalog {path} must contain a mapping")
    if not isinstance(payload.get("category_weights"), dict):
        raise RuntimeError(f"Private generation catalog {path} must define category_weights")
    if not isinstance(payload.get("variants"), list):
        raise RuntimeError(f"Private generation catalog {path} must define a variants list")
    return payload, path


_COMBINED_CATALOG, _COMBINED_CATALOG_PATH = _load_combined_catalog()


def _load_env_category_weights() -> Dict[str, float] | None:
    raw = os.getenv(_CATEGORY_WEIGHTS_ENV, "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        payload = yaml.safe_load(raw)
    else:
        payload = {}
        for chunk in raw.split(","):
            key, sep, value = chunk.strip().partition("=")
            if not sep:
                raise RuntimeError(f"{_CATEGORY_WEIGHTS_ENV} entries must use category=weight")
            payload[key.strip()] = float(value.strip())
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(f"{_CATEGORY_WEIGHTS_ENV} must contain a category weight mapping")
    return payload


def _load_category_weights() -> Dict[str, float]:
    env_payload = _load_env_category_weights()
    if env_payload is not None:
        payload = env_payload
        source = _CATEGORY_WEIGHTS_ENV
    elif _COMBINED_CATALOG is not None:
        payload = _COMBINED_CATALOG["category_weights"]
        source = _COMBINED_CATALOG_PATH
    else:
        source = _WEIGHTS_PATH
        try:
            payload = yaml.safe_load(_WEIGHTS_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Invalid generation weight file {_WEIGHTS_PATH}: {exc}") from exc
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(f"Generation weight source {source} must contain a mapping")
    payload = {
        key: value
        for key, value in payload.items()
        if key not in _RETIRED_CATEGORIES
    }
    if not payload:
        raise RuntimeError(f"Generation weight source {source} contains only retired categories")
    if not all(isinstance(key, str) and isinstance(value, (int, float)) and value > 0 for key, value in payload.items()):
        raise RuntimeError(f"Generation weight source {source} must contain positive numeric weights")
    total = float(sum(payload.values()))
    return {key: float(value) / total for key, value in payload.items()}


CATEGORY_WEIGHTS = _load_category_weights()

FORMAT_PATTERN_GROUPS: Dict[str, List[str]] = {
    "game": [
        "game_stage",
        "scoreboard",
        "restart_button",
        "keyboard_touch_controls",
        "instant_start_or_one_play_button",
        "combo_or_streak",
        "meta_reward",
    ],
    "quiz": [
        "question_card",
        "answer_options",
        "scoreboard",
        "result_panel",
        "restart_button",
        "instant_start_or_one_play_button",
    ],
    "app": [
        "preloaded_sample_records",
        "record_list",
        "filter_bar",
        "detail_panel",
        "one_click_demo_action",
        "save_action",
        "status_feedback",
    ],
    "commerce": [
        "preselected_starter_option",
        "catalog_cards",
        "configuration_form",
        "cart_summary",
        "checkout_state",
        "status_feedback",
    ],
    "product": [
        "product_hero",
        "price_or_plan",
        "variant_selector",
        "benefit_list",
        "cart_or_checkout_summary",
        "primary_buy_action",
    ],
    "creative_tool": [
        "instant_preview",
        "tool_palette",
        "canvas_or_preview",
        "property_controls",
        "randomize_or_sample_action",
        "export_or_save_action",
    ],
    "simulation": [
        "preloaded_example_state",
        "system_stage",
        "parameter_controls",
        "result_readout",
        "reset_button",
    ],
    "investigation": [
        "evidence_list",
        "filter_or_sort_controls",
        "comparison_panel",
        "saved_findings",
    ],
}

_REQUIRED_FIELDS = {
    "id",
    "category",
    "activity_type",
    "core_mechanic",
    "experience_archetype",
    "primary_loop_type",
    "format_name",
    "user_goal",
    "domain_objects",
    "state_variables",
    "completion_condition",
    "primary_action",
    "family",
}


def _nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _string_or_strings(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) or _nonempty_strings(value)


def _load_catalog() -> List[Dict[str, Any]]:
    if _COMBINED_CATALOG is not None:
        sources = [(_COMBINED_CATALOG_PATH, _COMBINED_CATALOG["variants"])]
    else:
        files = sorted(_VARIANTS_DIR.glob("*.yaml"))
        if not files:
            raise RuntimeError(
                "No generation catalog found. Set VARIANT_CATALOG_PATH or provide "
                f"local YAML files in {_VARIANTS_DIR}"
            )
        sources = []
        for path in files:
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise RuntimeError(f"Invalid generation catalog file {path}: {exc}") from exc
            sources.append((path, payload))

    variants: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path, payload in sources:
        if not isinstance(payload, list):
            raise RuntimeError(f"Generation catalog file {path} must contain a YAML list")

        for index, raw in enumerate(payload):
            location = f"{path}:{index + 1}"
            if not isinstance(raw, dict):
                raise RuntimeError(f"{location} must be a mapping")
            missing = sorted(_REQUIRED_FIELDS - set(raw))
            if missing:
                raise RuntimeError(f"{location} is missing required fields: {', '.join(missing)}")

            variant = dict(raw)
            variant_id = variant["id"]
            if not isinstance(variant_id, str) or not _ID_RE.fullmatch(variant_id):
                raise RuntimeError(f"{location} has invalid id {variant_id!r}")
            if variant_id in seen:
                raise RuntimeError(f"Duplicate generation variant id: {variant_id}")
            seen.add(variant_id)

            category = variant["category"]
            if category in _RETIRED_CATEGORIES:
                continue
            if category not in CATEGORY_WEIGHTS:
                raise RuntimeError(f"{location} has unknown category {category!r}")
            if not _string_or_strings(variant["experience_archetype"]):
                raise RuntimeError(f"{location} has invalid experience_archetype")
            if not _string_or_strings(variant["primary_loop_type"]):
                raise RuntimeError(f"{location} has invalid primary_loop_type")
            if not _nonempty_strings(variant["domain_objects"]):
                raise RuntimeError(f"{location} must define domain_objects")
            if not _nonempty_strings(variant["state_variables"]):
                raise RuntimeError(f"{location} must define state_variables")
            for key in ("activity_type", "core_mechanic", "format_name", "user_goal", "completion_condition", "primary_action", "family"):
                if not isinstance(variant[key], str) or not variant[key].strip():
                    raise RuntimeError(f"{location} has invalid {key}")
            if "ritual" in " ".join(
                str(variant.get(key, "")).lower()
                for key in ("activity_type", "experience_archetype", "pattern_group", "family")
            ):
                raise RuntimeError(f"{location} uses retired ritual vocabulary")

            allowed_patterns = variant.get("allowed_patterns")
            pattern_group = variant.get("pattern_group")
            if allowed_patterns is not None and not _nonempty_strings(allowed_patterns):
                raise RuntimeError(f"{location} has invalid allowed_patterns")
            if allowed_patterns is None and pattern_group not in FORMAT_PATTERN_GROUPS:
                raise RuntimeError(f"{location} has unknown pattern_group {pattern_group!r}")
            if "is_tool" in variant and not isinstance(variant["is_tool"], bool):
                raise RuntimeError(f"{location} has non-boolean is_tool")

            variants.append(variant)

    return variants


_VARIANTS = _load_catalog()
missing_categories = sorted(
    category
    for category in CATEGORY_WEIGHTS
    if not any(variant["category"] == category for variant in _VARIANTS)
)
if missing_categories:
    raise RuntimeError(f"Generation catalog has empty categories: {', '.join(missing_categories)}")

VARIANT_BY_ID: Dict[str, Dict[str, Any]] = {variant["id"]: variant for variant in _VARIANTS}
VARIANTS_BY_CATEGORY: Dict[str, List[str]] = {
    category: [variant["id"] for variant in _VARIANTS if variant["category"] == category]
    for category in CATEGORY_WEIGHTS
}

GAME_FORMATS = VARIANTS_BY_CATEGORY["games"]
PRODUCT_FORMATS = VARIANTS_BY_CATEGORY["products"]
RETENTION_TOY_FORMATS = VARIANTS_BY_CATEGORY["toys"]
LOW_FRICTION_APP_FORMATS = VARIANTS_BY_CATEGORY["apps_low_friction"]
EXTRAS = VARIANTS_BY_CATEGORY["extras"]
APP_FORMATS = LOW_FRICTION_APP_FORMATS
TOOL_FORMATS = [variant["id"] for variant in _VARIANTS if variant.get("is_tool") is True]
ALL_FORMATS = [variant["id"] for variant in _VARIANTS]

FORMAT_VARIANT_SPECS: Dict[str, Dict[str, Any]] = {
    variant["id"]: {
        "activity_type": variant["activity_type"],
        "core_mechanic": variant["core_mechanic"],
        "experience_archetype": variant["experience_archetype"],
        "primary_loop_type": variant["primary_loop_type"],
        "family": variant["family"],
    }
    for variant in _VARIANTS
}
VARIANT_TASK_OVERRIDES: Dict[str, Dict[str, Any]] = {
    variant["id"]: {
        "format": variant["format_name"],
        "user_goal": variant["user_goal"],
        "domain_objects": list(variant["domain_objects"]),
        "state_variables": list(variant["state_variables"]),
        "completion_condition": variant["completion_condition"],
        "allowed_patterns": list(
            variant.get("allowed_patterns")
            or FORMAT_PATTERN_GROUPS[variant["pattern_group"]]
        ),
    }
    for variant in _VARIANTS
}
PRIMARY_ACTION_MAP = {variant["id"]: variant["primary_action"] for variant in _VARIANTS}
CATEGORY_MAP = {variant["id"]: variant["category"] for variant in _VARIANTS}
PATTERN_GROUP_MAP = {
    variant["id"]: variant.get("pattern_group", "custom")
    for variant in _VARIANTS
}
ACTIVITY_FAMILY_MAP = {variant["id"]: variant["family"] for variant in _VARIANTS}
CORE_MECHANICS = list(dict.fromkeys(variant["core_mechanic"] for variant in _VARIANTS))

# Compatibility export for schema construction and deterministic fallback iteration.
# Selection uses choose_weighted_variant(), not duplicate entries in this list.
FORMAT_FIRST_VARIANT_POOL = list(ALL_FORMATS)


def choose_weighted_variant(
    rng: random.Random,
    *,
    excluded: Iterable[str] = (),
) -> str:
    excluded_set = set(excluded)
    categories = [
        category
        for category, variants in VARIANTS_BY_CATEGORY.items()
        if any(variant not in excluded_set for variant in variants)
    ]
    if not categories:
        raise RuntimeError("No generation variants remain after exclusions")
    category = rng.choices(
        categories,
        weights=[CATEGORY_WEIGHTS[item] for item in categories],
        k=1,
    )[0]
    choices = [variant for variant in VARIANTS_BY_CATEGORY[category] if variant not in excluded_set]
    return rng.choice(choices)


def validate_catalog_domains(
    *,
    activity_types: Sequence[str],
    experience_archetypes: Sequence[str],
    primary_loop_types: Sequence[str],
) -> None:
    allowed_activity_types = set(activity_types)
    allowed_archetypes = set(experience_archetypes)
    allowed_loops = set(primary_loop_types)
    for variant in _VARIANTS:
        variant_id = variant["id"]
        if variant["activity_type"] not in allowed_activity_types:
            raise RuntimeError(f"{variant_id} has unsupported activity_type {variant['activity_type']!r}")
        archetypes = variant["experience_archetype"]
        if isinstance(archetypes, str):
            archetypes = [archetypes]
        invalid_archetypes = sorted(set(archetypes) - allowed_archetypes)
        if invalid_archetypes:
            raise RuntimeError(f"{variant_id} has unsupported experience_archetype values: {invalid_archetypes}")
        loops = variant["primary_loop_type"]
        if isinstance(loops, str):
            loops = [loops]
        invalid_loops = sorted(set(loops) - allowed_loops)
        if invalid_loops:
            raise RuntimeError(f"{variant_id} has unsupported primary_loop_type values: {invalid_loops}")
