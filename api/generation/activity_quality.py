from __future__ import annotations

import re
from typing import Any, Dict, List


ACTIVITY_SCORE_THRESHOLD = 75

_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_SCRIPT_RE = re.compile(r"<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>", re.IGNORECASE)
_RANGE_RE = re.compile(r"<input\b[^>]*type=['\"]?range", re.IGNORECASE)
_CONTROL_RE = re.compile(r"<(?:button|input|select|textarea)\b|role=['\"](?:button|slider|tab)['\"]", re.IGNORECASE)
_EVENT_RE = re.compile(
    r"(addEventListener\(\s*['\"](?:click|input|change|pointer|pointermove|pointerdown|mousemove|touch|keydown|keyup|submit|drag|drop)"
    r"|onclick=|oninput=|onchange=|onsubmit=)",
    re.IGNORECASE,
)
_STATE_RE = re.compile(
    r"(let|const|var)\s+(?:state|score|progress|selected|items|inventory|cart|records|unlocked)\b"
    r"|state\s*=|score|progress|selected|unlocked|completed|dataset\.|classList\.|textContent|innerText|appendChild|removeChild|setAttribute",
    re.IGNORECASE,
)
_PAYOFF_RE = re.compile(
    r"\b(score|points?|correct|incorrect|complete|completed|clear|cleared|lost|game over|unlock|unlocked|saved|result|output|created|cart|booking|checkout|report|rank|level|win|winner|finish|mission|collection|selected|configured|filtered|matched|streak|lives|timer)\b",
    re.IGNORECASE,
)
_TASK_RE = re.compile(
    r"\b(answer|guess|match|collect|sort|assemble|draw|paint|filter|search|configure|navigate|unlock|classify|compose|inspect|repair|trade|book|select|create|save|submit|move|shoot|steer|jump|restart|reset)\b",
    re.IGNORECASE,
)
_VISUAL_ONLY_RE = re.compile(
    r"\b(pulse|glow|shimmer|sparkle|particles?|ambient|calibrate|resonance|frequency|density)\b",
    re.IGNORECASE,
)
_ABSTRACT_GLUE_RE = re.compile(
    r"\b(migration|ladder|signal|archive|protocol|registry|relay|transmission|hidden|ritual|echo)\b",
    re.IGNORECASE,
)
_HIDDEN_REVEAL_RE = re.compile(r"\b(hidden|reveal|unlock|decode|transmission|signal|archive|fragment)\b", re.IGNORECASE)
_EMPTY_START_RE = re.compile(r"\b(empty|blank|placeholder|start from scratch|no items|0 items|slot\s+\d+)\b", re.IGNORECASE)


def _extract_html(doc: Dict[str, Any]) -> str:
    html = doc.get("html") if isinstance(doc, dict) else ""
    return html if isinstance(html, str) else ""


def _visible_text(html: str) -> str:
    stripped = _STYLE_SCRIPT_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", stripped)).strip().lower()


