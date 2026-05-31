from __future__ import annotations

import re
from typing import Any, Dict, List


PREMIUM_SCORE_THRESHOLD = 70

_MOTION_RE = re.compile(
    r"(gsap|scrolltrigger|requestanimationframe|@keyframes|animation:|transition:|parallax|ndw\.loop)",
    re.IGNORECASE,
)
_INTERACTION_RE = re.compile(
    r"(addEventListener\(|onclick=|onpointer|pointermove|pointerdown|mousemove|touchstart|keydown|input|change|canvas)",
    re.IGNORECASE,
)
_REGION_RE = re.compile(r"<(main|section|article|aside|nav|footer|canvas)\b", re.IGNORECASE)
_DIV_RE = re.compile(r"<div\b", re.IGNORECASE)
_POSITIONED_LAYER_RE = re.compile(r"(position:\s*(?:absolute|fixed)|\babsolute\b|\bfixed\b|\brelative\b)", re.IGNORECASE)
_TEXT_RE = re.compile(r">([^<]{20,})<")
_LOCAL_KIT_RE = re.compile(r"/static/design-kit/", re.IGNORECASE)
_FULL_VIEW_RE = re.compile(r"(min-height:\s*100vh|min-h-screen|100vh)", re.IGNORECASE)
_BACKGROUND_RE = re.compile(r"(linear-gradient|radial-gradient|background-image|background:)", re.IGNORECASE)
_CENTERED_CARD_RE = re.compile(r"(mx-auto|max-w-(sm|md|lg|xl)|justify-center|items-center)", re.IGNORECASE)
_LOW_CONTRAST_RE = re.compile(r"(text-slate-400|text-slate-500|text-gray-400|text-gray-500)", re.IGNORECASE)
_THREE_RE = re.compile(r"(<canvas\b|\bTHREE\b|WebGLRenderer|getContext\(\s*['\"](?:webgl|webgl2))", re.IGNORECASE)
_COLOR_RE = re.compile(
    r"(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]+\)|hsla?\([^)]+\)|\b(?:white|black|transparent)\b)",
    re.IGNORECASE,
)
_GLOBAL_LISTENER_RE = re.compile(r"\b(?:window|document)\.addEventListener\(", re.IGNORECASE)
_GLOBAL_REMOVE_RE = re.compile(r"\b(?:window|document)\.removeEventListener\(", re.IGNORECASE)
_INLINE_LOOP_CLEANUP_RE = re.compile(
    r"function\s+\w+\s*\([^)]*\)\s*\{[\s\S]{0,4000}?requestAnimationFrame\([\s\S]{0,2000}?NDW\.registerCleanup\(",
    re.IGNORECASE,
)
_POINTER_ONLY_CONTROL_RE = re.compile(
    r"addEventListener\(\s*['\"]mousedown['\"][\s\S]{0,3000}?addEventListener\(\s*['\"]touchstart['\"]",
    re.IGNORECASE,
)
_KEYBOARD_CONTROL_RE = re.compile(r"addEventListener\(\s*['\"]keydown['\"]", re.IGNORECASE)
_ACCESSIBILITY_ATTR_RE = re.compile(
    r"(role\s*=\s*['\"](?:button|slider|spinbutton)['\"]|tabindex\s*=|aria-label\s*=|aria-labelledby\s*=)",
    re.IGNORECASE,
)


def _extract_html(doc: Dict[str, Any]) -> str:
    if not isinstance(doc, dict):
        return ""
    html = doc.get("html")
    if isinstance(html, str):
        return html
    components = doc.get("components")
    if isinstance(components, list):
        parts: List[str] = []
        for comp in components:
            if not isinstance(comp, dict):
                continue
            props = comp.get("props")
            chunk = props.get("html") if isinstance(props, dict) else None
            if isinstance(chunk, str):
                parts.append(chunk)
        return "\n".join(parts)
    return ""


def _normalized_color_tokens(html: str) -> List[str]:
    if not html:
        return []
    tokens = {
        match.group(0).strip().lower().replace(" ", "")
        for match in _COLOR_RE.finditer(html)
        if match.group(0).strip()
    }
    return sorted(tokens)


