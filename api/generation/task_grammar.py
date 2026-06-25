from __future__ import annotations

from typing import Any, Dict, List

from data.load_variants import (
    FORMAT_PATTERN_GROUPS,
    VARIANT_TASK_OVERRIDES,
)


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
            "user_goal": f"Play with the {readable}, change its settings, and watch the scene respond.",
            "domain_objects": ["scene", "settings", "response", "reset"],
            "state_variables": ["settings", "sceneState", "intensity", "resetCount"],
            "completion_condition": "the visible scene changes from selected settings",
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
    payoff_scene = _payoff_scene_for(base["format"], activity_type)
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
        "payoff_scene": payoff_scene,
        "controls": controls,
        "retention_contract": _retention_contract_for_category(_category_for_variant(activity_variant, activity_type)),
        "error_states": _error_states_for(base["format"]),
        "visual_budget": {
            "ambient_background": "optional_subtle",
            "motion_only_for": ["state feedback", "progress", "success", "failure", "focus"],
        },
    }


def _payoff_scene_for(format_name: str, activity_type: str) -> Dict[str, str]:
    lowered = format_name.lower()
    if any(term in lowered for term in ["ordering", "restaurant", "delivery"]):
        return {
            "trigger": "after the user adds or places an order",
            "scene": "show a receipt plus an animated courier bike/car route moving toward a destination with ETA/status updates",
            "continue_action": "edit cart, track progress, or reorder",
        }
    if any(term in lowered for term in ["booking", "ticket", "travel", "event"]):
        return {
            "trigger": "after the user selects/reserves an option",
            "scene": "show a ticket/pass, itinerary or route timeline, confirmation code, and next-step status",
            "continue_action": "change option, compare another route, or reserve again",
        }
    if activity_type == "product_or_storefront" or any(term in lowered for term in ["product", "sneaker", "skincare", "coffee", "furniture", "pricing", "template", "drop"]):
        return {
            "trigger": "after variant selection or add-to-cart",
            "scene": "show selected configuration, cart drawer or checkout/receipt summary, total, and availability/state feedback",
            "continue_action": "adjust variant, compare, checkout, or reset selection",
        }
    if activity_type in {"platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game", "microgame"}:
        return {
            "trigger": "after a scored move, round, win, loss, or completion",
            "scene": "show score burst, result state, best score/progress, and restart/next-round affordance",
            "continue_action": "restart, beat score, next level, or replay",
        }
    if activity_type in {"saas_replica", "fake_os_app", "data_investigation"}:
        return {
            "trigger": "after select/filter/save/create action",
            "scene": "show changed record status, saved summary, generated report, or completed workflow result",
            "continue_action": "open another record, refine filter, or save another result",
        }
    if activity_type in {"creative_tool", "interactive_instrument", "simulation"}:
        return {
            "trigger": "after direct manipulation or parameter change",
            "scene": "show a finished preview/artifact, before-after comparison, capture/export state, or visible scene response",
            "continue_action": "remix, export, randomize, reset, or tune again",
        }
    return {
        "trigger": "after the primary action",
        "scene": "show a concrete result, progress state, saved state, created output, or completion moment",
        "continue_action": "try again, refine, compare, or reset",
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
