from __future__ import annotations
import json
import logging
import os
import random
from typing import Any, Dict, Optional
import requests
from api import dedupe
log = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3n-e2b-it:free").strip()
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
FORCE_OPENROUTER_ONLY = os.getenv("FORCE_OPENROUTER_ONLY", "0").lower() in {"1", "true", "yes", "on"}

# Groq (OpenAI-compatible) primary provider
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

try:
    TEMPERATURE = float(os.getenv("TEMPERATURE", "1.35"))
except Exception:
    TEMPERATURE = 1.35

# Token and timeout configuration
# Defaults favor longer generations; adjust via .env if provider rejects
try:
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "15000"))
except Exception:
    LLM_MAX_TOKENS = 15000
try:
    OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", str(LLM_MAX_TOKENS)))
except Exception:
    OPENROUTER_MAX_TOKENS = LLM_MAX_TOKENS
try:
    LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "75"))
except Exception:
    LLM_TIMEOUT_SECS = 75
try:
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", str(LLM_MAX_TOKENS)))
except Exception:
    GROQ_MAX_TOKENS = LLM_MAX_TOKENS
"""
This module now only calls the LLM. No local library or stub fallbacks.
If generation fails, we return {"error": "..."} and the API returns 200 with that body,
or 503 earlier in the /generate endpoint if credentials are missing.
"""

def status() -> Dict[str, Any]:
    if GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
        return {
            "provider": "groq",
            "model": GROQ_MODEL,
            "has_token": True,
            "using": "groq",
        }
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {
            "provider": "openrouter",
            "model": OPENROUTER_MODEL,
            "has_token": bool(OPENROUTER_API_KEY),
            "using": "openrouter",
        }
    return {
        "provider": None,
        "model": None,
        "has_token": False,
        "using": "stub",
    }


def probe() -> Dict[str, Any]:
    if GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
        return {"ok": True, "using": "groq"}
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {"ok": bool(OPENROUTER_API_KEY), "using": "openrouter"}
    return {"ok": False, "using": "stub"}


def generate_page(brief: str, seed: int) -> Dict[str, Any]:
    """Return a doc in one of the two accepted shapes or {error}.

    Behaviors:
    - Empty or auto brief lets the model invent a theme.
    - Seed only used for palette/layout hinting; not required.
    """
    auto_cues = {"", "auto", "random", "surprise me"}
    brief_str = (brief or "").strip()
    is_auto = brief_str.lower() in auto_cues
    if not brief_str or is_auto:
        brief_str = ""  
    seed_val = int(seed or 0)
    if not seed_val:
        seed_val = random.randint(1, 10_000_000)

    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        attempts += 1
        doc: Optional[Dict[str, Any]] = None
        providers: list[str] = []
        if GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
            providers.append("groq")
        if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
            providers.append("openrouter")
        logging.warning("llm providers_order=%s force_openrouter_only=%s", providers, FORCE_OPENROUTER_ONLY)
        for p in providers:
            logging.warning("llm attempting provider=%s", p)
            if p == "groq":
                doc = _call_groq_for_page(brief_str, seed_val)
            elif p == "openrouter":
                doc = _call_openrouter_for_page(brief_str, seed_val)
            if doc:
                logging.warning("llm chosen provider=%s", p)
                break
        if not doc:
            logging.warning("All providers failed; returning error doc.")
            return {"error": "Model generation failed"}

        if not doc:
            logging.warning("Model call failed or returned invalid JSON; returning error doc.")
            return {"error": "Model generation failed"}

        sig = dedupe.signature_for_doc(doc)
        if sig and dedupe.has(sig):
            logging.info("Duplicate app signature encountered; retrying another generation (attempt %d)", attempts)
            seed_val = (seed_val + 7919) % 10_000_019
            continue

        # Unique enough; record and return
        if sig:
            dedupe.add(sig)
        return doc

    return doc or {"error": "Model generation failed"}


