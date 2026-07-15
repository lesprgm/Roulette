from __future__ import annotations

import random
from typing import Dict, List

from data.format_catalog import (
    FORMAT_FAMILY_MAP,
    ALL_FORMATS,
    CORE_MECHANICS,
    FORMAT_SPECS,
    choose_weighted_format,
    validate_catalog_domains,
)

INTERACTION_PATTERNS = [
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

INTERACTION_LOOPS = [
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
]

FORMAT_CATEGORIES = [
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
    format_categories=FORMAT_CATEGORIES,
    interaction_patterns=INTERACTION_PATTERNS,
    interaction_loops=INTERACTION_LOOPS,
)

BORING_INTERACTION_PATTERNS = [
    "slider_only_controls",
    "buttons_only_toggle_visual_effects",
    "fake_metrics_without_task",
    "decorative_dashboard_chrome",
    "no_goal_or_payoff",
    "no_persistent_state",
]

INTERACTION_FAILURE_MODES = [
    "decorative_only_interaction",
    "unclear_first_action",
    "dead_controls",
    "word_salad_labels",
    "no_state_change",
    "no_continue_reason",
    "visual_noise_over_primary_action",
    "desktop_only_interaction",
]


def _resolve_spec(spec: Dict[str, str | List[str]], format_id: str, seed: int | None = None) -> Dict[str, str]:
    rng = random.Random(f"{int(seed or 0)}:{format_id}:resolve-spec")
    resolved: Dict[str, str] = {}
    for key, value in spec.items():
        if isinstance(value, list):
            resolved[key] = rng.choice(value)
        else:
            resolved[key] = value
    return resolved


def _as_list(value: str | List[str]) -> List[str]:
    return value if isinstance(value, list) else [value]


def _deabstract_loop(format_category: str, loop_type: str) -> str:
    if loop_type == "press_sequence_to_unlock":
        if format_category in {"platformer", "snake_game", "microgame"}:
            return "collect_to_complete"
        if format_category in {"saas_replica", "commerce_or_booking_flow", "product_or_storefront"}:
            return "assemble_to_activate"
        if format_category in {"creative_tool", "interactive_instrument", "simulation"}:
            return "drag_to_transform"
        return "choose_to_branch"
    if loop_type == "type_to_reveal" and format_category not in {"word_game", "narrative_explorer"}:
        return "collect_to_complete"
    return loop_type


def _format_spec_for_id(seed: int | None, format_id: str) -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:{format_id}:format-first-contract")
    spec = _resolve_spec(FORMAT_SPECS.get(format_id) or FORMAT_SPECS["breakout_paddle"], format_id, seed)
    format_category = spec["format_category"]
    spec["interaction_loop"] = _deabstract_loop(format_category, spec["interaction_loop"])
    mechanic = spec["core_mechanic"]
    library_profile = _library_profile_for_format(rng, format_category, format_id, mechanic)
    disallowed = ["slider_only_controls", "buttons_only_toggle_visual_effects", "fake_metrics_without_task"]
    if format_category in {"interactive_instrument", "simulation"}:
        disallowed = ["buttons_only_toggle_visual_effects", "fake_metrics_without_task", "no_goal_or_payoff"]
    return {
        "format_category": format_category,
        "format_id": format_id,
        "core_mechanic": mechanic,
        "reward_mechanic": spec["reward_mechanic"],
        "library_profile": library_profile,
        "implementation_goal": "Implement the selected recognizable format as the product, with art direction supporting its task and payoff.",
        "required_actions": _required_actions_for_mechanic(mechanic),
        "required_state": "Track score, progress, selections, records, cart, created output, unlocked stages, or configured choices in visible state.",
        "payoff": "Show a recognizable result for the selected format: score, win/loss, saved workflow state, checkout/booking result, preview, delivery/route tracker, or created artifact.",
        "boredom_risks": disallowed,
        "success_signal": "The visitor can identify the format, use its core mechanic, and see a concrete result.",
        "retention_contract": _retention_contract_for_format(format_category, format_id),
    }


def seeded_format_first_target(
    seed: int | None = None,
    *,
    recent_format_ids: List[str] | None = None,
    recent_format_families: List[str] | None = None,
    recent_interaction_loops: List[str] | None = None,
    recent_reward_mechanics: List[str] | None = None,
) -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:format-first-target")
    recent_format_ids_set = set(recent_format_ids or [])
    recent_format_families_set = set(recent_format_families or [])
    recent_interaction_loops_set = set(recent_interaction_loops or [])
    recent_reward_mechanics_set = set(recent_reward_mechanics or [])
    format_id = ""
    for attempt in range(120):
        candidate = choose_weighted_format(rng)
        family = format_family_for_id(candidate)
        raw_spec = FORMAT_SPECS.get(candidate) or FORMAT_SPECS["breakout_paddle"]
        loops = {_deabstract_loop(str(raw_spec["format_category"]), loop) for loop in _as_list(raw_spec["interaction_loop"])}
        rewards = set(_as_list(raw_spec["reward_mechanic"]))
        if candidate in recent_format_ids_set and attempt < 90:
            continue
        if family in recent_format_families_set and attempt < 70:
            continue
        if loops & recent_interaction_loops_set and attempt < 50:
            continue
        if rewards & recent_reward_mechanics_set and attempt < 40:
            continue
        format_id = candidate
        break
    if not format_id:
        format_id = choose_weighted_format(rng)
    spec = _resolve_spec(FORMAT_SPECS.get(format_id) or FORMAT_SPECS["breakout_paddle"], format_id, seed)
    format_spec = _format_spec_for_id(seed, format_id)
    return {
        "interaction_pattern": spec["interaction_pattern"],
        "interaction_loop": spec["interaction_loop"],
        "format_category": spec["format_category"],
        "format_spec": format_spec,
        "format_first": True,
        "format_selection": {
            "format_id": format_id,
            "dominance_rule": "The selected format is the product. Art direction may support it but must not rename, obscure, or replace it.",
        },
    }


def format_family_for_id(format_id: str) -> str:
    return FORMAT_FAMILY_MAP.get(format_id, "other")


def seeded_diverse_format_first_targets(
    seed: int | None,
    count: int,
    *,
    recent_format_ids: List[str] | None = None,
    recent_format_families: List[str] | None = None,
    recent_interaction_loops: List[str] | None = None,
    recent_reward_mechanics: List[str] | None = None,
) -> List[Dict[str, object]]:
    rng = random.Random(f"{int(seed or 0)}:diverse-format-first-targets:{count}")
    recent_format_ids_set = set(recent_format_ids or [])
    recent_format_family_set = set(recent_format_families or [])
    recent_interaction_loop_set = set(recent_interaction_loops or [])
    recent_reward_mechanic_set = set(recent_reward_mechanics or [])
    used_format_ids: set[str] = set()
    used_format_families: set[str] = set()
    targets: List[Dict[str, object]] = []
    max_count = max(1, int(count or 1))

    for index in range(max_count):
        chosen_format_id = ""
        chosen_format_family = ""
        for attempt in range(120):
            candidate = choose_weighted_format(rng, excluded=used_format_ids)
            family = format_family_for_id(candidate)
            raw_spec = FORMAT_SPECS.get(candidate) or FORMAT_SPECS["breakout_paddle"]
            loops = {_deabstract_loop(str(raw_spec["format_category"]), loop) for loop in _as_list(raw_spec["interaction_loop"])}
            rewards = set(_as_list(raw_spec["reward_mechanic"]))
            if candidate in used_format_ids:
                continue
            if family in used_format_families and len(used_format_families) < 10:
                continue
            if candidate in recent_format_ids_set and attempt < 80:
                continue
            if family in recent_format_family_set and attempt < 60:
                continue
            if loops & recent_interaction_loop_set and attempt < 45:
                continue
            if rewards & recent_reward_mechanic_set and attempt < 35:
                continue
            chosen_format_id = candidate
            chosen_format_family = family
            break
        if not chosen_format_id:
            for candidate in ALL_FORMATS:
                family = format_family_for_id(candidate)
                if candidate not in used_format_ids and (family not in used_format_families or len(used_format_families) >= 10):
                    chosen_format_id = candidate
                    chosen_format_family = family
                    break
        if not chosen_format_id:
            chosen_format_id = choose_weighted_format(rng)
            chosen_format_family = format_family_for_id(chosen_format_id)
        used_format_ids.add(chosen_format_id)
        used_format_families.add(chosen_format_family)
        site_seed = int(seed or 0) + ((index + 1) * 7919)
        spec = _resolve_spec(FORMAT_SPECS.get(chosen_format_id) or FORMAT_SPECS["breakout_paddle"], chosen_format_id, site_seed)
        spec["interaction_loop"] = _deabstract_loop(spec["format_category"], spec["interaction_loop"])
        format_spec = _format_spec_for_id(site_seed, chosen_format_id)
        targets.append(
            {
                "interaction_pattern": spec["interaction_pattern"],
                "interaction_loop": spec["interaction_loop"],
                "format_category": spec["format_category"],
                "format_family": chosen_format_family,
                "format_spec": format_spec,
                "format_first": True,
                "format_selection": {
                    "format_id": chosen_format_id,
                    "format_family": chosen_format_family,
                    "dominance_rule": "The selected format is the product. Art direction may support it but must not rename, obscure, or replace it.",
                },
            }
        )
    return targets


def seeded_genre_contract(
    seed: int | None = None,
    archetype: str = "",
    loop_type: str = "",
) -> Dict[str, object]:
    rng = random.Random(f"{int(seed or 0)}:{archetype}:{loop_type}:genre-contract")
    page_genre_by_archetype = {
        "browser_game": "arcade_microgame",
        "quiz_game": "arcade_microgame",
        "saas_workspace": "app_workspace",
        "commerce_workspace": "product_storefront",
        "interactive_instrument": "creative_tool",
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
        "motion_language": rng.choice(MOTION_LANGUAGES),
        "instruction_policy": instruction_policy,
        "chrome_policy": "minimal_functional",
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


def _library_profile_for_format(rng: random.Random, format_category: str, format_id: str, mechanic: str) -> str:
    physics_formats = {
        "breakout_paddle",
        "pinball_table",
        "basketball_arcade",
        "fishing_timing",
        "whack_a_target",
    }
    if format_id in physics_formats:
        return "matter_physics_game"
    if format_category in {"platformer", "snake_game", "microgame"}:
        return rng.choice(["ndw_canvas_game_loop", "ndw_audio_particles", "dom_css_state_machine"])
    if format_category in {"tic_tac_toe", "quiz_game", "memory_match", "word_game"}:
        return rng.choice(["dom_css_state_machine", "gsap_state_transition", "alpine_ui_state", "ndw_audio_particles"])
    if "map" in format_id or "orbit" in mechanic:
        return rng.choice(["three_orbit_scene", "three_bloom_scene", "ndw_canvas_game_loop"])
    if format_category in {"saas_replica", "commerce_or_booking_flow", "product_or_storefront"}:
        return "alpine_ui_state"
    if format_category in {"creative_tool", "simulation", "interactive_instrument"}:
        return rng.choice(["ndw_canvas_game_loop", "gsap_timeline_dom", "three_orbit_scene", "ndw_audio_particles"])
    return rng.choice(LIBRARY_PROFILES)


def _retention_contract_for_format(format_category: str, format_id: str) -> Dict[str, str]:
    if format_category in {"platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game", "microgame"}:
        return {
            "entry": "Start immediately or with one obvious Play button. No fake workspace, protocol, calibration, or terminal wrapper.",
            "loop_length": "A satisfying attempt should take 20-60 seconds.",
            "reward": "Show score plus at least one meta-reward such as combo, streak, best score, tickets, medals, lives, level, or unlock.",
            "copy": "Use a plain recognizable game title and a 3-7 word control cue.",
            "feedback": "Every input should cause visible motion, collision, progress, soundless juice, or score/state feedback.",
        }
    if format_category == "product_or_storefront":
        return {
            "entry": "Open with a complete product hero: product image/visual, name, price or plan, benefits/specs, variant selector, and primary buy/reserve/add-to-cart action.",
            "loop_length": "The first commerce payoff should be reachable in one click: selected variant, cart drawer, checkout summary, receipt, or reserved ticket.",
            "reward": "Show a cart/checkout/receipt/selected-plan state plus stock/drop/timer/social-proof feedback when compatible.",
            "copy": "Use normal ecommerce words: product, price, size, color, plan, cart, checkout, reserve, buy, compare.",
            "feedback": "Variant, quantity, plan, or add-to-cart actions must visibly update the product preview and checkout/cart state.",
        }
    if format_category in {"saas_replica", "commerce_or_booking_flow", "data_investigation", "fake_os_app"}:
        return {
            "entry": "Open with sample records/items already loaded. No blank dashboard or empty table as the first view.",
            "loop_length": "The first useful result should be reachable in one click or one edit.",
            "reward": "Show a saved state, selected record, receipt, itinerary, comparison, triage result, or configured summary.",
            "copy": "Use normal app language and concrete domain nouns; avoid sci-fi labels unless the domain is actually fictional.",
            "feedback": "Search, filter, select, create, save, or configure actions must visibly change data and status.",
        }
    if format_category in {"creative_tool", "interactive_instrument", "simulation"}:
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
