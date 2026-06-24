from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set


EXPERIENCE_SCORE_THRESHOLD = 75

EXPERIENCE_QUALITY_WEIGHTS = {
    "has_clear_premise": 10,
    "first_interaction_visible": 12,
    "primary_interaction_defined": 12,
    "meaningful_state_change": 15,
    "feedback_clarity": 12,
    "continue_reason_present": 10,
    "reset_or_replay_available": 6,
    "orientation_cues_present": 8,
    "interaction_not_decorative": 12,
    "mobile_interaction_supported": 8,
    "word_salad_risk_low": 5,
}

_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<(?:title|h1|h2)[^>]*>(.*?)</(?:title|h1|h2)>", re.IGNORECASE | re.DOTALL)
_CONTROL_RE = re.compile(r"(<button\b|<input\b|<select\b|<textarea\b|role=['\"](?:button|slider|tab)['\"])", re.IGNORECASE)
_EVENT_RE = re.compile(
    r"(addEventListener\(\s*['\"](?:click|input|change|pointer|pointermove|pointerdown|mousemove|touch|keydown|keyup|wheel|scroll)"
    r"|onclick=|oninput=|onchange=|requestAnimationFrame|canvas)",
    re.IGNORECASE,
)
_STATE_RE = re.compile(
    r"(let|const|var)\s+state\b|state\s*=|progress|score|count|unlocked|selected|current|dataset\.|classList\.|style\.|textContent|innerText|setAttribute",
    re.IGNORECASE,
)
_FEEDBACK_RE = re.compile(
    r"(textContent|innerText|classList\.|style\.|dataset\.|setAttribute|appendChild|animate\(|gsap\.|requestAnimationFrame|progress|meter|unlock|reveal)",
    re.IGNORECASE,
)
_PAYOFF_RE = re.compile(
    r"\b(score|result|receipt|cart|checkout|delivery|courier|eta|route|ticket|itinerary|saved|preview|export|report|win|loss|level|streak|complete|completed|configured|selected)\b",
    re.IGNORECASE,
)
_RESET_RE = re.compile(r"\b(reset|replay|restart|again|clear|new variant|shuffle)\b", re.IGNORECASE)
_MOBILE_RE = re.compile(r"(@media|touchstart|touchmove|pointerdown|pointermove|viewport|max-width|clamp\()", re.IGNORECASE)
_CUE_RE = re.compile(
    r"\b(start|drag|type|tap|click|hover|scroll|choose|select|press|move|steer|arrow|arrows|avoid|match|tune|scan|paint|scrub|zoom|reset|restart|add|reserve|checkout|buy|filter|search|save|plan|play|try|use)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"\b[a-z][a-z0-9-]{3,}\b", re.IGNORECASE)


def _extract_html(doc: Dict[str, Any]) -> str:
    if not isinstance(doc, dict):
        return ""
    html = doc.get("html")
    if isinstance(html, str):
        return html
    components = doc.get("components")
    if isinstance(components, list):
        chunks: List[str] = []
        for comp in components:
            props = comp.get("props") if isinstance(comp, dict) else None
            chunk = props.get("html") if isinstance(props, dict) else None
            if isinstance(chunk, str):
                chunks.append(chunk)
        return "\n".join(chunks)
    return ""


def _visible_text(html: str) -> str:
    without_scripts = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", html or "", flags=re.IGNORECASE)
    without_styles = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", without_scripts, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", without_styles)).strip().lower()


def _keywords(value: Any, limit: int = 8) -> Set[str]:
    words = []
    if isinstance(value, str):
        words = _WORD_RE.findall(value.lower())
    elif isinstance(value, Iterable):
        for item in value:
            if isinstance(item, str):
                words.extend(_WORD_RE.findall(item.lower()))
    stop = {"with", "from", "into", "that", "this", "must", "will", "user", "visible", "interaction"}
    return {w for w in words[:limit] if w not in stop}


def _plan_primary_loop(plan: Dict[str, Any]) -> Dict[str, Any]:
    loop = plan.get("primary_loop") if isinstance(plan, dict) else None
    return loop if isinstance(loop, dict) else {}


def _required_loop_fields_present(loop: Dict[str, Any]) -> bool:
    return all(isinstance(loop.get(key), str) and loop.get(key, "").strip() for key in (
        "user_action",
        "visible_response",
        "state_change",
        "reward_or_payoff",
        "continue_reason",
    ))


def _semantic_translation_integrated(plan: Dict[str, Any], text: str) -> bool:
    translation = plan.get("semantic_translation") if isinstance(plan, dict) else None
    if not isinstance(translation, dict) or not translation:
        return False
    matched = 0
    for anchor, roles in translation.items():
        terms = _keywords(anchor, limit=4)
        if isinstance(roles, dict):
            for role_text in roles.values():
                terms.update(_keywords(role_text, limit=6))
        if any(term in text for term in terms):
            matched += 1
    return matched >= max(1, min(2, len(translation)))