def _call_groq_for_page(brief: str, seed: int) -> Optional[Dict[str, Any]]:
    """Call Groq (OpenAI-compatible) and parse a page dict; None on failure."""
    temperature = TEMPERATURE

    prompt = f"""
You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": max(1.1, min(1.3, float(temperature))),
        "top_p": 0.95,
        "max_tokens": GROQ_MAX_TOKENS,
    }
    # Try JSON mode if supported; retry without on 400
    wants_json_mode = True
    body_with_json = dict(body)
    body_with_json["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(GROQ_ENDPOINT, headers=headers, json=body_with_json, timeout=LLM_TIMEOUT_SECS)
    except Exception as e:
        logging.warning("Groq request error: %r", e)
        return None

    if resp.status_code == 400:
        # Retry without json mode
        try:
            resp = requests.post(GROQ_ENDPOINT, headers=headers, json=body, timeout=LLM_TIMEOUT_SECS)
        except Exception as e:
            logging.warning("Groq retry (no json mode) error: %r", e)
            return None

    if resp.status_code != 200:
        # Attempt a single fallback model on common failure modes
        fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
        raw = None
        try:
            raw = resp.text
        except Exception:
            raw = None

        lower = (raw or "").lower()
        should_try_fallback = False
        reason = None
        # 1) Explicit model issues (invalid/not found)
        if ("model" in lower) and (("not found" in lower) or ("invalid" in lower)):
            should_try_fallback = True
            reason = "model rejected"
        # 2) Rate limited — try a different model if configured
        elif resp.status_code == 429:
            should_try_fallback = True
            reason = "rate limited"

        if fallback_model and GROQ_MODEL != fallback_model and should_try_fallback:
            logging.warning("Groq model '%s' %s; retrying with fallback '%s'", GROQ_MODEL, reason or "failed", fallback_model)
            body_fallback = dict(body)
            body_fallback["model"] = fallback_model
            try:
                resp_fb = requests.post(GROQ_ENDPOINT, headers=headers, json=body_fallback, timeout=LLM_TIMEOUT_SECS)
            except Exception as e:
                logging.warning("Groq fallback model request error: %r", e)
                return None
            if resp_fb.status_code != 200:
                try:
                    msg = resp_fb.text[:400]
                except Exception:
                    msg = str(resp_fb.status_code)
                logging.warning("Groq HTTP %s after fallback: %s", resp_fb.status_code, msg)
                return None
            # Use fallback response as success
            resp = resp_fb
        else:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Groq HTTP %s: %s", resp.status_code, msg)
            return None

    try:
        data = resp.json()
    except Exception:
        logging.warning("Groq: non-JSON HTTP body")
        return None

    text: Optional[str]
    try:
        text = (data.get("choices", [{}])[0].get("message", {}).get("content"))
    except Exception:
        text = None
    if not text or not isinstance(text, str):
        logging.warning("Groq: empty response text")
        return None

    try:
        page = _json_from_text(text)
    except Exception as e:
        logging.warning("Groq: failed to extract JSON: %r", e)
        return None

    try:
        norm = _normalize_doc(page)
        if isinstance(norm, dict):
            return norm
    except Exception as e:
        logging.warning("Groq: normalization error: %r", e)
    return None




_PAGE_SHAPE_HINT = """
Output valid JSON only. No markdown fences.