def extract_review_metrics(doc: Dict[str, Any]) -> Dict[str, Any]:
    html = _extract_html(doc)
    doc_kind = doc.get("kind") if isinstance(doc, dict) else None
    iframe_isolated = str(doc_kind or "").lower() == "full_page_html"
    region_count = len(_REGION_RE.findall(html))
    layered_div_count = len(_DIV_RE.findall(html)) if _FULL_VIEW_RE.search(html) else 0
    has_layered_stage = bool(layered_div_count >= 6 and _POSITIONED_LAYER_RE.search(html))
    has_background_treatment = bool(_BACKGROUND_RE.search(html))
    canvas_or_three = bool(_THREE_RE.search(html))
    first_paint = bool(html and (len(html) > 600 or _TEXT_RE.search(html)))
    motion = bool(_MOTION_RE.search(html))
    interaction = bool(_INTERACTION_RE.search(html))
    design_kit = bool(_LOCAL_KIT_RE.search(html))
    immersive_stage = bool(_FULL_VIEW_RE.search(html) and (canvas_or_three or region_count >= 2 or has_layered_stage))
    centered_card = (
        bool(_CENTERED_CARD_RE.search(html))
        and region_count <= 2
        and not canvas_or_three
        and not has_layered_stage
    )
    contrast_risk = bool(_LOW_CONTRAST_RE.search(html) and not has_background_treatment)
    listener_cleanup_risk = bool(
        not iframe_isolated and _GLOBAL_LISTENER_RE.search(html) and not _GLOBAL_REMOVE_RE.search(html)
    )
    loop_cleanup_risk = bool(not iframe_isolated and _INLINE_LOOP_CLEANUP_RE.search(html))
    accessibility_risk = bool(
        _POINTER_ONLY_CONTROL_RE.search(html)
        and not _KEYBOARD_CONTROL_RE.search(html)
        and not _ACCESSIBILITY_ATTR_RE.search(html)
    )
    colors = _normalized_color_tokens(html)
    return {
        "doc_kind": doc_kind,
        "html_bytes": len(html.encode("utf-8")),
        "quality_flags": {
            "first_paint": first_paint,
            "motion": motion,
            "interaction": interaction,
            "design_kit": design_kit,
            "centered_card": centered_card,
            "contrast_risk": contrast_risk,
            "listener_cleanup_risk": listener_cleanup_risk,
            "loop_cleanup_risk": loop_cleanup_risk,
            "accessibility_risk": accessibility_risk,
        },
        "layout_metrics": {
            "region_count": region_count,
            "layered_div_count": layered_div_count,
            "layered_stage": has_layered_stage,
            "immersive_stage": immersive_stage,
            "canvas_or_three": canvas_or_three,
        },
        "color_metrics": {
            "color_count": len(colors),
            "colors": colors,
            "has_background_treatment": has_background_treatment,
        },
    }


def score_page_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    html = _extract_html(doc)
    metrics = extract_review_metrics(doc)
    reasons: List[str] = []
    flags: Dict[str, Any] = {}
    score = 0

    if metrics["quality_flags"]["first_paint"]:
        score += 18
        reasons.append("visible first paint")
        flags["first_paint"] = True
    else:
        flags["first_paint"] = False

    region_count = int(metrics["layout_metrics"]["region_count"])
    flags["region_count"] = region_count
    if region_count >= 2 or metrics["layout_metrics"]["immersive_stage"]:
        score += 16
        reasons.append("non-trivial structure")

    if metrics["quality_flags"]["motion"]:
        score += 16
        reasons.append("meaningful motion hook")
        flags["motion"] = True
    else:
        flags["motion"] = False

    if metrics["quality_flags"]["interaction"]:
        score += 16
        reasons.append("clear signature interaction")
        flags["interaction"] = True
    else:
        flags["interaction"] = False

    if metrics["quality_flags"]["design_kit"]:
        score += 14
        reasons.append("uses local design kit")
        flags["design_kit"] = True
    else:
        flags["design_kit"] = False

    if metrics["color_metrics"]["has_background_treatment"]:
        score += 10
        reasons.append("intentional background treatment")

    centered_card = bool(metrics["quality_flags"]["centered_card"])
    flags["centered_card"] = centered_card
    if centered_card:
        score -= 12
        reasons.append("penalized generic centered-card shell")
    else:
        score += 6
        reasons.append("avoids generic centered card")

    if metrics["quality_flags"]["contrast_risk"]:
        score -= 6
        reasons.append("possible low contrast")
        flags["contrast_risk"] = True
    else:
        score += 4
        reasons.append("no obvious low-contrast shell")
        flags["contrast_risk"] = False

    if metrics["quality_flags"]["listener_cleanup_risk"]:
        score -= 16
        reasons.append("penalized global listener cleanup risk")
        flags["listener_cleanup_risk"] = True
    else:
        flags["listener_cleanup_risk"] = False

    if metrics["quality_flags"]["loop_cleanup_risk"]:
        score -= 20
        reasons.append("penalized cleanup registration inside animation loop")
        flags["loop_cleanup_risk"] = True
    else:
        flags["loop_cleanup_risk"] = False

    if metrics["quality_flags"]["accessibility_risk"]:
        score -= 12
        reasons.append("penalized pointer-only control without accessibility semantics")
        flags["accessibility_risk"] = True
    else:
        flags["accessibility_risk"] = False

    final_score = max(0, min(100, score))
    return {
        "score": final_score,
        "threshold": PREMIUM_SCORE_THRESHOLD,
        "passes": final_score >= PREMIUM_SCORE_THRESHOLD,
        "reasons": reasons,
        "flags": flags,
        "metrics": metrics,
    }