def score_experience(doc: Dict[str, Any], plan: Dict[str, Any] | None = None) -> Dict[str, Any]:
    html = _extract_html(doc)
    text = _visible_text(html)
    plan = plan if isinstance(plan, dict) else {}
    loop = _plan_primary_loop(plan)
    reasons: List[str] = []
    flags: Dict[str, bool] = {}
    score = 0

    has_clear_premise = bool(_TITLE_RE.search(html) or len(text) > 80)
    flags["has_clear_premise"] = has_clear_premise
    if has_clear_premise:
        score += EXPERIENCE_QUALITY_WEIGHTS["has_clear_premise"]
        reasons.append("clear premise/title")

    first_interaction = str(plan.get("first_interaction") or plan.get("onboarding_cue") or "")
    first_terms = _keywords(first_interaction)
    first_interaction_visible = bool(first_terms and any(term in text for term in first_terms)) or bool(_CUE_RE.search(text))
    flags["first_interaction_visible"] = first_interaction_visible
    if first_interaction_visible:
        score += EXPERIENCE_QUALITY_WEIGHTS["first_interaction_visible"]
        reasons.append("visible first-action cue")

    interactive_surface = bool(_CONTROL_RE.search(html) or _EVENT_RE.search(html))
    primary_interaction_defined = interactive_surface and _required_loop_fields_present(loop)
    flags["primary_interaction_defined"] = primary_interaction_defined
    if primary_interaction_defined:
        score += EXPERIENCE_QUALITY_WEIGHTS["primary_interaction_defined"]
        reasons.append("primary loop defined")

    meaningful_state_change = bool(loop.get("state_change")) and bool(_STATE_RE.search(html))
    flags["meaningful_state_change"] = meaningful_state_change
    if meaningful_state_change:
        score += EXPERIENCE_QUALITY_WEIGHTS["meaningful_state_change"]
        reasons.append("meaningful state change")

    feedback_clarity = bool(loop.get("visible_response")) and bool(_FEEDBACK_RE.search(html))
    flags["feedback_clarity"] = feedback_clarity
    if feedback_clarity:
        score += EXPERIENCE_QUALITY_WEIGHTS["feedback_clarity"]
        reasons.append("visible feedback contract")

    continue_reason_present = bool(loop.get("continue_reason") or plan.get("progression_model")) and (
        "progress" in text or "unlock" in text or "complete" in text or bool(_PAYOFF_RE.search(text)) or bool(plan.get("progression_model"))
    )
    flags["continue_reason_present"] = continue_reason_present
    if continue_reason_present:
        score += EXPERIENCE_QUALITY_WEIGHTS["continue_reason_present"]
        reasons.append("reason to continue")

    reset_or_replay_available = bool(plan.get("reset_or_replay")) and bool(_RESET_RE.search(html))
    flags["reset_or_replay_available"] = reset_or_replay_available
    if reset_or_replay_available:
        score += EXPERIENCE_QUALITY_WEIGHTS["reset_or_replay_available"]
        reasons.append("reset/replay available")

    orientation_cues_present = bool(plan.get("onboarding_cue")) and bool(_CUE_RE.search(text))
    flags["orientation_cues_present"] = orientation_cues_present
    if orientation_cues_present:
        score += EXPERIENCE_QUALITY_WEIGHTS["orientation_cues_present"]
        reasons.append("orientation cue present")

    interaction_not_decorative = interactive_surface and meaningful_state_change and feedback_clarity
    flags["interaction_not_decorative"] = interaction_not_decorative
    if interaction_not_decorative:
        score += EXPERIENCE_QUALITY_WEIGHTS["interaction_not_decorative"]
        reasons.append("interaction changes state")

    mobile_interaction_supported = bool(plan.get("mobile_interaction")) and bool(_MOBILE_RE.search(html))
    flags["mobile_interaction_supported"] = mobile_interaction_supported
    if mobile_interaction_supported:
        score += EXPERIENCE_QUALITY_WEIGHTS["mobile_interaction_supported"]
        reasons.append("mobile interaction supported")

    uppercase_tokens = re.findall(r"\b[A-Z0-9]{5,}\b", html or "")
    word_salad_risk_low = len(uppercase_tokens) <= 24
    flags["word_salad_risk_low"] = word_salad_risk_low
    if word_salad_risk_low:
        score += EXPERIENCE_QUALITY_WEIGHTS["word_salad_risk_low"]
        reasons.append("low word-salad risk")

    semantic_integration = _semantic_translation_integrated(plan, text)
    flags["semantic_integration"] = semantic_integration
    if not semantic_integration and plan.get("semantic_translation"):
        reasons.append("semantic anchors weakly integrated")

    task_contract = plan.get("task_contract") if isinstance(plan.get("task_contract"), dict) else {}
    payoff_scene = task_contract.get("payoff_scene") if isinstance(task_contract.get("payoff_scene"), dict) else {}
    payoff_scene_visible = bool(payoff_scene) and bool(_PAYOFF_RE.search(text))
    flags["payoff_scene_visible"] = payoff_scene_visible
    if payoff_scene and payoff_scene_visible:
        reasons.append("visible payoff scene")

    hard_failures: List[str] = []
    if not primary_interaction_defined:
        hard_failures.append("No primary interaction.")
    if not feedback_clarity:
        hard_failures.append("Interaction has no visible feedback.")
    if not meaningful_state_change:
        hard_failures.append("Interaction is decorative only.")
    if not first_interaction_visible:
        hard_failures.append("No visible first-action cue.")

    final_score = max(0, min(100, score))
    return {
        "score": final_score,
        "threshold": EXPERIENCE_SCORE_THRESHOLD,
        "passes": final_score >= EXPERIENCE_SCORE_THRESHOLD and not hard_failures,
        "reasons": reasons,
        "hard_failures": hard_failures,
        "flags": flags,
        "metrics": {
            "html_bytes": len(html.encode("utf-8")),
            "text_bytes": len(text.encode("utf-8")),
            "has_controls": bool(_CONTROL_RE.search(html)),
            "has_event_handlers": bool(_EVENT_RE.search(html)),
            "has_state_updates": bool(_STATE_RE.search(html)),
            "semantic_integration": semantic_integration,
            "payoff_scene_visible": payoff_scene_visible,
        },
    }