FORMATS (prefer #1):
1. {"kind":"ndw_snippet_v1","title":"...","background":{"style":"css","class":""},"css":"...","html":"...","js":"..."}
2. {"kind":"full_page_html","html":"<!doctype html>..."}
3. {"components":[{"id":"x","type":"custom","props":{"html":"...","height":360}}]}

RUNTIME (snippet only):
window.NDW provides:
- NDW.loop((dt) => ...) → dt in milliseconds since last frame
  CRITICAL: dt is passed as parameter. DO NOT manually track time (no lastTime=Date.now() or NDW.time.elapsed).
  Physics: velocity += accel * (dt/1000); position += velocity * (dt/1000);
  Example: NDW.loop((dt) => { update(dt/1000); draw(); });
- NDW.makeCanvas({fullScreen,width,height,parent,dpr}) → returns canvas element with .ctx, .dpr
  Usage: const canvas = NDW.makeCanvas({fullScreen:true}); const ctx = canvas.ctx;
  Dimensions: canvas.width, canvas.height (NOT canvas.canvas.width)
- NDW.onKey((e) => ...) → e is KeyboardEvent; check e.key ('ArrowUp', 'w', ' ', etc.)
    Register once, outside the loop. Do NOT reference dt inside the handler; use NDW.isDown inside NDW.loop for continuous input.
- NDW.onPointer((e) => ...) → e = {x, y, down, type, raw}
    Attach once outside the loop; inside handler mutate state flags. Pointer listeners inside NDW.loop will multiply events.
- NDW.isDown(key) → true if key pressed; works for 'ArrowUp', 'w', 'Space', 'mouse'
- NDW.onResize(() => ...)
- NDW.utils: clamp(v,min,max), lerp(a,b,t), rng(seed), hash(seed)
    rng(seed) returns a GENERATOR FUNCTION. Call it once to get a PRNG: const rand = NDW.utils.rng(seed); const value = rand();
    Shortcut: rand.valueOf() is overloaded, so rand * 1 also yields the next random, but prefer rand().
- NDW.pointer: {x,y,down}

RULES:
- NO external resources (scripts/fonts/images/fetch)
- NO manual time tracking (never use Date.now(), performance.now(), or NDW.time.elapsed for dt calculation)
- Initialize ALL state BEFORE NDW.loop() call
- Register event listeners (NDW.onKey / NDW.onPointer) BEFORE NDW.loop(); never define them inside the loop callback.
- Never chain NDW.* calls onto other expressions (no `.NDW`). Call each NDW method as its own statement terminated with a semicolon.
- Rotate categories so consecutive generations feel different. If the last request was a space shooter (Asteroids, etc.), pick a different genre or medium next.
- Include clear, readable instructions or context for the user in the HTML outside the canvas.
- Inline all CSS/JS
- For snippets: host provides #ndw-app; don't wrap another
- For canvas: NDW.makeCanvas auto-appends; clearRect(0,0,canvas.width,canvas.height) each frame
- Physics with dt parameter: v += a*(dt/1000); p += v*(dt/1000); (dt is milliseconds, convert to seconds)
- Title: include and use it (draw on canvas or small UI label)
- Do not prefix output HTML with stray characters; the host injects it directly.

CONTROLS:
- Keyboard discrete: NDW.onKey((e) => { if(e.key==='ArrowUp') jump(); });
- Keyboard continuous: if(NDW.isDown('ArrowLeft')) x -= speed*(dt/1000);
- Mouse/touch: NDW.onPointer((e) => { if(e.down) shoot(e.x, e.y); });
- Mouse pressed: if(NDW.isDown('mouse')) dragObject();

CHOOSE ONE TYPE (rotate variety; avoid repeating same category):
1. GAMES: ping pong, snake, tic tac toe, brick breaker, flappy bird, space invaders, memory match, connect four, tetris, asteroids
   - Initialize state (score=0, pos, vel) BEFORE NDW.loop
   - Pattern: NDW.loop((dt) => { ctx.clearRect(0,0,w,h); update(dt/1000); draw(); });
   - Physics: v += a*(dt/1000); p += v*(dt/1000); (dt in ms, convert to seconds)
    - Controls: NDW.onKey handlers toggle flags; NDW.isDown inside NDW.loop applies movement (no dt in handlers)
    - Provide on-screen instructions (controls, goals) and simple UI elements (score, lives, title) using HTML/CSS.
   - Full viewport for immersion
2. WEBSITES: landing page, portfolio, blog/article, product feature, pricing table, about/contact, gallery, FAQ, testimonials, dashboard, form
    - Use rich HTML+CSS sections (hero, features, CTA) with headings, paragraphs, buttons, and imagery styles.
    - Avoid relying solely on a canvas; craft a complete webpage layout.
3. INTERACTIVE ART: particles, flow fields, boids, cellular automata, noise field, kaleidoscope, gradient morph
   - Canvas pattern: const canvas=NDW.makeCanvas({fullScreen:true}); const ctx=canvas.ctx;
     - Initialize particle arrays BEFORE loop. Generate randoms via const rand = NDW.utils.rng(seed); const x = rand();
     - Auto-motion or pointer-reactive; ensure visible activity within 1s
      - Pointer handlers belong outside NDW.loop; inside the loop read NDW.pointer.
      - Add a short descriptive caption in HTML explaining the concept or interaction.

CANONICAL GAME TEMPLATE:
const canvas = NDW.makeCanvas({ fullScreen: true });
const ctx = canvas.ctx;
const rand = NDW.utils.rng(seed);
let state = { x: 0, vx: 0 };

NDW.onKey((e) => {
    if (e.key === 'ArrowLeft') state.vx = -1;
    if (e.key === 'ArrowRight') state.vx = 1;
});

NDW.loop((dt) => {
    const seconds = dt / 1000;
    state.x += state.vx * seconds * 200;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillRect(state.x, canvas.height - 40, 40, 20);
});

OUTPUT CHECKLIST:
✓ Valid JSON in format #1, #2, or #3
✓ Title present (if snippet) and used; or omit cleanly
✓ All vars initialized; listeners after DOM ready
✓ Canvas: clearRect called; rAF inside loop fn
✓ No undefined refs or missing elements
"""

# Removed Gemini provider support completely


def _call_openrouter_for_page(brief: str, seed: int) -> Optional[Dict[str, Any]]:
    """Call OpenRouter Chat Completions and parse a page dict; None on failure."""
    temperature = TEMPERATURE

    prompt = f"""
You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "non-deterministic-website",
    }
    # Prefer JSON mode first; if rejected by provider, we'll retry without it.
    wants_json_mode = True

    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": max(1.1, min(1.3, float(temperature))),
        "top_p": 0.95,
        "max_tokens": OPENROUTER_MAX_TOKENS,
    }
    if wants_json_mode:
        body["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=body, timeout=LLM_TIMEOUT_SECS)
    except Exception as e:
        logging.warning("OpenRouter request error: %r", e)
        return None

    if resp.status_code != 200:
        # If JSON mode not supported, retry once without response_format
        txt = None
        try:
            txt = resp.text
        except Exception:
            txt = None
        msg = (txt or "")[:400]
        if wants_json_mode and ("JSON mode is not enabled" in (txt or "") or "response_format" in (txt or "")):
            try:
                body.pop("response_format", None)
                resp = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=body, timeout=LLM_TIMEOUT_SECS)
            except Exception as e:
                logging.warning("OpenRouter retry (no json mode) error: %r", e)
                return None
            if resp.status_code != 200:
                try:
                    msg = resp.text[:400]
                except Exception:
                    msg = str(resp.status_code)
                logging.warning("OpenRouter HTTP %s after retry: %s", resp.status_code, msg)
                return None
        else:
            logging.warning("OpenRouter HTTP %s: %s", resp.status_code, msg)
            return None

    try:
        data = resp.json()
    except Exception:
        logging.warning("OpenRouter: non-JSON HTTP body")
        return None

    try:
        text = (data.get("choices", [{}])[0].get("message", {}).get("content"))
    except Exception:
        text = None
    if not text or not isinstance(text, str):
        try:
            text = resp.text
        except Exception:
            text = None
        if not text or not isinstance(text, str):
            logging.warning("OpenRouter: empty response text")
            return None

    try:
        page = _json_from_text(text)
    except Exception as e:
        logging.warning("OpenRouter: failed to extract JSON/HTML: %r", e)
        tl = (text or "")
        if isinstance(tl, str) and ("<html" in tl.lower() or "<!doctype" in tl.lower() or "<div" in tl.lower() or "<body" in tl.lower()):
            page = {"kind": "full_page_html", "html": tl}
        else:
            return None

    try:
        norm = _normalize_doc(page)
        if isinstance(norm, dict):
            return norm
    except Exception as e:
        logging.warning("OpenRouter: normalization error: %r", e)
    return None


