from __future__ import annotations

import random
from typing import Dict, List, Tuple


EXPERIENCE_ARCHETYPES = [
    "browser_game",
    "quiz_game",
    "saas_workspace",
    "commerce_workspace",
    "interactive_instrument",
    "fictional_control_room",
    "generative_poster",
    "spatial_exploration",
    "narrative_microsite",
    "interactive_editorial",
    "data_sculpture",
    "simulation_toy",
    "museum_exhibit",
    "visual_playground",
    "product_demo_experience",
    "creative_tool_interface",
]

PRIMARY_LOOP_TYPES = [
    "answer_to_score",
    "type_to_reveal",
    "drag_to_transform",
    "tune_to_harmonize",
    "collect_to_complete",
    "scan_to_compare",
    "sort_to_understand",
    "paint_to_grow",
    "assemble_to_activate",
    "scrub_time_to_compare",
    "steer_to_explore",
    "press_sequence_to_unlock",
    "hover_to_inspect",
    "choose_to_branch",
    "mix_to_generate",
    "zoom_to_inspect",
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
    "score_challenge",
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

PAGE_GENRES = [
    "arcade_microgame",
    "app_workspace",
    "product_storefront",
    "fictional_control_room",
    "museum_exhibit",
    "puzzle_box",
    "toy_simulator",
    "data_workspace",
    "narrative_artifact",
    "interactive_editorial",
    "creative_tool",
]

COPY_DENSITIES = ["almost_none", "low", "medium", "high"]

GENRE_VISUAL_DENSITIES = ["sparse", "focused", "dense", "maximal"]

PALETTE_STRATEGIES = [
    "monochrome_accent",
    "muted_plus_toxic",
    "arcade_dark_shell",
    "editorial_neutral",
    "terminal_limited",
    "pastel_toy",
    "high_contrast_game",
    "earth_material_accent",
]

MOTION_LANGUAGES = [
    "snappy_gamefeel",
    "slow_cinematic",
    "dashboard_subtle",
    "playful_elastic",
    "glitchy_unstable",
    "calm_product",
]

INSTRUCTION_POLICIES = [
    "affordance_only",
    "one_microcue",
    "labels_allowed",
    "documentation_allowed",
]

CHROME_POLICIES = [
    "none",
    "minimal_functional",
    "diegetic_only",
    "dashboard_when_essential",
]

ACTIVITY_TYPES = [
    "platformer",
    "snake_game",
    "tic_tac_toe",
    "quiz_game",
    "memory_match",
    "word_game",
    "microgame",
    "saas_replica",
    "commerce_or_booking_flow",
    "product_or_storefront",
    "creative_tool",
    "puzzle_box",
    "simulation",
    "fake_os_app",
    "portfolio_or_brand_site",
    "narrative_explorer",
    "data_investigation",
    "interactive_instrument",
]

GAME_FORMATS = [
    "platformer_collectathon",
    "snake_grid",
    "tic_tac_toe",
    "trivia_quiz",
    "memory_match",
    "word_guess",
    "breakout_paddle",
    "minesweeper_grid",
    "tile_merge_2048",
    "endless_runner",
    "rhythm_tap",
    "whack_a_target",
    "sliding_tile_puzzle",
    "tower_defense_lite",
    "pinball_table",
    "asteroids_shooter",
    "maze_escape",
    "reaction_timer",
    "fishing_timing",
    "basketball_arcade",
    "card_sort_strategy",
    "typing_race",
]

APP_FORMATS = [
    "kanban_workspace",
    "crm_pipeline",
    "invoice_builder",
    "analytics_explorer",
    "calendar_scheduler",
    "inventory_manager",
    "travel_booking",
    "restaurant_ordering",
    "marketplace_comparison",
    "subscription_configurator",
    "portfolio_builder",
    "resume_screener",
    "support_triage",
    "habit_tracker",
    "budget_planner",
    "recipe_planner",
]

PRODUCT_FORMATS = [
    "product_detail_page",
    "sneaker_drop_page",
    "skincare_product_page",
    "coffee_subscription_page",
    "furniture_product_configurator",
    "course_sales_page",
    "app_pricing_page",
    "digital_template_store",
    "event_ticket_checkout",
    "marketplace_listing_page",
    "limited_drop_countdown",
]

TOOL_FORMATS = [
    "drawing_studio",
    "music_step_sequencer",
    "map_route_planner",
    "color_palette_mixer",
    "poster_generator",
    "room_layout_builder",
    "avatar_customizer",
    "plant_growth_simulator",
    "weather_mixer",
    "data_story_scrubber",
]

LIBRARY_PROFILES = [
    "ndw_canvas_game_loop",
    "ndw_audio_particles",
    "gsap_timeline_dom",
    "gsap_state_transition",
    "lucide_app_chrome",
    "alpine_ui_state",
    "matter_physics_game",
    "three_orbit_scene",
    "three_bloom_scene",
    "dom_css_state_machine",
]

ACTIVITY_VERBS = [
    "collect",
    "sort",
    "assemble",
    "draw",
    "paint",
    "filter",
    "search",
    "configure",
    "navigate",
    "unlock",
    "classify",
    "compose",
    "inspect",
    "repair",
    "trade",
]

MECHANIC_PATTERNS = [
    "platform_jump_and_collect",
    "snake_collect_and_grow",
    "tic_tac_toe_turn_strategy",
    "answer_questions_for_score",
    "flip_cards_to_match_pairs",
    "guess_word_with_limited_attempts",
    "breakout_paddle_bounce",
    "minesweeper_deduction",
    "tile_merge_2048",
    "endless_runner_dodge",
    "rhythm_tap_timing",
    "whack_targets_for_score",
    "sliding_tile_reorder",
    "tower_defense_place_units",
    "pinball_flipper_bounce",
    "asteroids_thrust_and_shoot",
    "maze_escape_navigation",
    "reaction_timer_challenge",
    "fishing_timing_cast",
    "basketball_shot_arc",
    "card_hand_strategy",
    "typing_race_accuracy",
    "drag_objects_into_zones",
    "collect_items_to_complete_set",
    "sort_cards_into_meaningful_groups",
    "paint_or_draw_to_create_output",
    "filter_search_and_select_records",
    "configure_product_or_system",
    "assemble_machine_or_layout",
    "navigate_map_or_space",
    "type_commands_or_messages",
    "choose_branching_path",
    "unlock_sequence_or_stages",
    "inspect_compare_and_act",
]

BORING_INTERACTION_PATTERNS = [
    "slider_only_controls",
    "buttons_only_toggle_visual_effects",
    "fake_metrics_without_task",
    "decorative_dashboard_chrome",
    "no_goal_or_payoff",
    "no_persistent_state",
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
    ("browser_game", "collect_to_complete"),
    ("browser_game", "steer_to_explore"),
    ("browser_game", "press_sequence_to_unlock"),
    ("browser_game", "drag_to_transform"),
    ("quiz_game", "answer_to_score"),
    ("quiz_game", "choose_to_branch"),
    ("quiz_game", "collect_to_complete"),
    ("saas_workspace", "sort_to_understand"),
    ("saas_workspace", "assemble_to_activate"),
    ("saas_workspace", "collect_to_complete"),
    ("commerce_workspace", "sort_to_understand"),
    ("commerce_workspace", "assemble_to_activate"),
    ("interactive_instrument", "tune_to_harmonize"),
    ("simulation_toy", "drag_to_transform"),
    ("museum_exhibit", "scan_to_compare"),
    ("spatial_exploration", "steer_to_explore"),
    ("narrative_microsite", "choose_to_branch"),
    ("creative_tool_interface", "paint_to_grow"),
    ("data_sculpture", "scrub_time_to_compare"),
    ("fictional_control_room", "press_sequence_to_unlock"),
    ("generative_poster", "mix_to_generate"),
    ("interactive_editorial", "hover_to_inspect"),
    ("visual_playground", "press_sequence_to_unlock"),
    ("product_demo_experience", "assemble_to_activate"),
    ("museum_exhibit", "zoom_to_inspect"),
    ("creative_tool_interface", "sort_to_understand"),
]

LOW_FRICTION_APP_FORMATS = [
    "travel_booking",
    "restaurant_ordering",
    "marketplace_comparison",
    "subscription_configurator",
    "habit_tracker",
    "budget_planner",
    "recipe_planner",
    "calendar_scheduler",
    "portfolio_builder",
]

HEAVY_WORKFLOW_FORMATS = [
    "kanban_workspace",
    "crm_pipeline",
    "invoice_builder",
    "analytics_explorer",
    "inventory_manager",
    "resume_screener",
    "support_triage",
]

RETENTION_TOY_FORMATS = [
    "drawing_studio",
    "music_step_sequencer",
    "color_palette_mixer",
    "poster_generator",
    "room_layout_builder",
    "avatar_customizer",
    "plant_growth_simulator",
    "weather_mixer",
]

FORMAT_FIRST_VARIANT_POOL = (
    GAME_FORMATS
    + GAME_FORMATS
    + GAME_FORMATS
    + GAME_FORMATS
    + RETENTION_TOY_FORMATS
    + RETENTION_TOY_FORMATS
    + LOW_FRICTION_APP_FORMATS
    + LOW_FRICTION_APP_FORMATS
    + PRODUCT_FORMATS
    + PRODUCT_FORMATS
    + PRODUCT_FORMATS
    + HEAVY_WORKFLOW_FORMATS
    + ["record_investigation", "map_explorer", "timeline_compare", "case_file_sorter"]
)

FORMAT_VARIANT_SPECS: Dict[str, Dict[str, str]] = {
    "platformer_collectathon": {
        "activity_type": "platformer",
        "core_mechanic": "platform_jump_and_collect",
        "experience_archetype": "browser_game",
        "primary_loop_type": "collect_to_complete",
    },
    "snake_grid": {
        "activity_type": "snake_game",
        "core_mechanic": "snake_collect_and_grow",
        "experience_archetype": "browser_game",
        "primary_loop_type": "collect_to_complete",
    },
    "tic_tac_toe": {
        "activity_type": "tic_tac_toe",
        "core_mechanic": "tic_tac_toe_turn_strategy",
        "experience_archetype": "quiz_game",
        "primary_loop_type": "choose_to_branch",
    },
    "trivia_quiz": {
        "activity_type": "quiz_game",
        "core_mechanic": "answer_questions_for_score",
        "experience_archetype": "quiz_game",
        "primary_loop_type": "answer_to_score",
    },
    "memory_match": {
        "activity_type": "memory_match",
        "core_mechanic": "flip_cards_to_match_pairs",
        "experience_archetype": "quiz_game",
        "primary_loop_type": "collect_to_complete",
    },
    "word_guess": {
        "activity_type": "word_game",
        "core_mechanic": "guess_word_with_limited_attempts",
        "experience_archetype": "quiz_game",
        "primary_loop_type": "answer_to_score",
    },
    "breakout_paddle": {
        "activity_type": "microgame",
        "core_mechanic": "breakout_paddle_bounce",
        "experience_archetype": "browser_game",
        "primary_loop_type": "collect_to_complete",
    },
    "minesweeper_grid": {
        "activity_type": "microgame",
        "core_mechanic": "minesweeper_deduction",
        "experience_archetype": "browser_game",
        "primary_loop_type": "hover_to_inspect",
    },
    "tile_merge_2048": {
        "activity_type": "microgame",
        "core_mechanic": "tile_merge_2048",
        "experience_archetype": "browser_game",
        "primary_loop_type": "assemble_to_activate",
    },
    "endless_runner": {
        "activity_type": "microgame",
        "core_mechanic": "endless_runner_dodge",
        "experience_archetype": "browser_game",
        "primary_loop_type": "steer_to_explore",
    },
    "rhythm_tap": {
        "activity_type": "microgame",
        "core_mechanic": "rhythm_tap_timing",
        "experience_archetype": "browser_game",
        "primary_loop_type": "press_sequence_to_unlock",
    },
    "whack_a_target": {
        "activity_type": "microgame",
        "core_mechanic": "whack_targets_for_score",
        "experience_archetype": "browser_game",
        "primary_loop_type": "collect_to_complete",
    },
    "sliding_tile_puzzle": {
        "activity_type": "microgame",
        "core_mechanic": "sliding_tile_reorder",
        "experience_archetype": "browser_game",
        "primary_loop_type": "assemble_to_activate",
    },
    "tower_defense_lite": {
        "activity_type": "microgame",
        "core_mechanic": "tower_defense_place_units",
        "experience_archetype": "browser_game",
        "primary_loop_type": "assemble_to_activate",
    },
    "pinball_table": {
        "activity_type": "microgame",
        "core_mechanic": "pinball_flipper_bounce",
        "experience_archetype": "browser_game",
        "primary_loop_type": "steer_to_explore",
    },
    "asteroids_shooter": {
        "activity_type": "microgame",
        "core_mechanic": "asteroids_thrust_and_shoot",
        "experience_archetype": "browser_game",
        "primary_loop_type": "steer_to_explore",
    },
    "maze_escape": {
        "activity_type": "microgame",
        "core_mechanic": "maze_escape_navigation",
        "experience_archetype": "browser_game",
        "primary_loop_type": "steer_to_explore",
    },
    "reaction_timer": {
        "activity_type": "microgame",
        "core_mechanic": "reaction_timer_challenge",
        "experience_archetype": "browser_game",
        "primary_loop_type": "press_sequence_to_unlock",
    },
    "fishing_timing": {
        "activity_type": "microgame",
        "core_mechanic": "fishing_timing_cast",
        "experience_archetype": "browser_game",
        "primary_loop_type": "press_sequence_to_unlock",
    },
    "basketball_arcade": {
        "activity_type": "microgame",
        "core_mechanic": "basketball_shot_arc",
        "experience_archetype": "browser_game",
        "primary_loop_type": "press_sequence_to_unlock",
    },
    "card_sort_strategy": {
        "activity_type": "microgame",
        "core_mechanic": "card_hand_strategy",
        "experience_archetype": "browser_game",
        "primary_loop_type": "sort_to_understand",
    },
    "typing_race": {
        "activity_type": "word_game",
        "core_mechanic": "typing_race_accuracy",
        "experience_archetype": "quiz_game",
        "primary_loop_type": "type_to_reveal",
    },
    "kanban_workspace": {
        "activity_type": "saas_replica",
        "core_mechanic": "filter_search_and_select_records",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "crm_pipeline": {
        "activity_type": "saas_replica",
        "core_mechanic": "filter_search_and_select_records",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "invoice_builder": {
        "activity_type": "saas_replica",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "analytics_explorer": {
        "activity_type": "saas_replica",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "scrub_time_to_compare",
    },
    "calendar_scheduler": {
        "activity_type": "saas_replica",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "inventory_manager": {
        "activity_type": "saas_replica",
        "core_mechanic": "filter_search_and_select_records",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "travel_booking": {
        "activity_type": "commerce_or_booking_flow",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "restaurant_ordering": {
        "activity_type": "commerce_or_booking_flow",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "marketplace_comparison": {
        "activity_type": "commerce_or_booking_flow",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "subscription_configurator": {
        "activity_type": "commerce_or_booking_flow",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "product_detail_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "sneaker_drop_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "press_sequence_to_unlock",
    },
    "skincare_product_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "coffee_subscription_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "choose_to_branch",
    },
    "furniture_product_configurator": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "course_sales_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "choose_branching_path",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "choose_to_branch",
    },
    "app_pricing_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "digital_template_store": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "event_ticket_checkout": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "marketplace_listing_page": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "limited_drop_countdown": {
        "activity_type": "product_or_storefront",
        "core_mechanic": "press_sequence_to_unlock",
        "experience_archetype": "commerce_workspace",
        "primary_loop_type": "press_sequence_to_unlock",
    },
    "portfolio_builder": {
        "activity_type": "saas_replica",
        "core_mechanic": "assemble_machine_or_layout",
        "experience_archetype": "product_demo_experience",
        "primary_loop_type": "assemble_to_activate",
    },
    "resume_screener": {
        "activity_type": "saas_replica",
        "core_mechanic": "filter_search_and_select_records",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "support_triage": {
        "activity_type": "saas_replica",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "habit_tracker": {
        "activity_type": "saas_replica",
        "core_mechanic": "collect_items_to_complete_set",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "collect_to_complete",
    },
    "budget_planner": {
        "activity_type": "saas_replica",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "assemble_to_activate",
    },
    "recipe_planner": {
        "activity_type": "saas_replica",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "saas_workspace",
        "primary_loop_type": "sort_to_understand",
    },
    "drawing_studio": {
        "activity_type": "creative_tool",
        "core_mechanic": "paint_or_draw_to_create_output",
        "experience_archetype": "creative_tool_interface",
        "primary_loop_type": "paint_to_grow",
    },
    "music_step_sequencer": {
        "activity_type": "creative_tool",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "creative_tool_interface",
        "primary_loop_type": "assemble_to_activate",
    },
    "map_route_planner": {
        "activity_type": "creative_tool",
        "core_mechanic": "navigate_map_or_space",
        "experience_archetype": "spatial_exploration",
        "primary_loop_type": "steer_to_explore",
    },
    "color_palette_mixer": {
        "activity_type": "creative_tool",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "creative_tool_interface",
        "primary_loop_type": "mix_to_generate",
    },
    "poster_generator": {
        "activity_type": "creative_tool",
        "core_mechanic": "paint_or_draw_to_create_output",
        "experience_archetype": "generative_poster",
        "primary_loop_type": "paint_to_grow",
    },
    "room_layout_builder": {
        "activity_type": "creative_tool",
        "core_mechanic": "assemble_machine_or_layout",
        "experience_archetype": "creative_tool_interface",
        "primary_loop_type": "assemble_to_activate",
    },
    "avatar_customizer": {
        "activity_type": "creative_tool",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "creative_tool_interface",
        "primary_loop_type": "assemble_to_activate",
    },
    "plant_growth_simulator": {
        "activity_type": "simulation",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "simulation_toy",
        "primary_loop_type": "drag_to_transform",
    },
    "weather_mixer": {
        "activity_type": "simulation",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "simulation_toy",
        "primary_loop_type": "mix_to_generate",
    },
    "data_story_scrubber": {
        "activity_type": "data_investigation",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "data_sculpture",
        "primary_loop_type": "scrub_time_to_compare",
    },
    "record_investigation": {
        "activity_type": "data_investigation",
        "core_mechanic": "filter_search_and_select_records",
        "experience_archetype": "interactive_editorial",
        "primary_loop_type": "sort_to_understand",
    },
    "map_explorer": {
        "activity_type": "narrative_explorer",
        "core_mechanic": "navigate_map_or_space",
        "experience_archetype": "spatial_exploration",
        "primary_loop_type": "steer_to_explore",
    },
    "timeline_compare": {
        "activity_type": "data_investigation",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "data_sculpture",
        "primary_loop_type": "scrub_time_to_compare",
    },
    "case_file_sorter": {
        "activity_type": "data_investigation",
        "core_mechanic": "sort_cards_into_meaningful_groups",
        "experience_archetype": "interactive_editorial",
        "primary_loop_type": "sort_to_understand",
    },
    "operating_panel": {
        "activity_type": "fake_os_app",
        "core_mechanic": "configure_product_or_system",
        "experience_archetype": "fictional_control_room",
        "primary_loop_type": "assemble_to_activate",
    },
}


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


def _activity_contract_for_variant(seed: int | None, activity_variant: str) -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:{activity_variant}:format-first-contract")
    spec = FORMAT_VARIANT_SPECS.get(activity_variant) or FORMAT_VARIANT_SPECS["breakout_paddle"]
    activity_type = spec["activity_type"]
    mechanic = spec["core_mechanic"]
    library_profile = _library_profile_for_activity(rng, activity_type, activity_variant, mechanic)
    disallowed = ["slider_only_controls", "buttons_only_toggle_visual_effects", "fake_metrics_without_task"]
    if activity_type in {"interactive_instrument", "simulation"}:
        disallowed = ["buttons_only_toggle_visual_effects", "fake_metrics_without_task", "no_goal_or_payoff"]
    return {
        "activity_type": activity_type,
        "activity_variant": activity_variant,
        "core_mechanic": mechanic,
        "library_profile": library_profile,
        "activity_goal": "Implement the selected recognizable format as the product, with semantic anchors used only as flavor.",
        "required_actions": _required_actions_for_mechanic(mechanic),
        "required_state": "Track score, progress, selections, records, cart, created output, unlocked stages, or configured choices in visible state.",
        "payoff": "Show a recognizable result for the selected format: score, win/loss, saved workflow state, checkout/booking result, preview, or created artifact.",
        "boredom_risks": disallowed,
        "success_signal": "The visitor can identify the format, use its core mechanic, and see a concrete result.",
        "retention_contract": _retention_contract_for_activity(activity_type, activity_variant),
    }


def seeded_format_first_target(seed: int | None = None) -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:format-first-target")
    activity_variant = rng.choice(FORMAT_FIRST_VARIANT_POOL)
    spec = FORMAT_VARIANT_SPECS.get(activity_variant) or FORMAT_VARIANT_SPECS["breakout_paddle"]
    activity_contract = _activity_contract_for_variant(seed, activity_variant)
    return {
        "experience_archetype": spec["experience_archetype"],
        "primary_loop_type": spec["primary_loop_type"],
        "activity_type": spec["activity_type"],
        "activity_contract": activity_contract,
        "format_first": True,
        "format_contract": {
            "activity_variant": activity_variant,
            "dominance_rule": "This selected activity_variant is the product. Semantic anchors may flavor visuals/copy but must not rename, obscure, or replace the recognizable format.",
        },
    }


def activity_family_for_variant(activity_variant: str) -> str:
    if activity_variant in {"word_guess", "typing_race"}:
        return "word_game"
    if activity_variant in {"trivia_quiz", "memory_match", "tic_tac_toe", "card_sort_strategy"}:
        return "quiz_card_game"
    if activity_variant in {"snake_grid", "breakout_paddle", "endless_runner", "rhythm_tap", "whack_a_target", "pinball_table", "asteroids_shooter", "maze_escape", "reaction_timer", "fishing_timing", "basketball_arcade", "platformer_collectathon"}:
        return "arcade_action"
    if activity_variant in {"minesweeper_grid", "tile_merge_2048", "sliding_tile_puzzle", "tower_defense_lite"}:
        return "puzzle_strategy"
    if activity_variant in {"room_layout_builder", "furniture_product_configurator"}:
        return "layout_builder"
    if activity_variant in {"drawing_studio", "poster_generator", "avatar_customizer", "color_palette_mixer"}:
        return "creative_canvas"
    if activity_variant in {"music_step_sequencer"}:
        return "audio_tool"
    if activity_variant in {"plant_growth_simulator", "weather_mixer"}:
        return "simulation_toy"
    if activity_variant in PRODUCT_FORMATS:
        return "product_storefront"
    if activity_variant in {"travel_booking", "restaurant_ordering", "marketplace_comparison", "subscription_configurator"}:
        return "commerce_flow"
    if activity_variant in {"kanban_workspace", "crm_pipeline", "invoice_builder", "analytics_explorer", "calendar_scheduler", "inventory_manager", "resume_screener", "support_triage", "habit_tracker", "budget_planner", "recipe_planner", "portfolio_builder"}:
        return "workspace_app"
    if activity_variant in {"map_route_planner", "map_explorer"}:
        return "map_tool"
    if activity_variant in {"data_story_scrubber", "record_investigation", "timeline_compare", "case_file_sorter"}:
        return "data_investigation"
    return "other"


def seeded_diverse_format_first_targets(
    seed: int | None,
    count: int,
    *,
    recent_variants: List[str] | None = None,
    recent_families: List[str] | None = None,
) -> List[Dict[str, object]]:
    rng = random.Random(f"{int(seed or 0)}:diverse-format-first-targets:{count}")
    recent_variants_set = set(recent_variants or [])
    recent_family_set = set(recent_families or [])
    used_variants: set[str] = set()
    used_families: set[str] = set()
    targets: List[Dict[str, object]] = []
    max_count = max(1, int(count or 1))

    for index in range(max_count):
        chosen_variant = ""
        chosen_family = ""
        for attempt in range(120):
            candidate = rng.choice(FORMAT_FIRST_VARIANT_POOL)
            family = activity_family_for_variant(candidate)
            if candidate in used_variants:
                continue
            if family in used_families and len(used_families) < 10:
                continue
            if candidate in recent_variants_set and attempt < 80:
                continue
            if family in recent_family_set and attempt < 60:
                continue
            chosen_variant = candidate
            chosen_family = family
            break
        if not chosen_variant:
            for candidate in FORMAT_FIRST_VARIANT_POOL:
                family = activity_family_for_variant(candidate)
                if candidate not in used_variants and (family not in used_families or len(used_families) >= 10):
                    chosen_variant = candidate
                    chosen_family = family
                    break
        if not chosen_variant:
            chosen_variant = rng.choice(FORMAT_FIRST_VARIANT_POOL)
            chosen_family = activity_family_for_variant(chosen_variant)
        used_variants.add(chosen_variant)
        used_families.add(chosen_family)
        spec = FORMAT_VARIANT_SPECS.get(chosen_variant) or FORMAT_VARIANT_SPECS["breakout_paddle"]
        site_seed = int(seed or 0) + ((index + 1) * 7919)
        activity_contract = _activity_contract_for_variant(site_seed, chosen_variant)
        targets.append(
            {
                "experience_archetype": spec["experience_archetype"],
                "primary_loop_type": spec["primary_loop_type"],
                "activity_type": spec["activity_type"],
                "activity_family": chosen_family,
                "activity_contract": activity_contract,
                "format_first": True,
                "format_contract": {
                    "activity_variant": chosen_variant,
                    "activity_family": chosen_family,
                    "dominance_rule": "This selected activity_variant is the product. Semantic anchors may flavor visuals/copy but must not rename, obscure, or replace the recognizable format.",
                },
            }
        )
    return targets


def seeded_genre_contract(seed: int | None = None, archetype: str = "", loop_type: str = "") -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:{archetype}:{loop_type}:genre-contract")
    page_genre_by_archetype = {
        "browser_game": "arcade_microgame",
        "quiz_game": "arcade_microgame",
        "saas_workspace": "app_workspace",
        "commerce_workspace": "product_storefront",
        "interactive_instrument": "creative_tool",
        "fictional_control_room": "fictional_control_room",
        "generative_poster": "narrative_artifact",
        "spatial_exploration": "museum_exhibit",
        "narrative_microsite": "narrative_artifact",
        "interactive_editorial": "interactive_editorial",
        "data_sculpture": "data_workspace",
        "simulation_toy": "toy_simulator",
        "museum_exhibit": "museum_exhibit",
        "visual_playground": "arcade_microgame",
        "product_demo_experience": "creative_tool",
        "creative_tool_interface": "creative_tool",
    }
    page_genre = page_genre_by_archetype.get(archetype, rng.choice(PAGE_GENRES))
    copy_density = {
        "arcade_microgame": "almost_none",
        "toy_simulator": "low",
        "app_workspace": "medium",
        "product_storefront": "low",
        "fictional_control_room": "low",
        "museum_exhibit": "medium",
        "narrative_artifact": "medium",
        "data_workspace": "medium",
        "interactive_editorial": "medium",
        "creative_tool": "low",
    }.get(page_genre, "low")
    instruction_policy = "one_microcue" if copy_density in {"almost_none", "low"} else "labels_allowed"
    if page_genre == "museum_exhibit":
        instruction_policy = "labels_allowed"
    if page_genre == "data_workspace":
        instruction_policy = "labels_allowed"
    return {
        "page_genre": page_genre,
        "copy_density": copy_density,
        "visual_density": rng.choice(["sparse", "focused", "dense"]),
        "palette_strategy": rng.choice(PALETTE_STRATEGIES),
        "motion_language": rng.choice(MOTION_LANGUAGES),
        "instruction_policy": instruction_policy,
        "chrome_policy": "dashboard_when_essential" if page_genre in {"fictional_control_room", "data_workspace", "app_workspace"} else "minimal_functional",
        "focal_rule": "One dominant interactive stage; secondary controls must stay visually attached to the object they affect.",
        "copy_budget": "Use labels and one-line cues; avoid explanatory paragraphs unless the genre is editorial or museum-like.",
        "entry_rule": "Make the first interaction available on load or behind one obvious action. Do not require reading a tutorial first.",
        "retention_rule": "Give the visitor a quick loop with feedback, score/progress/result, and a reason to try again.",
        "jargon_policy": "Use plain product/game words. Do not use calibration, protocol, terminal, compiler, telemetry, lux, signal, frequency, drift, manifest, system, Roulette, NDW, runtime, or non-deterministic in visible copy.",
        "physical_metaphor_rule": "Where compatible, express the interface as a tactile machine, board, deck, receipt, ticket, cabinet, paper tray, dial, counter, or workbench instead of abstract floating panels.",
        "palette_roles": {
            "background": "dominant quiet field",
            "surface": "supporting surface",
            "primary_accent": "single action/feedback accent",
            "secondary_accent": "rare emphasis accent",
            "text": "high-contrast readable text",
        },
    }


def seeded_activity_contract(seed: int | None = None, archetype: str = "", loop_type: str = "") -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:{archetype}:{loop_type}:activity-contract")
    activity_by_archetype = {
        "browser_game": "microgame",
        "quiz_game": "quiz_game",
        "saas_workspace": "saas_replica",
        "commerce_workspace": "commerce_or_booking_flow",
        "interactive_instrument": "interactive_instrument",
        "fictional_control_room": "fake_os_app",
        "generative_poster": "creative_tool",
        "spatial_exploration": "narrative_explorer",
        "narrative_microsite": "narrative_explorer",
        "interactive_editorial": "data_investigation",
        "data_sculpture": "data_investigation",
        "simulation_toy": "simulation",
        "museum_exhibit": "data_investigation",
        "visual_playground": "microgame",
        "product_demo_experience": "saas_replica",
        "creative_tool_interface": "creative_tool",
    }
    activity_type = activity_by_archetype.get(archetype, rng.choice(ACTIVITY_TYPES))
    mechanics_by_activity = {
        "platformer": ["platform_jump_and_collect", "navigate_map_or_space", "collect_items_to_complete_set"],
        "snake_game": ["snake_collect_and_grow", "collect_items_to_complete_set", "navigate_map_or_space"],
        "tic_tac_toe": ["tic_tac_toe_turn_strategy", "choose_branching_path", "unlock_sequence_or_stages"],
        "quiz_game": ["answer_questions_for_score", "choose_branching_path", "collect_items_to_complete_set"],
        "memory_match": ["flip_cards_to_match_pairs", "collect_items_to_complete_set", "sort_cards_into_meaningful_groups"],
        "word_game": ["guess_word_with_limited_attempts", "type_commands_or_messages", "unlock_sequence_or_stages"],
        "microgame": ["collect_items_to_complete_set", "unlock_sequence_or_stages", "navigate_map_or_space"],
        "saas_replica": ["filter_search_and_select_records", "configure_product_or_system", "sort_cards_into_meaningful_groups"],
        "creative_tool": ["paint_or_draw_to_create_output", "assemble_machine_or_layout", "configure_product_or_system"],
        "puzzle_box": ["unlock_sequence_or_stages", "inspect_compare_and_act", "type_commands_or_messages"],
        "simulation": ["configure_product_or_system", "navigate_map_or_space", "inspect_compare_and_act"],
        "fake_os_app": ["type_commands_or_messages", "filter_search_and_select_records", "assemble_machine_or_layout"],
        "commerce_or_booking_flow": ["filter_search_and_select_records", "configure_product_or_system", "choose_branching_path"],
        "product_or_storefront": ["configure_product_or_system", "sort_cards_into_meaningful_groups", "choose_branching_path"],
        "portfolio_or_brand_site": ["navigate_map_or_space", "inspect_compare_and_act", "choose_branching_path"],
        "narrative_explorer": ["choose_branching_path", "inspect_compare_and_act", "navigate_map_or_space"],
        "data_investigation": ["filter_search_and_select_records", "sort_cards_into_meaningful_groups", "inspect_compare_and_act"],
        "interactive_instrument": ["type_commands_or_messages", "configure_product_or_system", "paint_or_draw_to_create_output"],
    }
    mechanics_by_variant = {
        "platformer_collectathon": ("platformer", "platform_jump_and_collect"),
        "snake_grid": ("snake_game", "snake_collect_and_grow"),
        "tic_tac_toe": ("tic_tac_toe", "tic_tac_toe_turn_strategy"),
        "trivia_quiz": ("quiz_game", "answer_questions_for_score"),
        "memory_match": ("memory_match", "flip_cards_to_match_pairs"),
        "word_guess": ("word_game", "guess_word_with_limited_attempts"),
        "breakout_paddle": ("microgame", "breakout_paddle_bounce"),
        "minesweeper_grid": ("microgame", "minesweeper_deduction"),
        "tile_merge_2048": ("microgame", "tile_merge_2048"),
        "endless_runner": ("microgame", "endless_runner_dodge"),
        "rhythm_tap": ("microgame", "rhythm_tap_timing"),
        "whack_a_target": ("microgame", "whack_targets_for_score"),
        "sliding_tile_puzzle": ("microgame", "sliding_tile_reorder"),
        "tower_defense_lite": ("microgame", "tower_defense_place_units"),
        "pinball_table": ("microgame", "pinball_flipper_bounce"),
        "asteroids_shooter": ("microgame", "asteroids_thrust_and_shoot"),
        "maze_escape": ("microgame", "maze_escape_navigation"),
        "reaction_timer": ("microgame", "reaction_timer_challenge"),
        "fishing_timing": ("microgame", "fishing_timing_cast"),
        "basketball_arcade": ("microgame", "basketball_shot_arc"),
        "card_sort_strategy": ("microgame", "card_hand_strategy"),
        "typing_race": ("word_game", "typing_race_accuracy"),
    }
    app_mechanics = {
        "kanban_workspace": "filter_search_and_select_records",
        "crm_pipeline": "filter_search_and_select_records",
        "invoice_builder": "configure_product_or_system",
        "analytics_explorer": "sort_cards_into_meaningful_groups",
        "calendar_scheduler": "configure_product_or_system",
        "inventory_manager": "filter_search_and_select_records",
        "travel_booking": "configure_product_or_system",
        "restaurant_ordering": "configure_product_or_system",
        "marketplace_comparison": "sort_cards_into_meaningful_groups",
        "subscription_configurator": "configure_product_or_system",
        "product_detail_page": "configure_product_or_system",
        "sneaker_drop_page": "configure_product_or_system",
        "skincare_product_page": "configure_product_or_system",
        "coffee_subscription_page": "configure_product_or_system",
        "furniture_product_configurator": "configure_product_or_system",
        "course_sales_page": "choose_branching_path",
        "app_pricing_page": "sort_cards_into_meaningful_groups",
        "digital_template_store": "sort_cards_into_meaningful_groups",
        "event_ticket_checkout": "configure_product_or_system",
        "marketplace_listing_page": "sort_cards_into_meaningful_groups",
        "limited_drop_countdown": "configure_product_or_system",
        "portfolio_builder": "assemble_machine_or_layout",
        "resume_screener": "filter_search_and_select_records",
        "support_triage": "sort_cards_into_meaningful_groups",
        "habit_tracker": "collect_items_to_complete_set",
        "budget_planner": "configure_product_or_system",
        "recipe_planner": "sort_cards_into_meaningful_groups",
    }
    tool_mechanics = {
        "drawing_studio": "paint_or_draw_to_create_output",
        "music_step_sequencer": "configure_product_or_system",
        "map_route_planner": "navigate_map_or_space",
        "color_palette_mixer": "configure_product_or_system",
        "poster_generator": "paint_or_draw_to_create_output",
        "room_layout_builder": "assemble_machine_or_layout",
        "avatar_customizer": "configure_product_or_system",
        "plant_growth_simulator": "configure_product_or_system",
        "weather_mixer": "configure_product_or_system",
        "data_story_scrubber": "sort_cards_into_meaningful_groups",
    }
    activity_variant = ""
    if archetype in {"browser_game", "visual_playground"}:
        activity_variant = rng.choice(GAME_FORMATS)
        activity_type, forced_mechanic = mechanics_by_variant[activity_variant]
    if archetype == "quiz_game":
        activity_variant = rng.choice(["trivia_quiz", "memory_match", "word_guess", "tic_tac_toe", "reaction_timer", "typing_race"])
        activity_type, forced_mechanic = mechanics_by_variant[activity_variant]
    if archetype in {"saas_workspace", "commerce_workspace", "product_demo_experience"}:
        activity_variant = rng.choice(PRODUCT_FORMATS + LOW_FRICTION_APP_FORMATS if archetype == "commerce_workspace" else APP_FORMATS)
        activity_type = "product_or_storefront" if activity_variant in PRODUCT_FORMATS else ("commerce_or_booking_flow" if archetype == "commerce_workspace" else "saas_replica")
        forced_mechanic = app_mechanics[activity_variant]
    if archetype in {"creative_tool_interface", "generative_poster", "interactive_instrument", "simulation_toy"}:
        activity_variant = rng.choice(TOOL_FORMATS)
        forced_mechanic = tool_mechanics[activity_variant]
        if archetype == "simulation_toy":
            activity_type = "simulation"
        elif archetype == "interactive_instrument":
            activity_type = "interactive_instrument"
        else:
            activity_type = "creative_tool"
    mechanic = locals().get("forced_mechanic") or rng.choice(mechanics_by_activity.get(activity_type, MECHANIC_PATTERNS))
    if not activity_variant:
        if activity_type in {"fake_os_app", "data_investigation", "narrative_explorer"}:
            activity_variant = rng.choice(["record_investigation", "map_explorer", "timeline_compare", "case_file_sorter", "operating_panel"])
        else:
            activity_variant = rng.choice(APP_FORMATS + TOOL_FORMATS)
    library_profile = _library_profile_for_activity(rng, activity_type, activity_variant, mechanic)
    disallowed = ["slider_only_controls", "buttons_only_toggle_visual_effects", "fake_metrics_without_task"]
    if activity_type in {"interactive_instrument", "simulation"}:
        disallowed = ["buttons_only_toggle_visual_effects", "fake_metrics_without_task", "no_goal_or_payoff"]
    return {
        "activity_type": activity_type,
        "activity_variant": activity_variant,
        "core_mechanic": mechanic,
        "library_profile": library_profile,
        "activity_goal": "Give the visitor a concrete task with a visible end state or useful output.",
        "required_actions": _required_actions_for_mechanic(mechanic),
        "required_state": "Track progress, selections, created output, unlocked stages, or configured choices in visible state.",
        "payoff": "Show a result, completion state, unlocked reveal, saved item, score, or transformed artifact.",
        "boredom_risks": disallowed,
        "success_signal": "The visitor can tell what changed, why it matters, and what they accomplished.",
        "retention_contract": _retention_contract_for_activity(activity_type, activity_variant),
    }


def _library_profile_for_activity(rng: random.Random, activity_type: str, activity_variant: str, mechanic: str) -> str:
    physics_variants = {
        "breakout_paddle",
        "pinball_table",
        "basketball_arcade",
        "fishing_timing",
        "whack_a_target",
    }
    if activity_variant in physics_variants:
        return "matter_physics_game"
    if activity_type in {"platformer", "snake_game", "microgame"}:
        return rng.choice(["ndw_canvas_game_loop", "ndw_audio_particles", "dom_css_state_machine"])
    if activity_type in {"tic_tac_toe", "quiz_game", "memory_match", "word_game"}:
        return rng.choice(["dom_css_state_machine", "gsap_state_transition", "alpine_ui_state", "ndw_audio_particles"])
    if "map" in activity_variant or "orbit" in mechanic:
        return rng.choice(["three_orbit_scene", "three_bloom_scene", "ndw_canvas_game_loop"])
    if activity_type in {"saas_replica", "commerce_or_booking_flow", "product_or_storefront"}:
        return "alpine_ui_state"
    if activity_type in {"creative_tool", "simulation", "interactive_instrument"}:
        return rng.choice(["ndw_canvas_game_loop", "gsap_timeline_dom", "three_orbit_scene", "ndw_audio_particles"])
    return rng.choice(LIBRARY_PROFILES)


def _retention_contract_for_activity(activity_type: str, activity_variant: str) -> Dict[str, str]:
    if activity_type in {"platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game", "microgame"}:
        return {
            "entry": "Start immediately or with one obvious Play button. No fake workspace, protocol, calibration, or terminal wrapper.",
            "loop_length": "A satisfying attempt should take 20-60 seconds.",
            "reward": "Show score plus at least one meta-reward such as combo, streak, best score, tickets, medals, lives, level, or unlock.",
            "copy": "Use a plain recognizable game title and a 3-7 word control cue.",
            "feedback": "Every input should cause visible motion, collision, progress, soundless juice, or score/state feedback.",
        }
    if activity_type == "product_or_storefront":
        return {
            "entry": "Open with a complete product hero: product image/visual, name, price or plan, benefits/specs, variant selector, and primary buy/reserve/add-to-cart action.",
            "loop_length": "The first commerce payoff should be reachable in one click: selected variant, cart drawer, checkout summary, receipt, or reserved ticket.",
            "reward": "Show a cart/checkout/receipt/selected-plan state plus stock/drop/timer/social-proof feedback when compatible.",
            "copy": "Use normal ecommerce words: product, price, size, color, plan, cart, checkout, reserve, buy, compare.",
            "feedback": "Variant, quantity, plan, or add-to-cart actions must visibly update the product preview and checkout/cart state.",
        }
    if activity_type in {"saas_replica", "commerce_or_booking_flow", "data_investigation", "fake_os_app"}:
        return {
            "entry": "Open with sample records/items already loaded. No blank dashboard or empty table as the first view.",
            "loop_length": "The first useful result should be reachable in one click or one edit.",
            "reward": "Show a saved state, selected record, receipt, itinerary, comparison, triage result, or configured summary.",
            "copy": "Use normal app language and concrete domain nouns; avoid sci-fi labels unless the domain is actually fictional.",
            "feedback": "Search, filter, select, create, save, or configure actions must visibly change data and status.",
        }
    if activity_type in {"creative_tool", "interactive_instrument", "simulation"}:
        return {
            "entry": "Show an existing preview/artifact first, then invite direct manipulation.",
            "loop_length": "The visitor should create or transform something in the first 10 seconds.",
            "reward": "Include Randomize, Remix, Save, Export, Capture, or Reset so the output feels replayable.",
            "copy": "Use tool labels near the canvas or preview; avoid paragraphs and abstract system copy.",
            "feedback": "Controls must affect the artifact, composition, forecast, layout, beat, drawing, or simulated state.",
        }
    return {
        "entry": "Make the first action obvious and available immediately.",
        "loop_length": "The first meaningful result should appear within 10 seconds.",
        "reward": "Show progress, saved state, score, result, or created output.",
        "copy": "Use plain human-facing words.",
        "feedback": "Every primary control must visibly change state.",
    }


def _required_actions_for_mechanic(mechanic: str) -> List[str]:
    return {
        "drag_objects_into_zones": ["drag", "drop", "arrange"],
        "platform_jump_and_collect": ["move", "jump", "collect"],
        "snake_collect_and_grow": ["steer", "collect", "avoid collision"],
        "tic_tac_toe_turn_strategy": ["choose square", "block opponent", "complete row"],
        "answer_questions_for_score": ["read question", "choose answer", "score result"],
        "flip_cards_to_match_pairs": ["flip card", "remember position", "match pair"],
        "guess_word_with_limited_attempts": ["type guess", "check letters", "solve word"],
        "breakout_paddle_bounce": ["move paddle", "bounce ball", "break bricks"],
        "minesweeper_deduction": ["open tile", "flag mine", "clear safe grid"],
        "tile_merge_2048": ["slide tiles", "merge numbers", "reach target tile"],
        "endless_runner_dodge": ["jump", "duck", "dodge obstacles"],
        "rhythm_tap_timing": ["watch beat", "tap on time", "build combo"],
        "whack_targets_for_score": ["spot target", "click quickly", "score streak"],
        "sliding_tile_reorder": ["slide tile", "restore order", "solve board"],
        "tower_defense_place_units": ["place unit", "start wave", "defend path"],
        "pinball_flipper_bounce": ["launch ball", "flip paddles", "hit bumpers"],
        "asteroids_thrust_and_shoot": ["thrust", "rotate", "shoot asteroids"],
        "maze_escape_navigation": ["move", "avoid traps", "reach exit"],
        "reaction_timer_challenge": ["wait for signal", "react fast", "compare time"],
        "fishing_timing_cast": ["cast", "time reel", "catch target"],
        "basketball_shot_arc": ["aim", "set power", "shoot ball"],
        "card_hand_strategy": ["draw card", "choose play", "score hand"],
        "typing_race_accuracy": ["type prompt", "avoid errors", "beat timer"],
        "collect_items_to_complete_set": ["move", "collect", "complete"],
        "sort_cards_into_meaningful_groups": ["sort", "select", "compare"],
        "paint_or_draw_to_create_output": ["draw", "paint", "generate output"],
        "filter_search_and_select_records": ["search", "filter", "select"],
        "configure_product_or_system": ["choose options", "apply configuration", "preview result"],
        "assemble_machine_or_layout": ["pick parts", "assemble", "activate"],
        "navigate_map_or_space": ["navigate", "inspect", "discover"],
        "type_commands_or_messages": ["type", "submit", "unlock response"],
        "choose_branching_path": ["choose", "branch", "reveal consequence"],
        "unlock_sequence_or_stages": ["attempt sequence", "unlock", "progress"],
        "inspect_compare_and_act": ["inspect", "compare", "act"],
    }.get(mechanic, ["act", "observe result", "continue"])
