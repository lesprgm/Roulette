from __future__ import annotations

import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import yaml


_CATALOG_DIR = Path(__file__).resolve().parent / "variants"
_WEIGHTS_PATH = Path(__file__).resolve().parent / "variant_weights.yaml"
_LOCAL_CAPABILITIES_PATH = Path(__file__).resolve().parent / "library_capabilities.yaml"
_SECRET_CAPABILITIES_PATH = Path("/etc/secrets/library_capabilities.yaml")
_CONFIGURED_CAPABILITIES_PATH = os.getenv("LIBRARY_CAPABILITIES_PATH", "").strip()
_CAPABILITIES_PATH = (
    Path(_CONFIGURED_CAPABILITIES_PATH).expanduser()
    if _CONFIGURED_CAPABILITIES_PATH
    else _SECRET_CAPABILITIES_PATH if _SECRET_CAPABILITIES_PATH.exists() else _LOCAL_CAPABILITIES_PATH
)
_DEFAULT_SECRET_CATALOG_PATHS = (
    Path("/etc/secrets/format_catalog.yaml"),
    Path("/etc/secrets/variant_catalog.yaml"),
)
_CONFIGURED_CATALOG_PATH = (
    os.getenv("FORMAT_CATALOG_PATH", "").strip()
    or os.getenv("VARIANT_CATALOG_PATH", "").strip()
)
_CATEGORY_WEIGHTS_ENV = "FORMAT_CATEGORY_WEIGHTS"
_LEGACY_CATEGORY_WEIGHTS_ENV = "VARIANT_CATEGORY_WEIGHTS"
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RETIRED_CATEGORIES = {"apps_heavy_workflow"}
_LEGACY_CATEGORY_ALIASES = {"extras": "extras_active"}
_LEGACY_FIELD_ALIASES = {
    "activity_type": "format_category",
    "experience_archetype": "interaction_pattern",
    "primary_loop_type": "interaction_loop",
}

REWARD_MECHANICS = [
    "score_chase",
    "completion_meter",
    "collection_discovery",
    "surprise_transformation",
    "generated_artifact",
    "route_or_progress_payoff",
    "comparison_reveal",
    "unlock_sequence",
    "tactile_satisfaction",
    "high_score_retry",
    "before_after_reveal",
    "checkout_or_receipt_payoff",
]
LIBRARY_CAPABILITIES = {
    "app_iconography",
    "direct_manipulation",
    "physics_2d",
    "reactive_state",
    "sequenced_motion",
    "spatial_3d",
}


def _default_reward_mechanic(item: Mapping[str, Any]) -> str:
    category = str(item.get("category") or "")
    format_category = str(item.get("format_category") or "")
    text = " ".join(str(item.get(key) or "") for key in ("id", "format_name", "core_mechanic", "completion_condition")).lower()
    if category == "products":
        if any(term in text for term in ("delivery", "booking", "ticket", "travel")):
            return "route_or_progress_payoff"
        if any(term in text for term in ("pricing", "comparison", "marketplace")):
            return "comparison_reveal"
        return "checkout_or_receipt_payoff"
    if category == "games" or format_category in {"platformer", "snake_game", "microgame"}:
        if any(term in text for term in ("quiz", "trivia", "answer")):
            return "score_chase"
        if any(term in text for term in ("memory", "word", "puzzle", "sudoku", "solitaire")):
            return "completion_meter"
        return "high_score_retry"
    if any(term in text for term in ("route", "map", "delivery", "booking", "travel")):
        return "route_or_progress_payoff"
    if any(term in text for term in ("compare", "comparison", "budget", "expense", "scale")):
        return "comparison_reveal"
    if any(term in text for term in ("draw", "poster", "palette", "sequencer", "builder", "studio", "generator")):
        return "generated_artifact"
    if any(term in text for term in ("sand", "weather", "growth", "simulator", "mixer")):
        return "surprise_transformation"
    if category == "extras_ambient":
        return "tactile_satisfaction"
    if category == "extras_active":
        return "collection_discovery"
    return "completion_meter"


def _load_combined_catalog() -> tuple[Dict[str, Any] | None, Path | None]:
    path = Path(_CONFIGURED_CATALOG_PATH).expanduser() if _CONFIGURED_CATALOG_PATH else None
    if path is None:
        path = next((candidate for candidate in _DEFAULT_SECRET_CATALOG_PATHS if candidate.exists()), None)
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
    formats = payload.get("formats", payload.get("variants"))
    if not isinstance(formats, list):
        raise RuntimeError(f"Private generation catalog {path} must define a formats list")
    payload["formats"] = formats
    return payload, path


_COMBINED_CATALOG, _COMBINED_CATALOG_PATH = _load_combined_catalog()


