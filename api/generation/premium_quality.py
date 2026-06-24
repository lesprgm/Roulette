from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def has_full_experience_plan(plan: Dict[str, Any]) -> bool:
    if not isinstance(plan, dict):
        return False
    loop = plan.get("primary_loop")
    if not isinstance(loop, dict):
        return False
    required = ("user_action", "visible_response", "state_change", "reward_or_payoff", "continue_reason")
    return bool(
        str(plan.get("first_interaction") or plan.get("onboarding_cue") or "").strip()
        and all(str(loop.get(key) or "").strip() for key in required)
    )


def attach_quality_score(
    doc: Dict[str, Any],
    mode: str,
    *,
    score_page_doc: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("error"):
        return doc
    quality = score_page_doc(doc)
    out = dict(doc)
    debug = out.get("ndw_debug")
    if not isinstance(debug, dict):
        debug = {}
    debug["generation_mode"] = mode
    debug["quality_score"] = quality
    out["ndw_debug"] = debug
    return out


def attach_premium_evaluations(
    scored: Dict[str, Any],
    plan: Dict[str, Any],
    *,
    score_experience: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    score_design_discipline: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    score_activity_depth: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    include_experience: Optional[bool] = None,
) -> Dict[str, Any]:
    debug = dict(scored.get("ndw_debug") or {})
    debug["premium_plan"] = plan
    should_score_experience = has_full_experience_plan(plan) if include_experience is None else include_experience
    if should_score_experience:
        debug["experience_quality"] = score_experience(scored, plan)
    else:
        debug["experience_quality"] = {
            "score": None,
            "threshold": None,
            "passes": True,
            "skipped": True,
            "reason": "full planner experience loop not available for this generation path",
        }
    debug["design_quality"] = score_design_discipline(scored, plan)
    debug["activity_quality"] = score_activity_depth(scored, plan)
    repair_signals: List[str] = []
    for key in ("experience_quality", "design_quality", "activity_quality"):
        result = debug.get(key)
        if not isinstance(result, dict) or result.get("passes", True):
            continue
        tags = result.get("tags") or result.get("hard_failures") or []
        if isinstance(tags, list):
            repair_signals.extend(str(tag) for tag in tags[:8])
        else:
            repair_signals.append(str(tags))
    debug["repair_signals"] = sorted(set(signal for signal in repair_signals if signal))
    scored["ndw_debug"] = debug
    return scored