def _activity_contract(plan: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    contract = plan.get("activity_contract")
    return contract if isinstance(contract, dict) else {}


def _task_contract(plan: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    contract = plan.get("task_contract")
    return contract if isinstance(contract, dict) else {}


def _has_any_term(text: str, values: List[Any]) -> bool:
    return any(str(value or "").strip().lower() in text for value in values if str(value or "").strip())


def score_activity_depth(doc: Dict[str, Any], plan: Dict[str, Any] | None = None) -> Dict[str, Any]:
    html = _extract_html(doc)
    text = _visible_text(html)
    contract = _activity_contract(plan)
    task_contract = _task_contract(plan)
    activity_type = str((plan or {}).get("activity_type") or contract.get("activity_type") or "")
    activity_variant = str(contract.get("activity_variant") or "")
    tags: List[str] = []
    notes: List[str] = []
    score = 100

    controls = len(_CONTROL_RE.findall(html))
    ranges = len(_RANGE_RE.findall(html))
    has_events = bool(_EVENT_RE.search(html))
    has_state = bool(_STATE_RE.search(html))
    has_task_language = bool(_TASK_RE.search(text)) or bool(contract.get("activity_goal"))
    has_payoff = bool(_PAYOFF_RE.search(text)) or bool(contract.get("payoff"))
    task_controls = task_contract.get("controls") if isinstance(task_contract.get("controls"), list) else []
    task_state_variables = task_contract.get("state_variables") if isinstance(task_contract.get("state_variables"), list) else []
    task_domain_objects = task_contract.get("domain_objects") if isinstance(task_contract.get("domain_objects"), list) else []
    task_completion = str(task_contract.get("completion_condition") or "").strip()

    if controls and ranges == controls and activity_type not in {"interactive_instrument", "simulation"}:
        tags.append("slider_only_activity")
        notes.append("all controls are sliders, but the selected activity type should require a richer mechanic")
        score -= 28
    elif ranges >= 3 and activity_type not in {"interactive_instrument", "simulation"}:
        tags.append("slider_dominant_activity")
        notes.append("sliders dominate the interaction surface outside an instrument/simulation activity")
        score -= 16

    if controls > 0 and not has_events:
        tags.append("dead_controls_risk")
        notes.append("controls exist without obvious event handlers")
        score -= 22

    if not has_state:
        tags.append("no_persistent_state")
        notes.append("no obvious progress, selection, output, score, cart, record, or unlocked state")
        score -= 18

    if not has_task_language:
        tags.append("no_concrete_task")
        notes.append("page does not expose a concrete visitor task")
        score -= 14

    if not has_payoff:
        tags.append("no_payoff")
        notes.append("page does not expose a result, completion, output, score, saved state, or reveal payoff")
        score -= 14

    if task_contract:
        if len(task_domain_objects) < 2:
            tags.append("task_objects_missing")
            notes.append("task_contract does not define enough domain objects")
            score -= 8
        elif not _has_any_term(text, task_domain_objects):
            tags.append("domain_objects_not_visible")
            notes.append("generated UI does not visibly expose task domain objects")
            score -= 8

        if len(task_state_variables) < 2:
            tags.append("state_model_missing")
            notes.append("task_contract does not define enough state variables")
            score -= 8
        else:
            state_hits = sum(1 for value in task_state_variables if str(value or "").lower() in html.lower())
            if state_hits == 0:
                tags.append("state_variables_not_implemented")
                notes.append("generated code does not reference task_contract state variables")
                score -= 12

        if not task_completion:
            tags.append("completion_condition_missing")
            notes.append("task_contract does not define a completion condition")
            score -= 10
        elif not (_PAYOFF_RE.search(text) or re.search(r"\b(done|finished|complete|saved|reserved|export|win|loss|result|preview|receipt)\b", text, re.IGNORECASE)):
            tags.append("completion_condition_not_visible")
            notes.append("completion condition is not visible as result/status/score/preview")
            score -= 10

        controls_with_state = 0
        for item in task_controls:
            if not isinstance(item, dict):
                continue
            changed = item.get("must_change_state")
            if isinstance(changed, list) and changed:
                controls_with_state += 1
        if task_controls and controls_with_state < len(task_controls):
            tags.append("control_state_contract_missing")
            notes.append("one or more planned controls do not declare must_change_state")
            score -= 10
        if task_controls and controls == 0:
            tags.append("planned_controls_not_rendered")
            notes.append("task_contract declares controls but generated UI has no controls")
            score -= 14
    elif plan:
        tags.append("task_contract_missing")
        notes.append("plan lacks task_contract for goal/domain/state/control validation")
        score -= 12

    if _VISUAL_ONLY_RE.search(text) and not (_PAYOFF_RE.search(text) or "appendChild" in html or "classList" in html):
        tags.append("visual_effect_only_risk")
        notes.append("copy suggests controls mainly tune visual effects without meaningful outcome")
        score -= 10

    if activity_type == "saas_replica":
        if not re.search(r"\b(search|filter|record|table|card|workspace|project|create|save|status|team|customer|invoice|ticket)\b", text, re.IGNORECASE):
            tags.append("saas_workflow_missing")
            notes.append("saas_replica lacks an app-like workflow vocabulary or data surface")
            score -= 18

    if activity_type == "product_or_storefront":
        if not re.search(r"\b(product|price|plan|cart|checkout|buy|reserve|order|size|color|variant|quantity|ticket|stock|drop|compare)\b", text, re.IGNORECASE):
            tags.append("product_contract_missing")
            notes.append("product_or_storefront lacks product, pricing, options, or checkout vocabulary")
            score -= 20
        if not re.search(r"\b(cart|checkout|receipt|reserved|selected|plan|total|order|claim|buy|add)\b", text, re.IGNORECASE):
            tags.append("product_payoff_missing")
            notes.append("product_or_storefront lacks visible commerce payoff state")
            score -= 12

    if activity_type in {"creative_tool", "simulation", "product_or_storefront", "saas_replica", "commerce_or_booking_flow"} and _EMPTY_START_RE.search(text):
        tags.append("blank_stage_first_paint")
        notes.append("visible copy suggests the first screen starts blank or placeholder-like")
        score -= 14

    if activity_type in {"microgame", "platformer", "snake_game", "tic_tac_toe", "quiz_game", "memory_match", "word_game"}:
        if not re.search(r"\b(score|level|collect|timer|win|complete|restart|reset|mission|target|lives|streak|lost|cleared|mine-count)\b", text + " " + html, re.IGNORECASE):
            tags.append("game_goal_missing")
            notes.append("game activity lacks score, level, target, timer, completion, or replay signal")
            score -= 18

    variant_patterns = {
        "platformer_collectathon": r"\b(platform|jump|coin|collect|level|enemy|obstacle|ground|score)\b",
        "snake_grid": r"\b(snake|food|grow|grid|collision|score)\b",
        "tic_tac_toe": r"\b(tic|toe|square|board|turn|row|winner|opponent)\b",
        "trivia_quiz": r"\b(quiz|question|answer|correct|incorrect|score|option)\b",
        "memory_match": r"\b(memory|match|pair|card|flip|turn|score)\b",
        "word_guess": r"\b(word|guess|letter|attempt|solve|hint|score)\b",
        "breakout_paddle": r"\b(breakout|paddle|brick|ball|bounce|lives|score)\b",
        "minesweeper_grid": r"\b(minesweeper|mine|flag|tile|safe|grid|clear)\b",
        "tile_merge_2048": r"\b(2048|merge|tile|slide|number|score)\b",
        "endless_runner": r"\b(run|runner|jump|duck|obstacle|distance|score)\b",
        "rhythm_tap": r"\b(rhythm|beat|tap|combo|timing|score)\b",
        "whack_a_target": r"\b(whack|target|hit|timer|streak|score)\b",
        "sliding_tile_puzzle": r"\b(sliding|tile|puzzle|move|solve|order)\b",
        "tower_defense_lite": r"\b(tower|defense|wave|enemy|path|base)\b",
        "pinball_table": r"\b(pinball|flipper|ball|bumper|launch|score)\b",
        "asteroids_shooter": r"\b(asteroid|ship|thrust|shoot|laser|score)\b",
        "maze_escape": r"\b(maze|exit|wall|trap|key|escape)\b",
        "reaction_timer": r"\b(reaction|timer|signal|fast|milliseconds|score)\b",
        "fishing_timing": r"\b(fishing|cast|reel|catch|bite|timing)\b",
        "basketball_arcade": r"\b(basketball|hoop|shot|arc|power|score)\b",
        "card_sort_strategy": r"\b(card|hand|draw|play|rank|score)\b",
        "typing_race": r"\b(typing|race|words|accuracy|wpm|timer)\b",
        "kanban_workspace": r"\b(kanban|board|task|column|card|status)\b",
        "crm_pipeline": r"\b(crm|lead|customer|pipeline|deal|stage)\b",
        "invoice_builder": r"\b(invoice|line item|subtotal|tax|total|client)\b",
        "analytics_explorer": r"\b(analytics|chart|filter|segment|metric|report)\b",
        "calendar_scheduler": r"\b(calendar|schedule|event|time slot|meeting|date)\b",
        "inventory_manager": r"\b(inventory|stock|sku|warehouse|quantity|reorder)\b",
        "travel_booking": r"\b(travel|booking|flight|hotel|itinerary|reserve)\b",
        "restaurant_ordering": r"\b(menu|order|cart|table|checkout|restaurant)\b",
        "marketplace_comparison": r"\b(compare|marketplace|price|vendor|product|shortlist)\b",
        "subscription_configurator": r"\b(plan|subscription|tier|billing|feature|checkout)\b",
        "product_detail_page": r"\b(product|price|variant|cart|buy|details|specs)\b",
        "sneaker_drop_page": r"\b(sneaker|drop|size|stock|claim|cart|price)\b",
        "skincare_product_page": r"\b(skincare|serum|cream|skin|ingredient|price|cart)\b",
        "coffee_subscription_page": r"\b(coffee|subscription|roast|bag|delivery|plan|cart)\b",
        "furniture_product_configurator": r"\b(furniture|sofa|chair|fabric|finish|room|cart|price)\b",
        "course_sales_page": r"\b(course|lesson|module|enroll|price|curriculum|checkout)\b",
        "app_pricing_page": r"\b(pricing|plan|tier|feature|billing|upgrade|checkout)\b",
        "digital_template_store": r"\b(template|download|license|price|preview|cart|checkout)\b",
        "event_ticket_checkout": r"\b(ticket|event|seat|date|venue|checkout|reserve)\b",
        "marketplace_listing_page": r"\b(listing|seller|price|product|compare|cart|marketplace)\b",
        "limited_drop_countdown": r"\b(drop|countdown|stock|claim|reserve|cart|limited)\b",
        "portfolio_builder": r"\b(portfolio|project|case study|layout|publish|preview)\b",
        "resume_screener": r"\b(resume|candidate|screen|skill|shortlist|score)\b",
        "support_triage": r"\b(ticket|priority|support|triage|queue|assign)\b",
        "habit_tracker": r"\b(habit|streak|day|check in|progress|goal)\b",
        "budget_planner": r"\b(budget|expense|income|savings|category|total)\b",
        "recipe_planner": r"\b(recipe|ingredient|meal|serving|cook|plan)\b",
        "drawing_studio": r"\b(draw|brush|canvas|stroke|palette|export)\b",
        "music_step_sequencer": r"\b(step|sequencer|beat|tempo|track|pattern)\b",
        "map_route_planner": r"\b(map|route|waypoint|distance|path|destination)\b",
        "color_palette_mixer": r"\b(color|palette|swatch|mix|hue|contrast)\b",
        "poster_generator": r"\b(poster|layout|headline|print|composition|export)\b",
        "room_layout_builder": r"\b(room|furniture|layout|floor|place|arrange)\b",
        "avatar_customizer": r"\b(avatar|hair|outfit|face|customize|preview)\b",
        "plant_growth_simulator": r"\b(plant|growth|water|soil|sun|garden)\b",
        "weather_mixer": r"\b(weather|cloud|rain|wind|temperature|forecast)\b",
        "data_story_scrubber": r"\b(data|timeline|scrub|story|compare|insight)\b",
        "record_investigation": r"\b(record|investigation|case|evidence|filter|select|save)\b",
        "map_explorer": r"\b(map|route|place|waypoint|region|navigate|explore)\b",
        "timeline_compare": r"\b(timeline|compare|event|before|after|scrub|date)\b",
        "case_file_sorter": r"\b(case|file|sort|evidence|folder|clue|record)\b",
        "operating_panel": r"\b(panel|operate|control|system|setting|apply|status)\b",
    }
    pattern = variant_patterns.get(activity_variant)
    variant_visible = bool(pattern and re.search(pattern, text, re.IGNORECASE))
    if pattern and not variant_visible:
        tags.append("activity_variant_mismatch")
        notes.append(f"activity_variant {activity_variant} is not visibly represented")
        score -= 18
        if _ABSTRACT_GLUE_RE.search(text):
            tags.append("poetic_renaming_of_known_format")
            notes.append("abstract metaphor language appears to replace the recognizable format name")
            score -= 10

    semantic = (plan or {}).get("semantic_anchors") if isinstance(plan, dict) else None
    if isinstance(semantic, dict) and semantic:
        anchor_mentions = sum(1 for value in semantic.values() if str(value).lower() in text)
        if anchor_mentions >= 3 and pattern and not variant_visible:
            tags.append("semantic_anchor_overrides_activity")
            notes.append("semantic anchors are more visible than the selected concrete activity format")
            score -= 8

    reveal_terms = len(_HIDDEN_REVEAL_RE.findall(text))
    reveal_friendly = activity_variant in {"word_guess", "case_file_sorter", "record_investigation", "timeline_compare"}
    if reveal_terms >= 5 and not reveal_friendly:
        tags.append("abstract_hidden_reveal_loop")
        notes.append("hidden/reveal/archive language dominates a format that should expose a concrete activity")
        score -= 8

    if activity_variant and not pattern:
        tags.append("format_contract_missing")
        notes.append(f"no activity-quality pattern exists for activity_variant {activity_variant}")
        score -= 6

    if activity_type == "platformer":
        if not re.search(r"\b(jump|platform|coin|collect|level|enemy|obstacle|ground)\b", text, re.IGNORECASE):
            tags.append("platformer_mechanic_missing")
            notes.append("platformer lacks jump/platform/collect/obstacle vocabulary")
            score -= 18

    if activity_type == "snake_game":
        if not re.search(r"\b(snake|food|grow|grid|collision|score)\b", text, re.IGNORECASE):
            tags.append("snake_mechanic_missing")
            notes.append("snake_game lacks snake/food/grow/grid/collision/score vocabulary")
            score -= 18

    if activity_type == "tic_tac_toe":
        if not re.search(r"\b(tic|toe|square|board|turn|row|winner|opponent)\b", text, re.IGNORECASE):
            tags.append("tic_tac_toe_mechanic_missing")
            notes.append("tic_tac_toe lacks board/turn/winner/opponent vocabulary")
            score -= 18

    if activity_type == "quiz_game":
        if not re.search(r"\b(quiz|question|answer|correct|incorrect|score|option)\b", text, re.IGNORECASE):
            tags.append("quiz_mechanic_missing")
            notes.append("quiz_game lacks question/answer/correct/score vocabulary")
            score -= 18

    if activity_type == "memory_match":
        if not re.search(r"\b(memory|match|pair|card|flip|turn|score)\b", text, re.IGNORECASE):
            tags.append("memory_match_mechanic_missing")
            notes.append("memory_match lacks card/flip/pair/match vocabulary")
            score -= 18

    if activity_type == "word_game":
        if not re.search(r"\b(word|guess|letter|attempt|solve|hint|score)\b", text, re.IGNORECASE):
            tags.append("word_game_mechanic_missing")
            notes.append("word_game lacks word/guess/letter/attempt vocabulary")
            score -= 18

    return {
        "score": max(0, min(100, score)),
        "threshold": ACTIVITY_SCORE_THRESHOLD,
        "passes": score >= ACTIVITY_SCORE_THRESHOLD,
        "tags": sorted(set(tags)),
        "notes": notes,
        "metrics": {
            "activity_type": activity_type,
            "activity_variant": activity_variant,
            "control_count": controls,
            "range_control_count": ranges,
            "has_events": has_events,
            "has_state": has_state,
            "has_task_language": has_task_language,
            "has_payoff": has_payoff,
            "task_contract_present": bool(task_contract),
            "task_control_count": len(task_controls),
            "task_state_variable_count": len(task_state_variables),
            "task_domain_object_count": len(task_domain_objects),
        },
    }