def _load_env_category_weights() -> Dict[str, float] | None:
    raw = (
        os.getenv(_CATEGORY_WEIGHTS_ENV, "").strip()
        or os.getenv(_LEGACY_CATEGORY_WEIGHTS_ENV, "").strip()
    )
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
    normalized: Dict[str, float] = {}
    for key, value in payload.items():
        key = _LEGACY_CATEGORY_ALIASES.get(str(key), str(key))
        normalized[key] = normalized.get(key, 0.0) + float(value)
    payload = {
        key: value
        for key, value in normalized.items()
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
    "format_category",
    "core_mechanic",
    "interaction_pattern",
    "interaction_loop",
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
        sources = [(
            _COMBINED_CATALOG_PATH,
            _COMBINED_CATALOG.get("formats", _COMBINED_CATALOG.get("variants")),
        )]
    else:
        files = sorted(_CATALOG_DIR.glob("*.yaml"))
        if not files:
            raise RuntimeError(
                "No generation catalog found. Set FORMAT_CATALOG_PATH or provide "
                f"local YAML files in {_CATALOG_DIR}"
            )
        sources = []
        for path in files:
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise RuntimeError(f"Invalid generation catalog file {path}: {exc}") from exc
            sources.append((path, payload))

    formats: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path, payload in sources:
        if not isinstance(payload, list):
            raise RuntimeError(f"Generation catalog file {path} must contain a YAML list")

        for index, raw in enumerate(payload):
            location = f"{path}:{index + 1}"
            if not isinstance(raw, dict):
                raise RuntimeError(f"{location} must be a mapping")
            item = dict(raw)
            for legacy, canonical in _LEGACY_FIELD_ALIASES.items():
                if canonical not in item and legacy in item:
                    item[canonical] = item[legacy]
                item.pop(legacy, None)
            missing = sorted(_REQUIRED_FIELDS - set(item))
            if missing:
                raise RuntimeError(f"{location} is missing required fields: {', '.join(missing)}")

            format_id = item["id"]
            if not isinstance(format_id, str) or not _ID_RE.fullmatch(format_id):
                raise RuntimeError(f"{location} has invalid id {format_id!r}")
            if format_id in seen:
                raise RuntimeError(f"Duplicate generation format id: {format_id}")
            seen.add(format_id)

            category = _LEGACY_CATEGORY_ALIASES.get(str(item["category"]), str(item["category"]))
            item["category"] = category
            if category in _RETIRED_CATEGORIES:
                continue
            if category not in CATEGORY_WEIGHTS:
                raise RuntimeError(f"{location} has unknown category {category!r}")
            if not _string_or_strings(item["interaction_pattern"]):
                raise RuntimeError(f"{location} has invalid interaction_pattern")
            if not _string_or_strings(item["interaction_loop"]):
                raise RuntimeError(f"{location} has invalid interaction_loop")
            if not _nonempty_strings(item["domain_objects"]):
                raise RuntimeError(f"{location} must define domain_objects")
            if not _nonempty_strings(item["state_variables"]):
                raise RuntimeError(f"{location} must define state_variables")
            for key in ("format_category", "core_mechanic", "format_name", "user_goal", "completion_condition", "primary_action", "family"):
                if not isinstance(item[key], str) or not item[key].strip():
                    raise RuntimeError(f"{location} has invalid {key}")
            if not item.get("reward_mechanic"):
                item["reward_mechanic"] = _default_reward_mechanic(item)
            if item["reward_mechanic"] not in REWARD_MECHANICS:
                raise RuntimeError(f"{location} has unknown reward_mechanic {item['reward_mechanic']!r}")
            if "ritual" in " ".join(
                str(item.get(key, "")).lower()
                for key in ("format_category", "interaction_pattern", "pattern_group", "family")
            ):
                raise RuntimeError(f"{location} uses retired ritual vocabulary")

            allowed_patterns = item.get("allowed_patterns")
            pattern_group = item.get("pattern_group")
            if allowed_patterns is not None and not _nonempty_strings(allowed_patterns):
                raise RuntimeError(f"{location} has invalid allowed_patterns")
            if allowed_patterns is None and pattern_group not in FORMAT_PATTERN_GROUPS:
                raise RuntimeError(f"{location} has unknown pattern_group {pattern_group!r}")
            if "is_tool" in item and not isinstance(item["is_tool"], bool):
                raise RuntimeError(f"{location} has non-boolean is_tool")

            formats.append(item)

    return formats


_FORMATS = _load_catalog()
missing_categories = sorted(
    category
    for category in CATEGORY_WEIGHTS
    if not any(item["category"] == category for item in _FORMATS)
)

FORMAT_BY_ID: Dict[str, Dict[str, Any]] = {item["id"]: item for item in _FORMATS}
FORMATS_BY_CATEGORY: Dict[str, List[str]] = {
    category: [item["id"] for item in _FORMATS if item["category"] == category]
    for category in CATEGORY_WEIGHTS
}

GAME_FORMATS = FORMATS_BY_CATEGORY["games"]
PRODUCT_FORMATS = FORMATS_BY_CATEGORY["products"]
ALL_FORMATS = [item["id"] for item in _FORMATS]


def _load_library_capabilities() -> Dict[str, List[str]]:
    try:
        payload = yaml.safe_load(_CAPABILITIES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid library capability catalog {_CAPABILITIES_PATH}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RuntimeError("Library capability catalog must use version 1")

    defaults = payload.get("default_capabilities")
    category_capabilities = payload.get("category_capabilities")
    capability_formats = payload.get("capability_formats")
    if not _nonempty_strings(defaults):
        raise RuntimeError("Library capability catalog must define default_capabilities")
    if not isinstance(category_capabilities, dict) or not isinstance(capability_formats, dict):
        raise RuntimeError("Library capability catalog must define category_capabilities and capability_formats")

    unknown_capabilities = set(defaults) - LIBRARY_CAPABILITIES
    known_categories = {str(item["format_category"]) for item in _FORMATS}
    unknown_categories = set(category_capabilities) - known_categories
    if unknown_categories:
        raise RuntimeError(f"Library capability catalog has unknown categories: {sorted(unknown_categories)}")
    for values in category_capabilities.values():
        if not _nonempty_strings(values):
            raise RuntimeError("Library capability category entries must contain capability names")
        unknown_capabilities.update(set(values) - LIBRARY_CAPABILITIES)
    unknown_capabilities.update(set(capability_formats) - LIBRARY_CAPABILITIES)
    if unknown_capabilities:
        raise RuntimeError(f"Library capability catalog has unknown capabilities: {sorted(unknown_capabilities)}")

    capabilities = {
        str(item["id"]): set(defaults) | set(category_capabilities.get(str(item["format_category"]), []))
        for item in _FORMATS
    }
    known_formats = set(capabilities)
    for capability, format_ids in capability_formats.items():
        if not _nonempty_strings(format_ids):
            raise RuntimeError(f"Library capability {capability!r} must contain format ids")
        unknown_formats = set(format_ids) - known_formats
        if unknown_formats:
            raise RuntimeError(f"Library capability {capability!r} has unknown formats: {sorted(unknown_formats)}")
        for format_id in format_ids:
            capabilities[format_id].add(capability)
    return {format_id: sorted(values) for format_id, values in capabilities.items()}


FORMAT_CAPABILITIES = _load_library_capabilities()

FORMAT_SPECS: Dict[str, Dict[str, Any]] = {
    item["id"]: {
        "format_category": item["format_category"],
        "core_mechanic": item["core_mechanic"],
        "interaction_pattern": item["interaction_pattern"],
        "interaction_loop": item["interaction_loop"],
        "family": item["family"],
        "reward_mechanic": item["reward_mechanic"],
    }
    for item in _FORMATS
}
FORMAT_TASK_OVERRIDES: Dict[str, Dict[str, Any]] = {
    item["id"]: {
        "format": item["format_name"],
        "user_goal": item["user_goal"],
        "domain_objects": list(item["domain_objects"]),
        "state_variables": list(item["state_variables"]),
        "completion_condition": item["completion_condition"],
        "primary_action": item["primary_action"],
        "allowed_patterns": list(
            item.get("allowed_patterns")
            or FORMAT_PATTERN_GROUPS[item["pattern_group"]]
        ),
    }
    for item in _FORMATS
}
FORMAT_FAMILY_MAP = {item["id"]: item["family"] for item in _FORMATS}
REWARD_MECHANIC_MAP = {item["id"]: item["reward_mechanic"] for item in _FORMATS}
CORE_MECHANICS = list(dict.fromkeys(item["core_mechanic"] for item in _FORMATS))

def choose_weighted_format(
    rng: random.Random,
    *,
    excluded: Iterable[str] = (),
) -> str:
    excluded_set = set(excluded)
    categories = [
        category
        for category, formats in FORMATS_BY_CATEGORY.items()
        if any(format_id not in excluded_set for format_id in formats)
    ]
    if not categories:
        raise RuntimeError("No generation formats remain after exclusions")
    category = rng.choices(
        categories,
        weights=[CATEGORY_WEIGHTS[item] for item in categories],
        k=1,
    )[0]
    choices = [format_id for format_id in FORMATS_BY_CATEGORY[category] if format_id not in excluded_set]
    return rng.choice(choices)


def validate_catalog_domains(
    *,
    format_categories: Sequence[str],
    interaction_patterns: Sequence[str],
    interaction_loops: Sequence[str],
) -> None:
    allowed_format_categories = set(format_categories)
    allowed_patterns = set(interaction_patterns)
    allowed_loops = set(interaction_loops)
    for item in _FORMATS:
        format_id = item["id"]
        if item["format_category"] not in allowed_format_categories:
            raise RuntimeError(f"{format_id} has unsupported format_category {item['format_category']!r}")
        patterns = item["interaction_pattern"]
        if isinstance(patterns, str):
            patterns = [patterns]
        invalid_patterns = sorted(set(patterns) - allowed_patterns)
        if invalid_patterns:
            raise RuntimeError(f"{format_id} has unsupported interaction_pattern values: {invalid_patterns}")
        loops = item["interaction_loop"]
        if isinstance(loops, str):
            loops = [loops]
        invalid_loops = sorted(set(loops) - allowed_loops)
        if invalid_loops:
            raise RuntimeError(f"{format_id} has unsupported interaction_loop values: {invalid_loops}")
