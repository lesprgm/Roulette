from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from api.generation.experience_grammar import all_experience_cell_keys, parse_cell_key, seeded_experience_cell
from api.generation.experience_quality import score_experience
from api.quality import score_page_doc

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


REDIS_URL = os.getenv("REDIS_URL", "").strip()
REDIS_DIVERSITY_ENABLED = os.getenv("REDIS_DIVERSITY_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
HTML_CACHE_TTL_SECONDS = int(os.getenv("DIVERSITY_HTML_CACHE_TTL_SECONDS", "604800") or 604800)
FINGERPRINT_TTL_SECONDS = int(os.getenv("DIVERSITY_FINGERPRINT_TTL_SECONDS", "604800") or 604800)

_CLIENT = None
if redis and REDIS_URL and REDIS_DIVERSITY_ENABLED and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        _CLIENT = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        _CLIENT = None

_TAG_RE = re.compile(r"<[^>]+>")
_HTML_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\b[a-z][a-z0-9-]{3,}\b", re.IGNORECASE)


def _client(client: Any = None) -> Any:
    return client if client is not None else _CLIENT


def _html_from_doc(doc: Dict[str, Any]) -> str:
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


def _slug(value: Any, limit: int = 40) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return (text[:limit].strip("_") or "unknown")


def _hash_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _weighted_sample(items: List[Tuple[str, float]], seed: int | None = None) -> str:
    if not items:
        return all_experience_cell_keys()[0]
    total = sum(max(0.0001, score) for _key, score in items)
    rng = random.Random(int(seed or time.time_ns()))
    cursor = rng.random() * total
    for key, score in items:
        cursor -= max(0.0001, score)
        if cursor <= 0:
            return key
    return items[-1][0]


def choose_experience_cell(seed: int | None = None, client: Any = None) -> Dict[str, str]:
    redis_client = _client(client)
    if redis_client is None:
        return seeded_experience_cell(seed)
    now = time.time()
    scored: List[Tuple[str, float]] = []
    try:
        for key in all_experience_cell_keys():
            count = float(redis_client.zscore("qd:count:experience_cell", key) or 0)
            avg_quality = float(redis_client.zscore("qd:avg_quality:experience_cell", key) or 0.5)
            last_used = float(redis_client.zscore("qd:last_used:experience_cell", key) or 0)
            age_hours = max(0.0, (now - last_used) / 3600.0) if last_used else 24.0
            underuse_bonus = 1.0 / (1.0 + count)
            quality_bonus = max(0.1, min(avg_quality, 1.0))
            staleness_bonus = min(1.0, age_hours / 24.0)
            score = (0.45 * underuse_bonus) + (0.35 * quality_bonus) + (0.20 * staleness_bonus)
            scored.append((key, score))
        return parse_cell_key(_weighted_sample(scored, seed))
    except Exception:
        return seeded_experience_cell(seed)


def _input_modalities(html: str) -> List[str]:
    found: List[str] = []
    checks = [
        ("keyboard", r"keydown|keyup|<input\b|<textarea\b"),
        ("pointer", r"pointer|mousemove|mousedown|click|drag"),
        ("touch", r"touchstart|touchmove|pointerdown"),
        ("scroll", r"scroll|wheel|ScrollTrigger"),
    ]
    for label, pattern in checks:
        if re.search(pattern, html or "", re.IGNORECASE):
            found.append(label)
    return found or ["passive"]


def _dominant_terms(html: str, limit: int = 8) -> List[str]:
    text = _HTML_RE.sub(" ", _TAG_RE.sub(" ", html or "")).lower()
    stop = {"with", "from", "this", "that", "into", "your", "html", "body", "main", "section"}
    counts: Dict[str, int] = {}
    for word in _WORD_RE.findall(text):
        if word in stop or word.isdigit():
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def build_site_descriptor(doc: Dict[str, Any], *, site_id: str | None = None) -> Dict[str, Any]:
    html = _html_from_doc(doc)
    debug = doc.get("ndw_debug") if isinstance(doc, dict) else None
    plan = debug.get("premium_plan") if isinstance(debug, dict) else None
    if not isinstance(plan, dict):
        plan = {}
    visual_quality = debug.get("quality_score") if isinstance(debug, dict) else None
    if not isinstance(visual_quality, dict):
        visual_quality = score_page_doc(doc)
    experience_quality = score_experience(doc, plan)
    loop = plan.get("primary_loop") if isinstance(plan.get("primary_loop"), dict) else {}
    anchors = plan.get("semantic_anchors") or plan.get("anchors") or {}
    cell = {
        "experience_archetype": plan.get("experience_archetype") or "unknown",
        "primary_loop_type": plan.get("primary_loop_type") or "unknown",
    }
    descriptor = {
        "site_id": site_id or _hash_text(html)[:16],
        "anchors": anchors if isinstance(anchors, dict) else {},
        "experience_archetype": cell["experience_archetype"],
        "visitor_role": plan.get("visitor_role") or "",
        "visitor_goal": plan.get("visitor_goal") or "",
        "primary_loop_type": cell["primary_loop_type"],
        "state_change_type": _slug(loop.get("state_change") if isinstance(loop, dict) else ""),
        "input_modality": _input_modalities(html),
        "layout_archetype": plan.get("layout_archetype") or plan.get("layout_key") or "",
        "motion_archetype": plan.get("motion_archetype") or plan.get("motion_preset") or "",
        "rendering_mode": plan.get("rendering_mode") or "",
        "quality_score": visual_quality.get("score", 0),
        "experience_score": experience_quality.get("score", 0),
        "terms": _dominant_terms(html),
        "created_at": int(time.time()),
    }
    return descriptor


def fingerprint_values(descriptor: Dict[str, Any], plan: Dict[str, Any], html: str) -> Dict[str, str]:
    structure = re.sub(r">[^<]+<", "><", html or "")
    structure = re.sub(r"\s+", " ", structure)
    return {
        "descriptor": _hash_json(descriptor),
        "plan": _hash_json(plan),
        "html_structure": _hash_text(structure[:20000]),
    }


def descriptor_has_duplicate(descriptor: Dict[str, Any], plan: Dict[str, Any], html: str, client: Any = None) -> bool:
    redis_client = _client(client)
    if redis_client is None:
        return False
    try:
        values = fingerprint_values(descriptor, plan, html)
        return any(redis_client.exists(f"fingerprint:{kind}:{value}") for kind, value in values.items())
    except Exception:
        return False


def record_generation_event(event: str, fields: Dict[str, Any], client: Any = None) -> None:
    redis_client = _client(client)
    if redis_client is None:
        return
    try:
        payload = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v) for k, v in fields.items()}
        payload["event"] = event
        payload["ts"] = str(int(time.time()))
        redis_client.xadd("generation:events", payload, maxlen=10000, approximate=True)
    except Exception:
        return


