from __future__ import annotations

from typing import Any, Dict, List


FORMAT_PATTERN_GROUPS = {
    "game": [
        "game_stage",
        "scoreboard",
        "restart_button",
        "keyboard_touch_controls",
        "instant_start_or_one_play_button",
        "combo_or_streak",
        "meta_reward",
    ],
    "quiz": ["question_card", "answer_options", "scoreboard", "result_panel", "restart_button", "instant_start_or_one_play_button"],
    "app": ["preloaded_sample_records", "record_list", "filter_bar", "detail_panel", "one_click_demo_action", "save_action", "status_feedback"],
    "commerce": ["preselected_starter_option", "catalog_cards", "configuration_form", "cart_summary", "checkout_state", "status_feedback"],
    "product": ["product_hero", "price_or_plan", "variant_selector", "benefit_list", "cart_or_checkout_summary", "primary_buy_action"],
    "creative_tool": ["instant_preview", "tool_palette", "canvas_or_preview", "property_controls", "randomize_or_sample_action", "export_or_save_action"],
    "simulation": ["preloaded_example_state", "system_stage", "parameter_controls", "result_readout", "reset_button"],
    "investigation": ["evidence_list", "filter_or_sort_controls", "comparison_panel", "saved_findings"],
}


VARIANT_TASK_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "snake_grid": {
        "format": "snake_game",
        "user_goal": "Steer the snake, collect food, grow longer, and avoid collision.",
        "domain_objects": ["snake", "food", "grid", "wall", "score"],
        "state_variables": ["snakeBody", "foodPosition", "direction", "score", "gameOver"],
        "completion_condition": "game over after collision or a target score is reached",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "breakout_paddle": {
        "format": "breakout_game",
        "user_goal": "Move the paddle to bounce the ball and break every brick.",
        "domain_objects": ["paddle", "ball", "bricks", "lives", "score"],
        "state_variables": ["paddleX", "ball", "bricksRemaining", "lives", "score"],
        "completion_condition": "all bricks are cleared or lives reach zero",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "tile_merge_2048": {
        "format": "2048_game",
        "user_goal": "Slide and merge tiles to reach the target tile.",
        "domain_objects": ["number_tiles", "grid", "score", "next_move"],
        "state_variables": ["tiles", "score", "moves", "gameOver", "bestTile"],
        "completion_condition": "target tile reached or no moves remain",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "memory_match": {
        "format": "memory_match_game",
        "user_goal": "Flip cards and match every pair with as few turns as possible.",
        "domain_objects": ["cards", "pairs", "turns", "matches"],
        "state_variables": ["flippedCards", "matchedPairs", "turnCount", "complete"],
        "completion_condition": "all pairs are matched",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["quiz"],
    },
    "trivia_quiz": {
        "format": "trivia_quiz",
        "user_goal": "Answer questions and see a final score.",
        "domain_objects": ["questions", "answers", "score", "result"],
        "state_variables": ["currentQuestion", "selectedAnswer", "score", "finished"],
        "completion_condition": "all questions answered and final result shown",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["quiz"],
    },
    "invoice_builder": {
        "format": "invoice_builder",
        "user_goal": "Create a valid invoice with line items, totals, and export-ready preview.",
        "domain_objects": ["client", "line_item", "quantity", "rate", "tax", "due_date"],
        "state_variables": ["client", "items", "subtotal", "tax", "total", "exportReady"],
        "completion_condition": "invoice preview is valid and export action is enabled",
        "allowed_patterns": ["form", "editable_table", "summary_card", "preview_panel", "save_action"],
    },
    "travel_booking": {
        "format": "travel_booking_flow",
        "user_goal": "Choose itinerary options and reserve a coherent trip package.",
        "domain_objects": ["destination", "date", "flight", "hotel", "traveler", "price"],
        "state_variables": ["destination", "dateRange", "selectedFlight", "selectedHotel", "total", "reserved"],
        "completion_condition": "reservation summary is shown with selected trip details",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["commerce"],
    },
    "sales_tracker": {
        "format": "sales_tracker",
        "user_goal": "Filter leads, move deals between stages, and save a pipeline update.",
        "domain_objects": ["lead", "deal", "stage", "owner", "value"],
        "state_variables": ["leads", "selectedLead", "stage", "filters", "saved"],
        "completion_condition": "at least one lead is updated and saved",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["app"],
    },
    "task_board": {
        "format": "task_board",
        "user_goal": "Organize tasks across columns and save a project board state.",
        "domain_objects": ["task", "column", "assignee", "status"],
        "state_variables": ["tasks", "columns", "selectedTask", "filters", "saved"],
        "completion_condition": "task movement or status update is saved",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["app"],
    },
    "room_layout_builder": {
        "format": "room_layout_builder",
        "user_goal": "Arrange furniture into a room layout and preview the final plan.",
        "domain_objects": ["room", "furniture", "grid", "layout", "preview"],
        "state_variables": ["placedItems", "selectedFurniture", "roomSize", "layoutValid"],
        "completion_condition": "a valid room layout preview is shown",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["creative_tool"],
    },
    "music_step_sequencer": {
        "format": "music_step_sequencer",
        "user_goal": "Toggle steps, change tempo, and play a repeating beat pattern.",
        "domain_objects": ["steps", "tracks", "tempo", "pattern", "playhead"],
        "state_variables": ["steps", "tempo", "playing", "playhead", "patternName"],
        "completion_condition": "a named pattern is playing or saved",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["creative_tool"],
    },
    "weather_mixer": {
        "format": "weather_mixer",
        "user_goal": "Adjust weather factors and read the resulting forecast state.",
        "domain_objects": ["temperature", "wind", "humidity", "clouds", "forecast"],
        "state_variables": ["temperature", "wind", "humidity", "forecast", "severity"],
        "completion_condition": "forecast readout updates from selected weather factors",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["simulation"],
    },
    "record_investigation": {
        "format": "record_investigation",
        "user_goal": "Filter records, compare evidence, and save a finding.",
        "domain_objects": ["record", "evidence", "tag", "finding", "case"],
        "state_variables": ["records", "filters", "selectedEvidence", "findings", "saved"],
        "completion_condition": "at least one finding is saved from selected evidence",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["investigation"],
    },
    "sudoku_grid": {
        "format": "sudoku_puzzle",
        "user_goal": "Fill the grid with numbers 1-9 so each row, column, and box contains all digits.",
        "domain_objects": ["grid", "number", "row", "column", "box"],
        "state_variables": ["cells", "selectedCell", "hints", "complete", "errors"],
        "completion_condition": "all 81 cells are filled correctly",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "connect_four": {
        "format": "connect_four_game",
        "user_goal": "Drop discs to connect four in a row before your opponent does.",
        "domain_objects": ["disc", "column", "row", "board", "player"],
        "state_variables": ["board", "currentPlayer", "winner", "columnHeights"],
        "completion_condition": "one player connects four discs",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "solitaire_card": {
        "format": "solitaire_game",
        "user_goal": "Sort all cards into foundation stacks by suit.",
        "domain_objects": ["card", "suit", "stack", "tableau", "foundation"],
        "state_variables": ["deck", "tableau", "foundations", "drawPile"],
        "completion_condition": "all cards are in foundation stacks",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "pong_clone": {
        "format": "pong_game",
        "user_goal": "Bounce the ball past your opponent to score points.",
        "domain_objects": ["paddle", "ball", "score", "court"],
        "state_variables": ["paddle1", "paddle2", "ball", "score1", "score2"],
        "completion_condition": "first player reaches target score",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "flappy_bird": {
        "format": "flappy_bird_game",
        "user_goal": "Tap to flap and dodge pipes for as long as possible.",
        "domain_objects": ["bird", "pipe", "gap", "score", "ground"],
        "state_variables": ["birdY", "velocity", "pipes", "score", "alive"],
        "completion_condition": "game ends on collision",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "darts_scoring": {
        "format": "darts_game",
        "user_goal": "Throw darts at the target to score the highest points.",
        "domain_objects": ["dart", "board", "bullseye", "score", "round"],
        "state_variables": ["throws", "totalScore", "rounds", "highScore"],
        "completion_condition": "all rounds are completed",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "bowling_arcade": {
        "format": "bowling_game",
        "user_goal": "Roll the ball to knock down all ten pins.",
        "domain_objects": ["ball", "pin", "lane", "frame", "score"],
        "state_variables": ["pins", "ballPosition", "frames", "totalScore"],
        "completion_condition": "all ten frames are completed",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
    "air_hockey": {
        "format": "air_hockey_game",
        "user_goal": "Hit the puck into your opponent's goal to score.",
        "domain_objects": ["puck", "striker", "goal", "table", "score"],
        "state_variables": ["puck", "playerStriker", "aiStriker", "playerScore", "aiScore"],
        "completion_condition": "first player reaches target score",
        "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
    },
}


def _category_for_variant(activity_variant: str, activity_type: str) -> str:
    if activity_type in {"platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game", "microgame"}:
        return "game"
    if activity_type in {"saas_replica", "fake_os_app"}:
        return "app"
    if activity_type == "product_or_storefront":
        return "product"
    if activity_type == "commerce_or_booking_flow":
        return "commerce"
    if activity_type in {"creative_tool", "interactive_instrument"}:
        return "creative_tool"
    if activity_type == "simulation":
        return "simulation"
    if activity_type in {"data_investigation", "narrative_explorer", "puzzle_box"}:
        return "investigation"
    if "booking" in activity_variant or "ordering" in activity_variant:
        return "commerce"
    return "app"


def _fallback_task(activity_variant: str, activity_type: str) -> Dict[str, Any]:
    category = _category_for_variant(activity_variant, activity_type)
    readable = activity_variant.replace("_", " ")
    if category == "game":
        return {
            "format": activity_variant,
            "user_goal": f"Play the {readable} format until a score, win state, or failure state is reached.",
            "domain_objects": ["player", "target", "score", "timer", "streak", "reward", "restart"],
            "state_variables": ["score", "activeTarget", "timer", "streak", "bestScore", "complete", "failed"],
            "completion_condition": "score/result panel shows a win, loss, completion, or best score",
            "allowed_patterns": FORMAT_PATTERN_GROUPS["game"],
        }
    if category == "creative_tool":
        return {
            "format": activity_variant,
            "user_goal": f"Use the {readable} tool to create or preview a finished artifact.",
            "domain_objects": ["tool", "settings", "artifact", "preview"],
            "state_variables": ["settings", "selectedTool", "artifactState", "previewReady"],
            "completion_condition": "a created artifact or preview is visible",
            "allowed_patterns": FORMAT_PATTERN_GROUPS["creative_tool"],
        }
    if category == "simulation":
        return {
            "format": activity_variant,
            "user_goal": f"Adjust the {readable} system and interpret the resulting state.",
            "domain_objects": ["system", "parameters", "result", "reset"],
            "state_variables": ["parameters", "resultState", "severity", "resetCount"],
            "completion_condition": "result readout changes from selected parameters",
            "allowed_patterns": FORMAT_PATTERN_GROUPS["simulation"],
        }
    if category == "product":
        return {
            "format": activity_variant,
            "user_goal": f"Inspect the {readable}, choose an option, and see a cart, reservation, or checkout summary.",
            "domain_objects": ["product", "price", "variant", "benefit", "cart", "checkout"],
            "state_variables": ["selectedVariant", "quantity", "cartItems", "total", "checkoutReady"],
            "completion_condition": "selected product option appears in cart, checkout, receipt, reservation, or comparison summary",
            "allowed_patterns": FORMAT_PATTERN_GROUPS["product"],
        }
    return {
        "format": activity_variant,
        "user_goal": f"Use the {readable} workflow to select, configure, save, or compare domain items.",
        "domain_objects": ["record", "item", "filter", "selection", "result"],
        "state_variables": ["records", "filters", "selectedItems", "saved", "result"],
        "completion_condition": "a selected, saved, configured, or compared result is visible",
        "allowed_patterns": FORMAT_PATTERN_GROUPS.get(category, FORMAT_PATTERN_GROUPS["app"]),
    }


def task_contract_for_variant(activity_variant: str, activity_type: str) -> Dict[str, Any]:
    base = dict(VARIANT_TASK_OVERRIDES.get(activity_variant) or _fallback_task(activity_variant, activity_type))
    controls = [
        {
            "label": _primary_action_label(base["format"]),
            "type": "button_or_direct_input",
            "must_change_state": base["state_variables"][:2],
        },
        {
            "label": "Reset or edit",
            "type": "button",
            "must_change_state": [base["state_variables"][-1]],
        },
    ]
    if "filter" in " ".join(base["domain_objects"]).lower() or "records" in base["state_variables"]:
        controls.insert(
            0,
            {"label": "Filter/search", "type": "input", "must_change_state": ["filters", "selectedItems"]},
        )
    return {
        **base,
        "controls": controls,
        "retention_contract": _retention_contract_for_category(_category_for_variant(activity_variant, activity_type)),
        "error_states": _error_states_for(base["format"]),
        "visual_budget": {
            "ambient_background": "optional_subtle",
            "motion_only_for": ["state feedback", "progress", "success", "failure", "focus"],
        },
    }


def _error_states_for(format_name: str) -> List[str]:
    if "invoice" in format_name:
        return ["missing client", "empty line item", "invalid amount"]
    if "booking" in format_name or "ordering" in format_name:
        return ["missing date", "no option selected", "invalid quantity"]
    if "game" in format_name or format_name in {"snake_grid", "breakout_game", "2048_game"}:
        return ["game over", "invalid move", "restart requested"]
    return ["missing required selection", "invalid state", "reset requested"]


def _primary_action_label(format_name: str) -> str:
    lowered = format_name.lower()
    if any(term in lowered for term in ["game", "snake", "breakout", "2048", "runner", "rhythm", "whack", "pinball", "asteroids", "maze", "basketball", "pong", "flappy", "darts", "bowling", "hockey", "sudoku", "connect", "solitaire"]):
        return "Play / move"
    if "quiz" in lowered or "word" in lowered or "memory" in lowered:
        return "Answer / match"
    if "booking" in lowered or "ordering" in lowered or "marketplace" in lowered:
        return "Select option"
    if any(term in lowered for term in ["product", "sneaker", "skincare", "coffee", "furniture", "course", "pricing", "template", "ticket", "drop"]):
        return "Add / reserve"
    if "builder" in lowered or "studio" in lowered or "generator" in lowered or "mixer" in lowered:
        return "Create preview"
    return "Select / save"


def _retention_contract_for_category(category: str) -> Dict[str, str]:
    if category == "game":
        return {
            "entry": "Playable immediately or after one obvious Play action.",
            "meta_reward": "Track score plus streak, combo, best score, lives, level, tickets, or medals.",
            "copy": "Plain title plus a short control cue; no tutorial panel.",
            "empty_state": "Never show an empty playfield without a target, player, score, and restart.",
        }
    if category in {"app", "commerce", "investigation"}:
        return {
            "entry": "Preload realistic sample records/items/options.",
            "meta_reward": "Show a saved result, receipt, itinerary, selected record, finding, or configured summary.",
            "copy": "Use plain app labels and domain nouns, not sci-fi system jargon.",
            "empty_state": "No blank tables, empty slots, or placeholder-only workflows.",
        }
    if category == "product":
        return {
            "entry": "Show product hero, price/plan, variants, and a primary buy/reserve action immediately.",
            "meta_reward": "Show cart drawer, checkout summary, receipt, reservation, selected plan, stock timer, or comparison result.",
            "copy": "Use normal ecommerce language. No fake dashboard or abstract system labels.",
            "empty_state": "Never open with no product image/visual, no price, or no selectable option.",
        }
    if category in {"creative_tool", "simulation"}:
        return {
            "entry": "Show a starter artifact/preview before interaction.",
            "meta_reward": "Include Randomize, Remix, Save, Export, Capture, or Reset.",
            "copy": "Keep labels attached to controls; avoid explanatory paragraphs.",
            "empty_state": "No empty canvas unless the first action visibly creates something.",
        }
    return {
        "entry": "Make the first action obvious.",
        "meta_reward": "Show result, progress, saved state, or score.",
        "copy": "Use plain human-facing copy.",
        "empty_state": "Avoid empty first screens.",
    }
