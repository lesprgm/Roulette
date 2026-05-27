from __future__ import annotations

import random
from typing import Dict, List, Tuple


EXPERIENCE_ARCHETYPES = [
    "interactive_instrument",
    "fictional_control_room",
    "generative_poster",
    "spatial_exploration",
    "narrative_microsite",
    "interactive_editorial",
    "data_sculpture",
    "simulation_toy",
    "ambient_dashboard",
    "museum_exhibit",
    "visual_playground",
    "product_demo_experience",
    "creative_tool_interface",
]

PRIMARY_LOOP_TYPES = [
    "type_to_reveal",
    "drag_to_transform",
    "tune_to_harmonize",
    "collect_to_complete",
    "scan_to_discover",
    "sort_to_understand",
    "paint_to_grow",
    "assemble_to_activate",
    "scrub_time_to_compare",
    "steer_to_explore",
    "press_sequence_to_unlock",
    "hover_to_inspect",
    "choose_to_branch",
    "mix_to_generate",
    "zoom_to_uncover",
]

FEEDBACK_PATTERNS = [
    "immediate_visual_response",
    "meter_progression",
    "layer_reveal",
    "stateful_transformation",
    "object_accumulation",
    "environmental_reaction",
    "textual_confirmation",
    "spatial_movement",
]

PROGRESSION_PATTERNS = [
    "completion_meter",
    "unlock_sequence",
    "collection_set",
    "before_after_comparison",
    "increasing_complexity",
    "hidden_message_reveal",
    "map_expansion",
    "timeline_scrub",
]

REPLAYABILITY_PATTERNS = [
    "reset_to_initial_state",
    "generate_new_variant",
    "alternate_path",
    "parameter_retune",
    "randomized_seed_replay",
]

AFFORDANCE_PATTERNS = [
    "visible_button",
    "labeled_slider",
    "draggable_object",
    "typing_input",
    "hover_target",
    "scroll_cue",
    "tap_zone",
    "canvas_pointer_area",
]

EXPERIENCE_FAILURE_MODES = [
    "decorative_only_interaction",
    "unclear_first_action",
    "dead_controls",
    "word_salad_labels",
    "no_state_change",
    "no_continue_reason",
    "visual_noise_over_primary_action",
    "desktop_only_interaction",
    "anchors_used_only_as_surface_style",
]

DEFAULT_EXPERIENCE_CELLS: List[Tuple[str, str]] = [
    ("interactive_instrument", "type_to_reveal"),
    ("simulation_toy", "drag_to_transform"),
    ("museum_exhibit", "scan_to_discover"),
    ("spatial_exploration", "steer_to_explore"),
    ("narrative_microsite", "choose_to_branch"),
    ("creative_tool_interface", "paint_to_grow"),
    ("data_sculpture", "scrub_time_to_compare"),
    ("fictional_control_room", "tune_to_harmonize"),
    ("generative_poster", "mix_to_generate"),
    ("interactive_editorial", "hover_to_inspect"),
    ("visual_playground", "press_sequence_to_unlock"),
    ("product_demo_experience", "assemble_to_activate"),
    ("ambient_dashboard", "collect_to_complete"),
    ("museum_exhibit", "zoom_to_uncover"),
    ("creative_tool_interface", "sort_to_understand"),
]


def cell_key(archetype: str, loop_type: str) -> str:
    return f"{archetype}:{loop_type}"


def parse_cell_key(value: str) -> Dict[str, str]:
    left, _, right = str(value or "").partition(":")
    archetype = left if left in EXPERIENCE_ARCHETYPES else EXPERIENCE_ARCHETYPES[0]
    loop_type = right if right in PRIMARY_LOOP_TYPES else PRIMARY_LOOP_TYPES[0]
    return {
        "experience_archetype": archetype,
        "primary_loop_type": loop_type,
    }


def all_experience_cell_keys() -> List[str]:
    return [cell_key(archetype, loop_type) for archetype, loop_type in DEFAULT_EXPERIENCE_CELLS]


def seeded_experience_cell(seed: int | None = None) -> Dict[str, str]:
    rng = random.Random(int(seed or 0))
    archetype, loop_type = DEFAULT_EXPERIENCE_CELLS[rng.randrange(len(DEFAULT_EXPERIENCE_CELLS))]
    return {
        "experience_archetype": archetype,
        "primary_loop_type": loop_type,
    }
