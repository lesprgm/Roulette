from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


DESIGN_SCORE_THRESHOLD = 75

_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_SCRIPT_RE = re.compile(r"<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>", re.IGNORECASE)
_COLOR_RE = re.compile(r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\)|\b(?:black|white|red|orange|yellow|green|blue|purple|pink|cyan|magenta|lime)\b)")
_CONTROL_RE = re.compile(r"<(?:button|input|select|textarea)\b|role=['\"](?:button|slider|tab)['\"]", re.IGNORECASE)
_PANEL_RE = re.compile(r"\b(card|panel|badge|stat|metric|telemetry|registry|dashboard|console|slot|rail|sidebar)\b", re.IGNORECASE)
_PLANNING_TERMS_RE = re.compile(
    r"\b(onboarding instructions?|visitor role|visitor goal|primary loop|feedback contract|how to use|instructions?)\b",
    re.IGNORECASE,
)
_VISIBLE_ARTIFACT_RE = re.compile(r"(^|\s)(//|TODO|undefined|null|```|~~~|\{ ?\"kind\"|raw json)(\s|$)", re.IGNORECASE)
_AI_TROPE_RE = re.compile(r"\b(glassmorphism|neon glow|cyber dashboard|control room|telemetry|system status|calibrated|protocol)\b", re.IGNORECASE)
_GENERIC_AI_WORD_RE = re.compile(
    r"\b(data|schematic|system|signal|drift|protocol|calibration|initiate|terminal|compiler|telemetry|manifest|roulette|ndw|runtime|non-deterministic)\b",
    re.IGNORECASE,
)
_HOST_BRAND_RE = re.compile(r"\b(roulette|ndw|no delay wireless|non-deterministic)\b", re.IGNORECASE)
_PRIMARY_ACTION_RE = re.compile(
    r"\b(play|start|type|answer|submit|draw|paint|randomize|remix|generate|save|book|reserve|buy|add to cart|compare|checkout|restart|reset|try|choose|select|filter|search|add|move|shoot|launch|steer|jump|match)\b",
    re.IGNORECASE,
)
_EMPTY_STAGE_RE = re.compile(r"\b(empty|blank|placeholder|start from scratch|slot\s+\d+|no items|0 items)\b", re.IGNORECASE)
_TITLE_TEXT_RE = re.compile(r"<(?:title|h1|h2)[^>]*>(.*?)</(?:title|h1|h2)>", re.IGNORECASE | re.DOTALL)
_STRUCTURAL_VISUAL_RE = re.compile(r"<(?:svg|canvas|figure)\b|<table\b", re.IGNORECASE)
_CONTENT_VISUAL_TERM_RE = re.compile(
    r"\b(product|preview|thumbnail|gallery|image|illustration|sprite|player|enemy|target|board|grid|map|route|"
    r"ticket|receipt|pass|calendar|chart|graph|avatar|record|kanban|card deck|menu item|cart|checkout|"
    r"artifact|canvas|drawing|sequencer|timeline|itinerary)\b",
    re.IGNORECASE,
)
_CHROME_ONLY_RE = re.compile(r"\b(panel|button|badge|stat|metric|toolbar|sidebar|icon|gradient|background)\b", re.IGNORECASE)
_MATERIAL_EMBODIMENT_RE = re.compile(
    r"(repeating-linear-gradient|radial-gradient|linear-gradient|::before|::after|border-(?:image|style|radius)|"
    r"box-shadow|filter|feTurbulence|feDisplacementMap|<pattern\b|<mask\b|clip-path|canvas|getContext|"
    r"Mesh(?:Standard|Physical)?Material|texture|grain|fiber|fibre|woven|weave|stitch|stitched|thread|"
    r"fabric|soft|padded|quilt|brushed|polished|metallic|marble|woodgrain|leather|ceramic|glassmorphism)",
    re.IGNORECASE,
)
_MATERIAL_SPEC_LEAK_RE = re.compile(
    r"\b(?:material|finish|chassis material|surface material)\s*:\s*[a-z][a-z -]{2,}"
    r"|\b[a-z][a-z -]{2,}\s+finish\b"
    r"|\b[a-z][a-z -]{2,}\s+alloy\b",
    re.IGNORECASE,
)
_COPY_LIMITS = {
    "almost_none": 45,
    "low": 95,
    "medium": 170,
    "high": 280,
}


def _extract_html(doc: Dict[str, Any]) -> str:
    html = doc.get("html") if isinstance(doc, dict) else ""
    return html if isinstance(html, str) else ""


def _visible_text(html: str) -> str:
    stripped = _STYLE_SCRIPT_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", stripped)).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _title_text(html: str) -> str:
    return " ".join(re.sub(r"\s+", " ", _TAG_RE.sub(" ", match)).strip() for match in _TITLE_TEXT_RE.findall(html or ""))


