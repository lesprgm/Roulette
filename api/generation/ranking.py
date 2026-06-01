from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from api import dedupe
from api.quality import extract_review_metrics, score_page_doc


def _diversity_bucket(doc: Dict[str, Any]) -> tuple:
    metrics = extract_review_metrics(doc)
    flags = metrics["quality_flags"]
    layout = metrics["layout_metrics"]
    colors = metrics["color_metrics"]
    region_bucket = min(int(layout["region_count"]), 4)
    color_bucket = min(int(colors["color_count"]) // 2, 4)
    return (
        doc.get("kind"),
        bool(layout["canvas_or_three"]),
        bool(layout["immersive_stage"]),
        region_bucket,
        color_bucket,
        bool(flags["motion"]),
        bool(flags["interaction"]),
        bool(flags["design_kit"]),
        bool(flags["centered_card"]),
    )


def _candidate_score(doc: Dict[str, Any]) -> int:
    quality = score_page_doc(doc)
    metrics = quality.get("metrics") or extract_review_metrics(doc)
    flags = metrics["quality_flags"]
    layout = metrics["layout_metrics"]
    colors = metrics["color_metrics"]
    score = int(quality.get("score", 0))
    score += min(int(colors["color_count"]), 6)
    if layout["immersive_stage"]:
        score += 8
    if layout["canvas_or_three"]:
        score += 4
    if flags["motion"]:
        score += 4
    if flags["interaction"]:
        score += 3
    if flags["design_kit"]:
        score += 3
    if flags["centered_card"]:
        score -= 10
    return score


def rank_prefetch_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not docs:
        return []
    ranked: List[Tuple[int, tuple, int, Dict[str, Any]]] = []
    seen_signatures: Set[str] = set()
    for idx, doc in enumerate(docs):
        if not isinstance(doc, dict):
            continue
        sig = dedupe.signature_for_doc(doc)
        if sig and sig in seen_signatures:
            continue
        if sig:
            seen_signatures.add(sig)
        ranked.append((_candidate_score(doc), _diversity_bucket(doc), idx, doc))
    ranked.sort(key=lambda item: (-item[0], item[2]))

    primary: List[Dict[str, Any]] = []
    spill: List[Dict[str, Any]] = []
    seen_buckets: Set[tuple] = set()
    for _score, bucket, _idx, doc in ranked:
        if bucket in seen_buckets:
            spill.append(doc)
            continue
        seen_buckets.add(bucket)
        primary.append(doc)
    return primary + spill