def record_site_descriptor(doc: Dict[str, Any], *, event: str = "site_served", client: Any = None) -> Optional[Dict[str, Any]]:
    if not isinstance(doc, dict) or doc.get("error"):
        return None
    redis_client = _client(client)
    if redis_client is None:
        return build_site_descriptor(doc)
    html = _html_from_doc(doc)
    debug = doc.get("ndw_debug") if isinstance(doc, dict) else None
    plan = debug.get("premium_plan") if isinstance(debug, dict) and isinstance(debug.get("premium_plan"), dict) else {}
    descriptor = build_site_descriptor(doc)
    site_id = str(descriptor["site_id"])
    cell_key = f"{descriptor['experience_archetype']}:{descriptor['primary_loop_type']}"
    quality_norm = max(0.0, min(1.0, float(descriptor.get("experience_score") or descriptor.get("quality_score") or 0) / 100.0))
    try:
        pipe = redis_client.pipeline()
        pipe.set(f"site:{site_id}:descriptor", json.dumps(descriptor, ensure_ascii=False, separators=(",", ":")))
        pipe.set(f"site:{site_id}:plan", json.dumps(plan, ensure_ascii=False, separators=(",", ":")))
        pipe.set(f"site:{site_id}:quality", json.dumps({
            "visual": (debug or {}).get("quality_score"),
            "experience": score_experience(doc, plan),
        }, ensure_ascii=False, separators=(",", ":")))
        if HTML_CACHE_TTL_SECONDS > 0 and html:
            pipe.setex(f"site:{site_id}:html", HTML_CACHE_TTL_SECONDS, html)
        pipe.zincrby("qd:count:experience_cell", 1, cell_key)
        pipe.zincrby("qd:count:experience_archetype", 1, str(descriptor["experience_archetype"]))
        pipe.zincrby("qd:count:primary_loop_type", 1, str(descriptor["primary_loop_type"]))
        pipe.zadd("qd:last_used:experience_cell", {cell_key: int(time.time())})
        pipe.zadd("qd:avg_quality:experience_cell", {cell_key: quality_norm})
        pipe.hincrby(f"qd:cell:{cell_key}", "count", 1)
        pipe.hset(
            f"qd:cell:{cell_key}",
            mapping={
                "last_generated_at": str(int(time.time())),
                "last_site_id": site_id,
                "last_quality": str(quality_norm),
            },
        )
        for kind, value in fingerprint_values(descriptor, plan, html).items():
            pipe.setex(f"fingerprint:{kind}:{value}", FINGERPRINT_TTL_SECONDS, site_id)
        pipe.execute()
        record_generation_event(event, {
            "site_id": site_id,
            "experience_archetype": descriptor["experience_archetype"],
            "primary_loop_type": descriptor["primary_loop_type"],
            "quality_score": descriptor["quality_score"],
            "experience_score": descriptor["experience_score"],
        }, client=redis_client)
    except Exception:
        return descriptor
    return descriptor
