from __future__ import annotations
import json
import logging
import os
import random
from typing import Any, Dict, Generator, Optional
import requests

PROVIDER = "gemini"
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-pro")
try:
    TEMPERATURE = float(os.getenv("TEMPERATURE", "1.2"))
except Exception:
    TEMPERATURE = 1.2

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
)

USING = "gemini" if GEMINI_API_KEY else "stub"

def status() -> Dict[str, Any]:
    return {
        "provider": PROVIDER,
        "model": MODEL_NAME if GEMINI_API_KEY else None,
        "has_token": bool(GEMINI_API_KEY),
        "using": USING,
    }


def probe() -> Dict[str, Any]:
    ok = bool(GEMINI_API_KEY)
    return {"ok": ok, "using": "gemini" if ok else "stub"}


def generate_page(brief: str, seed: int) -> Dict[str, Any]:
    """Return a complete page JSON (Gemini when possible, stub otherwise).

    Behaviors for hands-off demo:
    - If 'brief' is falsy or looks like an auto cue ("auto", "random", "surprise me"), let the model pick a short creative theme.
    - If 'seed' is falsy/0, pick a random seed so subsequent clicks differ.
    """
    auto_cues = {"", "auto", "random", "surprise me"}
    brief_str = (brief or "").strip()
    is_auto = brief_str.lower() in auto_cues
    if not brief_str or is_auto:
        brief_str = ""  # pass empty downstream; prompt will instruct to invent a theme
    seed_val = int(seed or 0)
    if not seed_val:
        seed_val = random.randint(1, 10_000_000)

    if GEMINI_API_KEY:
        page = _call_gemini_for_page(brief_str, seed_val)
        if page:
            page.setdefault("model_version", MODEL_NAME)
            return page
        logging.warning("Gemini failed or returned invalid JSON; using stub.")

    return _stub_page(brief_str or "Creative brand", seed_val)


def stream_page(brief: str, seed: int) -> Generator[str, None, None]:
    """
    NDJSON stream compatible with tests/FE:
      1) {"event":"meta","request_id":"..."}
      2) {"event":"page","data":{...full page...}}
    """
    rid = _make_request_id()
    yield json.dumps({"event": "meta", "request_id": rid}) + "\n"
    page = generate_page(brief, seed)
    yield json.dumps({"event": "page", "data": page}) + "\n"


_PAGE_SHAPE_HINT = """
Return ONLY a single JSON object with these top-level keys:
- "components": array of component objects, each:
     { "id": string, "type": string, "props": object }
    Allowed types (only these): "hero", "cta", "feature_grid", "testimonial", "stats", "pricing", "gallery", "text", "card_list".
- "layout": { "flow": "stack" | "grid" }
- "palette": { "primary": string, "accent": string }
    Choose contrasting values for both from this set: { slate, indigo, rose, emerald, amber, violet }.
- "links": array of strings (like "/about")
- "seed": integer (echo the chosen seed)
Rules:
- Generate a fresh, short brief and a fresh seed on each call; do not rely on client inputs.
- Output raw JSON only (no prose, no code fences). JSON must be valid/parseable.
- Include ≥3 different component types from the allowed set and vary order, types, and copy length across calls (avoid only "hero + text + cta").
- Use layout.flow randomly: choose "grid" ~30% of the time, otherwise "stack".
- Provide sensible defaults (titles, labels, hrefs), and omit empty values. No demo cards.
- Prefer adding one of: "feature_grid", "testimonial", "stats", "pricing", "gallery", or "card_list".
- Fill required fields for each component; omit a component if you cannot provide minimal content.
"""

def _call_gemini_for_page(brief: str, seed: int) -> Optional[Dict[str, Any]]:
    """Call Gemini 1.5 Pro via REST and parse a page dict; None on failure."""
    # Higher temperature increases variety; the seed nudges palette/layout hints below.
    temperature = TEMPERATURE
    palette_hint = _seeded_palette_hint(seed)
    layout_hint = _seeded_layout_hint(seed)

    prompt = f"""
You are a webpage generator that returns JSON only.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}

 Palette hint (optional): {palette_hint}
 Layout hint (optional): {layout_hint}
"""

    try:
        resp = requests.post(
            GEMINI_ENDPOINT + f"?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048},
            },
            timeout=45,
        )
    except Exception as e:
        logging.warning("Gemini request error: %r", e)
        return None

    if resp.status_code != 200:
        logging.warning("Gemini HTTP %s: %s", resp.status_code, resp.text[:400])
        return None

    try:
        data = resp.json()
    except Exception:
        logging.warning("Gemini: non-JSON HTTP body")
        return None

    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text")
    )
    if not text or not isinstance(text, str):
        logging.warning("Gemini: empty response text")
        return None

    try:
        page = _json_from_text(text)
    except Exception as e:
        logging.warning("Gemini: failed to extract JSON: %r", e)
        return None

    # Minimal validation + defaults
    if not isinstance(page, dict) or "components" not in page or not isinstance(
        page["components"], list
    ):
        logging.warning("Gemini: missing 'components' array")
        return None

    page.setdefault("layout", {"flow": "stack"})
    page.setdefault("palette", {"primary": "slate", "accent": "indigo"})
    page.setdefault("links", ["/about"])
    page["seed"] = seed
    return page