def _contract(plan: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    contract = plan.get("genre_contract")
    return contract if isinstance(contract, dict) else {}


def _copy_limit(contract: Dict[str, Any]) -> Tuple[str, int]:
    density = str(contract.get("copy_density") or "medium")
    return density, _COPY_LIMITS.get(density, _COPY_LIMITS["medium"])


def _has_content_visual_artifact(html: str, text: str, plan: Dict[str, Any] | None) -> bool:
    if _STRUCTURAL_VISUAL_RE.search(html):
        return True
    if _CONTENT_VISUAL_TERM_RE.search(text):
        return True
    activity = (plan or {}).get("activity_contract") if isinstance(plan, dict) else None
    if isinstance(activity, dict):
        variant = str(activity.get("activity_variant") or "").replace("_", " ")
        family = str(activity.get("activity_family") or "").replace("_", " ")
        if variant and variant in text.lower():
            return True
        if family and family in text.lower():
            return True
    return False


def score_design_discipline(doc: Dict[str, Any], plan: Dict[str, Any] | None = None) -> Dict[str, Any]:
    html = _extract_html(doc)
    text = _visible_text(html)
    lower_text = text.lower()
    contract = _contract(plan)
    tags: List[str] = []
    notes: List[str] = []
    score = 100
    control_count = len(_CONTROL_RE.findall(html))

    copy_density, copy_limit = _copy_limit(contract)
    words = _word_count(text)
    if words > copy_limit:
        tags.append("copy_over_budget")
        notes.append(f"copy density {copy_density} allows about {copy_limit} words; visible text has {words}")
        score -= 14

    if _PLANNING_TERMS_RE.search(text):
        tags.append("planning_terms_visible")
        notes.append("visible UI contains planning/tutorial terminology")
        score -= 26

    if "onboarding" in lower_text or "onboarding instructions" in lower_text:
        tags.append("literal_onboarding_section")
        notes.append("onboarding leaked as a literal UI section")
        score -= 20

    if _VISIBLE_ARTIFACT_RE.search(text):
        tags.append("visible_code_artifact")
        notes.append("visible copy includes code/comment/debug artifact text")
        score -= 30

    colors = set(match.group(1).lower().replace(" ", "") for match in _COLOR_RE.finditer(html))
    if len(colors) > 16:
        tags.append("palette_collision")
        notes.append(f"too many visible color literals ({len(colors)}) for coherent palette roles")
        score -= 10

    panel_terms = _PANEL_RE.findall(text)
    visual_density = str(contract.get("visual_density") or "")
    if len(panel_terms) >= 9 and visual_density not in {"dense", "maximal"}:
        tags.append("too_many_panels")
        notes.append("panel/badge/dashboard language dominates a non-dense genre")
        score -= 12

    if _AI_TROPE_RE.search(text) and str(contract.get("chrome_policy") or "") in {"none", "minimal_functional", "diegetic_only"}:
        tags.append("decorative_dashboard_chrome")
        notes.append("fake telemetry/dashboard chrome appears despite restrictive chrome policy")
        score -= 10

    generic_ai_terms = _GENERIC_AI_WORD_RE.findall(text)
    if len(generic_ai_terms) >= 4:
        tags.append("generic_ai_title_or_copy")
        notes.append("visible copy leans on repeated sci-fi/generator filler terms")
        score -= 10

    if _HOST_BRAND_RE.search(text):
        tags.append("host_brand_leakage")
        notes.append("visible copy exposes host/project branding instead of the generated site's own identity")
        score -= 12

    if _MATERIAL_SPEC_LEAK_RE.search(text):
        tags.append("material_spec_label_leakage")
        notes.append("material anchor appears as generic spec-label copy instead of embodied surface/form")
        score -= 10

    if control_count and not _PRIMARY_ACTION_RE.search(text):
        tags.append("weak_primary_action")
        notes.append("controls exist but no obvious fun/useful primary action is visible")
        score -= 8

    if _EMPTY_STAGE_RE.search(text):
        tags.append("blank_stage_first_paint")
        notes.append("visible copy suggests an empty or placeholder first screen")
        score -= 10

    if control_count >= 4 and words > copy_limit * 0.75:
        tags.append("controls_overexplained")
        notes.append("obvious controls are paired with heavy explanatory copy")
        score -= 8

    if not re.search(r"<(?:main|section|canvas)\b", html, re.IGNORECASE):
        tags.append("weak_focal_point")
        notes.append("no obvious primary stage/region found")
        score -= 10

    if not _has_content_visual_artifact(html, text, plan):
        tags.append("visual_chrome_only")
        notes.append("page appears to rely on panels/buttons/backgrounds without a content-bearing visual artifact")
        score -= 12
    elif control_count >= 2 and len(_CHROME_ONLY_RE.findall(text)) >= 5 and not _STRUCTURAL_VISUAL_RE.search(html):
        tags.append("weak_content_visual")
        notes.append("visible content names a format, but UI chrome appears to dominate over a primary visual object/stage")
        score -= 6

    semantic = (plan or {}).get("semantic_anchors") if isinstance(plan, dict) else None
    if isinstance(semantic, dict) and semantic:
        matched = sum(1 for value in semantic.values() if str(value).lower() in lower_text)
        if matched >= 3 and control_count < 2:
            tags.append("semantic_anchors_only_decorative")
            notes.append("semantic anchors are visible as surface labels but interaction appears thin")
            score -= 8
        title_text = _title_text(html).lower()
        anchor_in_title = any(
            (term := str(value or "").strip().lower()) and term in title_text
            for value in semantic.values()
        )
        if anchor_in_title and not _MATERIAL_EMBODIMENT_RE.search(html):
            tags.append("semantic_anchor_label_only")
            notes.append(
                "semantic anchor appears in title/heading but no material, texture, shape, motion, or metaphor embodiment cues were found"
            )
            score -= 12

    return {
        "score": max(0, min(100, score)),
        "threshold": DESIGN_SCORE_THRESHOLD,
        "passes": score >= DESIGN_SCORE_THRESHOLD,
        "tags": sorted(set(tags)),
        "notes": notes,
        "metrics": {
            "visible_word_count": words,
            "copy_density": copy_density,
            "copy_limit": copy_limit,
            "color_count": len(colors),
            "control_count": control_count,
            "panel_term_count": len(panel_terms),
            "has_content_visual_artifact": _has_content_visual_artifact(html, text, plan),
        },
    }