def _json_from_text(text: str) -> Any:
    """Extract JSON object or HTML from text with robust fallbacks; raise on failure.

    Strategy:
    - If text starts with HTML tags, wrap as full_page_html.
    - Try fenced blocks: ```json ...``` first, then any ``` ... ```.
    - Try first balanced {...} object (brace-aware in presence of strings).
    - Sanitize: remove trailing commas, normalize smart quotes.
    - If any HTML-like tag appears anywhere, wrap remaining text as full_page_html.
    """
    t = (text or "").strip()
    tl = t.lower().lstrip()
    if tl.startswith("<!doctype") or tl.startswith("<html") or tl.startswith("<div") or tl.startswith("<body"):
        return {"kind": "full_page_html", "html": t}

    def _balanced_json_slice(s: str) -> Optional[str]:
        in_str = False
        esc = False
        depth = 0
        start_idx = -1
        for i, ch in enumerate(s):
            if not in_str and ch == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif not in_str and ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        return s[start_idx:i+1]
            elif ch == '"':
                if not esc:
                    in_str = not in_str
                esc = False
                continue
            esc = (ch == '\\') and not esc
        return None

    import re
    m = re.search(r"```json\s*([\s\S]*?)```", t, re.IGNORECASE)
    candidate = None
    if m:
        candidate = m.group(1)
    else:
        m2 = re.search(r"```\s*([\s\S]*?)```", t)
        if m2:
            candidate = m2.group(1)
    if not candidate:
        candidate = _balanced_json_slice(t)

    def _try_load(s: str) -> Any:
        return json.loads(s)

    if candidate:
        try:
            return _try_load(candidate)
        except Exception:
            s = re.sub(r",\s*([}\]])", r"\1", candidate)
            s = s.replace("“", '"').replace("”", '"').replace("’", "'")
            try:
                return _try_load(s)
            except Exception:
                pass

    # Last resort: if any HTML-like tag appears anywhere, wrap as full_page_html
    if re.search(r"<\s*(?:!doctype|html|body|div|section|canvas|main)\b", t, re.IGNORECASE):
        return {"kind": "full_page_html", "html": t}
    raise ValueError("No JSON or HTML content found")