def _json_from_text(text: str) -> Any:
    """Extract first {...} block from text and json.loads it."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(text[start : end + 1])


def _seeded_palette_hint(seed: int) -> Dict[str, str]:
    random.seed(seed)
    # Use the requested six-color set for both primary and accent
    colors = ["slate", "indigo", "rose", "emerald", "amber", "violet"]
    primaries = colors
    accents = colors
    return {"primary": random.choice(primaries), "accent": random.choice(accents)}


def _seeded_layout_hint(seed: int) -> str:
    random.seed(seed + 1337)
    # ~30% grid, else stack
    return "grid" if random.random() < 0.3 else "stack"


def _make_request_id() -> str:
    return f"{random.randint(0, 16**8):08x}"


def _stub_page(brief: str, seed: int) -> Dict[str, Any]:
    random.seed(seed)
    colors = ["slate", "indigo", "rose", "emerald", "amber", "violet"]
    primary = random.choice(colors)
    accent = random.choice(colors)
    # Invent a short theme when brief is empty
    themes = [
        "Indie film fest", "Eco cleaning brand", "Retro arcade", "Yoga studio",
        "Coffee roastery", "Trail running club", "AI startup", "Artisanal bakery"
    ]
    theme = brief.strip() or random.choice(themes)
    title = f"{theme} landing page"
    allowed = ["hero", "cta", "feature_grid", "testimonial", "stats", "pricing", "gallery", "text", "card_list"]
    picks = random.sample(allowed, k=random.randint(3, 5))
    comps = []
    for i, t in enumerate(picks, start=1):
        if t == "hero":
            comps.append({"id": f"hero-{i}", "type": "hero", "props": {"title": title, "subtitle": "Discover what's new"}})
        elif t == "feature_grid":
            comps.append({
                "id": f"features-{i}", "type": "feature_grid",
                "props": {
                    "title": "Highlights",
                    "features": [
                        {"title": "Fast setup", "body": "Start in minutes."},
                        {"title": "Responsive", "body": "Looks great everywhere."},
                        {"title": "Customizable", "body": "Tweak content easily."}
                    ]
                }
            })
        elif t == "cta":
            comps.append({"id": f"cta-{i}", "type": "cta", "props": {"title": "Get started", "label": "Learn more", "href": "#"}})
        elif t == "text":
            comps.append({"id": f"text-{i}", "type": "text", "props": {"title": "About", "body": "Short blurb about the project."}})
        elif t == "testimonial":
            comps.append({"id": f"testi-{i}", "type": "testimonial", "props": {"quote": "Love this demo!", "author": "Alex"}})
        elif t == "stats":
            comps.append({"id": f"stats-{i}", "type": "stats", "props": {"stats": [{"value": "24k", "label": "Users"}, {"value": "99.9%", "label": "Uptime"}]}})
        elif t == "pricing":
            comps.append({"id": f"pricing-{i}", "type": "pricing", "props": {"title": "Simple pricing", "items": [{"title": "Basic", "body": "$9/mo"}, {"title": "Pro", "body": "$29/mo"}]}})
        elif t == "gallery":
            comps.append({"id": f"gallery-{i}", "type": "gallery", "props": {"images": ["https://picsum.photos/seed/1/400/240", "https://picsum.photos/seed/2/400/240"]}})
        elif t == "card_list":
            comps.append({"id": f"cards-{i}", "type": "card_list", "props": {"items": [{"title": "Card A", "body": "Details"}, {"title": "Card B", "body": "Details"}]}})
    layout = {"flow": "grid"} if random.random() < 0.3 else {"flow": "stack"}
    return {
        "components": comps,
        "layout": layout,
        "palette": {"primary": primary, "accent": accent},
        "links": ["/about"],
        "seed": seed,
        "model_version": "v0",
    }
