from __future__ import annotations

import random
from typing import Dict, List, Tuple

from data.load_variants import (
    ACTIVITY_FAMILY_MAP,
    ALL_FORMATS,
    CORE_MECHANICS,
    FORMAT_VARIANT_SPECS,
    choose_weighted_variant,
    validate_catalog_domains,
)



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

GENRE_VISUAL_DENSITIES = ["sparse", "focused", "dense", "maximal", "variable_adaptive", "zoned", "generous_white"]

PALETTE_STRATEGIES = [
    "monochrome_accent",
    "muted_plus_toxic",
    "arcade_dark_shell",
    "editorial_neutral",
    "pastel_toy",
    "high_contrast_game",
    "earth_material_accent",
    "warm_amber",
    "forest_natural",
    "ocean_coastal",
    "zen_minimal",
    "tropical_vibrant",
]

MOTION_LANGUAGES = [
    "snappy_gamefeel",
    "slow_cinematic",
    "dashboard_subtle",
    "playful_elastic",
    "glitchy_unstable",
    "calm_product",
    "scroll_parallax",
    "staggered_sequence",
    "liquid_smooth",
    "spring_bounce",
    "hover_ambient",
    "kinetic_type",
    "float_dreamy",
    "morph_shape",
    "grain_texture",
    "neon_pulse",
    "minimal_fade",
]

INSTRUCTION_POLICIES = [
    "affordance_only",
    "one_microcue",
    "labels_allowed",
    "documentation_allowed",
    "visual_cue_only",
    "embedded_hint",
    "contextual_tooltip",
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
    "sudoku_fill_number_grid",
    "connect_four_drop_disc",
    "solitaire_sort_stacks",
    "pong_bounce_ball",
    "flappy_bird_dodge_pipe",
    "darts_throw_for_score",
    "bowling_knock_pins",
    "air_hockey_strike_puck",
]
MECHANIC_PATTERNS = list(dict.fromkeys(MECHANIC_PATTERNS + CORE_MECHANICS))

validate_catalog_domains(
    activity_types=ACTIVITY_TYPES,
    experience_archetypes=EXPERIENCE_ARCHETYPES,
    primary_loop_types=PRIMARY_LOOP_TYPES,
)

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



def _resolve_spec(spec: Dict[str, str | List[str]], variant: str, seed: int | None = None) -> Dict[str, str]:
    rng = random.Random(f"{int(seed or 0)}:{variant}:resolve-spec")
    resolved: Dict[str, str] = {}
    for key, value in spec.items():
        if isinstance(value, list):
            resolved[key] = rng.choice(value)
        else:
            resolved[key] = value
    return resolved


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
    spec = _resolve_spec(FORMAT_VARIANT_SPECS.get(activity_variant) or FORMAT_VARIANT_SPECS["breakout_paddle"], activity_variant, seed)
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
    activity_variant = choose_weighted_variant(rng)
    spec = _resolve_spec(FORMAT_VARIANT_SPECS.get(activity_variant) or FORMAT_VARIANT_SPECS["breakout_paddle"], activity_variant, seed)
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
    return ACTIVITY_FAMILY_MAP.get(activity_variant, "other")


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
            candidate = choose_weighted_variant(rng, excluded=used_variants)
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
            for candidate in ALL_FORMATS:
                family = activity_family_for_variant(candidate)
                if candidate not in used_variants and (family not in used_families or len(used_families) >= 10):
                    chosen_variant = candidate
                    chosen_family = family
                    break
        if not chosen_variant:
            chosen_variant = choose_weighted_variant(rng)
            chosen_family = activity_family_for_variant(chosen_variant)
        used_variants.add(chosen_variant)
        used_families.add(chosen_family)
        site_seed = int(seed or 0) + ((index + 1) * 7919)
        spec = _resolve_spec(FORMAT_VARIANT_SPECS.get(chosen_variant) or FORMAT_VARIANT_SPECS["breakout_paddle"], chosen_variant, site_seed)
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
    def matching_variants(*, require_archetype: bool, require_loop: bool) -> List[str]:
        matches: List[str] = []
        for variant, raw_spec in FORMAT_VARIANT_SPECS.items():
            archetypes = raw_spec["experience_archetype"]
            loops = raw_spec["primary_loop_type"]
            if isinstance(archetypes, str):
                archetypes = [archetypes]
            if isinstance(loops, str):
                loops = [loops]
            if require_archetype and archetype and archetype not in archetypes:
                continue
            if require_loop and loop_type and loop_type not in loops:
                continue
            matches.append(variant)
        return matches

    candidates = matching_variants(require_archetype=True, require_loop=True)
    if not candidates:
        candidates = matching_variants(require_archetype=True, require_loop=False)
    if not candidates:
        candidates = matching_variants(require_archetype=False, require_loop=True)
    if not candidates:
        candidates = list(ALL_FORMATS)
    return _activity_contract_for_variant(seed, rng.choice(candidates))


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
        "sudoku_fill_number_grid": ["place number", "check row", "complete grid"],
        "connect_four_drop_disc": ["drop disc", "block opponent", "connect four"],
        "solitaire_sort_stacks": ["draw card", "stack by suit", "clear tableau"],
        "pong_bounce_ball": ["move paddle", "bounce ball", "score point"],
        "flappy_bird_dodge_pipe": ["tap to flap", "dodge pipe", "avoid ground"],
        "darts_throw_for_score": ["aim", "throw dart", "hit target"],
        "bowling_knock_pins": ["aim", "roll ball", "knock pins"],
        "air_hockey_strike_puck": ["move striker", "hit puck", "score goal"],
        "idle_clicker_earn_upgrades": ["click", "buy upgrade", "watch numbers grow"],
        "wordle_feedback_guess": ["type word", "check colors", "narrow letters"],
        "match_three_swap_tiles": ["swap tiles", "match three", "clear board"],
        "tetris_stack_falling_shapes": ["rotate piece", "move sideways", "drop and clear"],
        "io_arena_eat_and_grow": ["move cell", "eat smaller", "avoid bigger"],
        "drawing_guessing_pictionary": ["draw prompt", "submit", "let AI guess"],
        "bubble_shooter_aim_match": ["aim", "shoot bubble", "match colors"],
        "physics_catapult_projectile": ["aim trajectory", "set power", "launch"],
        "color_sort_pour_liquid": ["select bottle", "pour color", "sort all layers"],
        "blackjack_hand_strategy": ["hit", "stand", "beat dealer"],
        "browse_and_simulate_order": ["browse items", "add to cart", "preview order"],
    }.get(mechanic, ["act", "observe result", "continue"])
