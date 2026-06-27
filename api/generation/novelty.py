from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from api.quality import extract_review_metrics


LEDGER_PATH = Path(os.getenv("NOVELTY_LEDGER_PATH", "cache/novelty_ledger.json"))
LEDGER_SIZE = max(10, int(os.getenv("NOVELTY_LEDGER_SIZE", "80") or 80))

_WORD_RE = re.compile(r"\b[a-z][a-z0-9-]{3,}\b", re.IGNORECASE)
_TITLE_RE = re.compile(r"<(?:title|h1)[^>]*>(.*?)</(?:title|h1)>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

_GENERIC_WORDS = {
    "with",
    "from",
    "this",
    "that",
    "your",
    "into",
    "control",
    "system",
    "interactive",
    "experience",
    "premium",
    "generated",
}


def _doc_html(doc: Dict[str, Any]) -> str:
    if not isinstance(doc, dict):
        return ""
    html = doc.get("html")
    if isinstance(html, str):
        return html
    comps = doc.get("components")
    if isinstance(comps, list):
        parts: List[str] = []
        for comp in comps:
            props = comp.get("props") if isinstance(comp, dict) else None
            if isinstance(props, dict) and isinstance(props.get("html"), str):
                parts.append(props["html"])
        return "\n".join(parts)
    return ""


def _clean_text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html or "")).strip().lower()


def _dominant_terms(html: str, limit: int = 8) -> List[str]:
    text = _clean_text(html)
    counts = Counter(
        w.lower()
        for w in _WORD_RE.findall(text)
        if w.lower() not in _GENERIC_WORDS
    )
    return [word for word, _count in counts.most_common(limit)]


def _title_terms(html: str) -> List[str]:
    terms: List[str] = []
    for match in _TITLE_RE.finditer(html or ""):
        terms.extend(_dominant_terms(match.group(1), limit=4))
    return terms[:6]


def fingerprint_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    html = _doc_html(doc)
    metrics = extract_review_metrics(doc)
    flags = metrics.get("quality_flags", {})
    layout = metrics.get("layout_metrics", {})
    colors = metrics.get("color_metrics", {})
    debug = doc.get("ndw_debug") if isinstance(doc, dict) else None
    plan = debug.get("premium_plan") if isinstance(debug, dict) else None
    if not isinstance(plan, dict):
        plan = {}
    return {
        "ts": int(time.time()),
        "layout": plan.get("layout_archetype") or plan.get("layout_key") or _layout_bucket(layout),
        "palette": plan.get("palette_key") or _palette_bucket(colors),
        "motion": plan.get("motion_preset") or plan.get("motion_archetype") or _motion_bucket(flags),
        "interaction": plan.get("interaction_model") or ("interactive" if flags.get("interaction") else "ambient"),
        "rendering": plan.get("rendering_mode") or ("three" if layout.get("canvas_or_three") else "dom"),
        "terms": _dominant_terms(html),
        "title_terms": _title_terms(html),
    }


def _layout_bucket(layout: Dict[str, Any]) -> str:
    if layout.get("immersive_stage"):
        return "immersive_stage"
    if layout.get("canvas_or_three"):
        return "canvas_or_three"
    regions = int(layout.get("region_count") or 0)
    if regions >= 4:
        return "dense_regions"
    if regions >= 2:
        return "split_regions"
    return "single_stage"


def _palette_bucket(colors: Dict[str, Any]) -> str:
    values = [str(c).lower() for c in colors.get("colors", []) if isinstance(c, str)]
    joined = " ".join(values)
    if "#2563eb" in joined or "#003087" in joined:
        return "blue"
    if "#0d9488" in joined or "#38bdf8" in joined or "#06b6d4" in joined:
        return "teal_cyan"
    if "#a47864" in joined or "#c9694a" in joined:
        return "earth_warm"
    if "#a78bfa" in joined or "#635bff" in joined or "#7c3aed" in joined:
        return "purple"
    if "#4ade80" in joined or "#a3e635" in joined or "#22c55e" in joined:
        return "green"
    if "#990011" in joined or "#fb7185" in joined or "#ff6b6b" in joined:
        return "red_rose"
    if "#f59e0b" in joined or "#f97316" in joined or "#eab308" in joined:
        return "amber_orange"
    return "mixed"


def _motion_bucket(flags: Dict[str, Any]) -> str:
    return "motion" if flags.get("motion") else "static"


def _read_entries() -> List[Dict[str, Any]]:
    try:
        data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        entries = data.get("entries")
    else:
        entries = data
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def record_served_doc(doc: Dict[str, Any]) -> None:
    if not isinstance(doc, dict) or doc.get("error"):
        return
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    entries = _read_entries()
    entries.append(fingerprint_doc(doc))
    entries = entries[-LEDGER_SIZE:]
    try:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(json.dumps({"entries": entries}, separators=(",", ":")), encoding="utf-8")
    except Exception:
        return


def _top_values(entries: List[Dict[str, Any]], key: str, limit: int = 4) -> List[str]:
    counts = Counter(str(entry.get(key, "")).strip() for entry in entries)
    counts.pop("", None)
    return [value for value, _count in counts.most_common(limit)]


def novelty_summary(limit: int = 40) -> Dict[str, Any]:
    entries = _read_entries()[-max(1, limit):]
    if not entries:
        return {
            "avoid_recent": [],
            "overused_axes": {},
            "underused_targets": [
                "avoid cyber/audio dashboards unless the concept demands it",
                "try spatial maps, playable instruments, living posters, kinetic editorials, or fictional tools",
            ],
        }
    term_counts: Counter[str] = Counter()
    for entry in entries:
        term_counts.update(str(t) for t in entry.get("terms", []) if t)
        term_counts.update(str(t) for t in entry.get("title_terms", []) if t)
    avoid_terms = [term for term, _count in term_counts.most_common(12)]
    overused = {
        "layouts": _top_values(entries, "layout"),
        "palettes": _top_values(entries, "palette"),
        "motion": _top_values(entries, "motion"),
        "interactions": _top_values(entries, "interaction"),
        "rendering": _top_values(entries, "rendering"),
    }
    return {
        "avoid_recent": avoid_terms,
        "overused_axes": overused,
        "underused_targets": [
            "choose a different layout/palette/motion family than the overused axes",
            "prefer a world metaphor not present in avoid_recent",
            "if recent pages are dashboards, make an artifact, instrument, map, simulator, or editorial scene",
        ],
    }