def _seeded_palette_hint(seed: int) -> Dict[str, str]:
    random.seed(seed)
    colors = ["slate", "indigo", "rose", "emerald", "amber", "violet", "cyan"]
    primaries = colors
    accents = colors
    return {"primary": random.choice(primaries), "accent": random.choice(accents)}

def _seeded_layout_hint(seed: int) -> str:
    random.seed(seed + 1337)
    return "grid" if random.random() < 0.3 else "stack"

def _make_request_id() -> str:
    return f"{random.randint(0, 16**8):08x}"



def _normalize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model output to one of the accepted shapes or raise ValueError."""
    if not isinstance(doc, dict):
        raise ValueError("not a dict")
    if isinstance(doc.get("error"), str):
        return {"error": str(doc["error"])[:500]}
    # Inference: if no explicit kind/components but looks like a snippet payload, coerce
    if ("html" in doc or "css" in doc or "js" in doc) and not (doc.get("components") or doc.get("kind") or doc.get("type")):
        doc = {"kind": "ndw_snippet_v1", **{k: v for k, v in doc.items() if k in {"title","background","css","html","js"}}}
    # Accept the new compact snippet format directly
    kind = str(doc.get("kind") or doc.get("type") or "").lower()
    # Tolerate common synonyms for snippet kind
    if kind in {"ndw_snippet", "snippet_v1", "ndw-canvas-snippet", "canvas_snippet", "canvas-snippet"}:
        kind = "ndw_snippet_v1"
    if kind == "ndw_snippet_v1":
        # Validate minimal fields, coerce to expected keys
        out: Dict[str, Any] = {"kind": "ndw_snippet_v1"}
        if isinstance(doc.get("title"), str):
            out["title"] = doc["title"]
        bg = doc.get("background")
        if isinstance(bg, dict):
            out_bg: Dict[str, Any] = {}
            sty = bg.get("style")
            if isinstance(sty, list):
                sty = "; ".join([s for s in sty if isinstance(s, str)])
            if isinstance(sty, str) and sty.strip():
                import re
                sty = re.sub(r"^\s*background\s*:\s*", "", sty, flags=re.IGNORECASE)
                out_bg["style"] = sty
            cls = bg.get("class") or bg.get("className") or bg.get("classes")
            if isinstance(cls, list):
                cls = " ".join([c for c in cls if isinstance(c, str)])
            if isinstance(cls, str) and cls.strip():
                out_bg["class"] = cls
            if out_bg:
                out["background"] = out_bg
        css = doc.get("css"); html = doc.get("html"); js = doc.get("js")
        if isinstance(css, str) and css.strip():
            out["css"] = css
        if isinstance(html, str) and html.strip():
            out["html"] = html
        if isinstance(js, str) and js.strip():
            out["js"] = js
        if not out.get("html"):
            # If no HTML provided, attempt to derive from any nested structure
            for k in ("content", "body", "markup"):
                v = doc.get(k)
                if isinstance(v, str) and ("<" in v and ">" in v):
                    out["html"] = v
                    break
        if not out.get("html") and not out.get("css") and not out.get("js"):
            raise ValueError("ndw_snippet_v1 missing content")
        return out
    # Accept common variants/synonyms for full-page HTML
    for key in ("kind", "type"):
        k = str(doc.get(key) or "").lower()
        if k in {"full_page_html", "page_html", "html_page", "full_html"}:
            html = doc.get("html") or doc.get("content") or doc.get("body")
            if isinstance(html, str) and html.strip():
                return {"kind": "full_page_html", "html": html}
    if isinstance(doc.get("html"), str) and doc["html"].strip():
        return {"kind": "full_page_html", "html": doc["html"]}
    for key in ("content", "body", "page", "app", "markup"):
        val = doc.get(key)
        if isinstance(val, str) and ("<" in val and ">" in val):
            return {"kind": "full_page_html", "html": val}
        if isinstance(val, dict) and isinstance(val.get("html"), str):
            return {"kind": "full_page_html", "html": val.get("html")}
    comps = doc.get("components")
    if isinstance(comps, dict):
        comps = [comps]
    if isinstance(comps, list):
        for c in comps:
            if not isinstance(c, dict):
                continue
            props = c.get("props") or {}
            html = props.get("html") if isinstance(props, dict) else None
            if not (isinstance(html, str) and html.strip()):
                html = c.get("html") if isinstance(c.get("html"), str) else None
            if isinstance(html, str) and html.strip():
                height = props.get("height") if isinstance(props, dict) else c.get("height")
                # Attempt to coerce string heights like "100vh" to a reasonable pixel default
                try:
                    h = int(height) if height is not None else 360
                except Exception:
                    # If string like "100vh", fall back to a tall default
                    h = 720
                return {
                    "components": [
                        {
                            "id": str(c.get("id") or "custom-1"),
                            "type": "custom",
                            "props": {"html": html, "height": h},
                        }
                    ]
                }
    def _find_html(obj: Any, depth: int = 0) -> Optional[str]:
        if depth > 2:
            return None
        if isinstance(obj, str) and ("<" in obj and ">" in obj) and len(obj) > 20:
            return obj
        if isinstance(obj, dict):
            for v in obj.values():
                found = _find_html(v, depth + 1)
                if found:
                    return found
        if isinstance(obj, list):
            for v in obj:
                found = _find_html(v, depth + 1)
                if found:
                    return found
        return None
    html_any = _find_html(doc)
    if html_any:
        return {"kind": "full_page_html", "html": html_any}
    raise ValueError("No renderable HTML found")
