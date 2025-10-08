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
    max_attempts = 3  # initial + up to 2 retries on duplicates
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
            # All providers failed for this attempt; return an error immediately
            logging.warning("All providers failed; returning error doc.")
            return {"error": "Model generation failed"}

        if not doc:
            # Transport or normalization failure — return an error immediately
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

    # If we exhausted retries, return the last doc we saw (should be valid)
    return doc or {"error": "Model generation failed"}


def _call_groq_for_page(brief: str, seed: int) -> Optional[Dict[str, Any]]:
    """Call Groq (OpenAI-compatible) and parse a page dict; None on failure."""
    temperature = TEMPERATURE
    palette_hint = _seeded_palette_hint(seed)
    layout_hint = _seeded_layout_hint(seed)

    prompt = f"""
You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}

Optional hints you may use internally (do not include them in the output):
- Palette hint: {palette_hint}
- Layout hint: {layout_hint}
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
        # If model is invalid, attempt a single fallback model
        fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
        raw = None
        try:
            raw = resp.text
        except Exception:
            raw = None
        if (
            fallback_model
            and GROQ_MODEL != fallback_model
            and ("model" in (raw or "").lower())
            and (("not found" in (raw or "").lower()) or ("invalid" in (raw or "").lower()))
        ):
            logging.warning("Groq model '%s' rejected; retrying with fallback '%s'", GROQ_MODEL, fallback_model)
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
You are an expert web designer and creative developer creating modern, visually striking websites and interactive experiences.

OUTPUT FORMAT (CRITICAL):
You must output valid JSON in one of these exact formats:
1. { "kind": "full_page_html", "html": "<!doctype html>...complete HTML document..." }
2. { "components": [{ "id": "custom-1", "type": "custom", "props": { "html": "<div>...inline HTML with <script>...</div>", "height": "100vh" }}] }

Choose format 1 for full-page experiences. Choose format 2 for embedded components. 
For full-screen experiences in format 2, set height to "100vh". For games or immersive experiences, always use full viewport height.

EXECUTION MODE (choose before coding):
* MODE A: Interactive app - User directly controls objects and behavior
* MODE B: Entertaining non-interactive - Automatically entertaining with motion/reveals (no static content)

Core Requirements:
- Create complete, functional experiences using HTML, CSS, and vanilla JavaScript only
- NO external scripts, fonts, images, or network calls allowed
- Inline all CSS and JavaScript within the HTML
- Make it fully interactive with smooth animations and engaging user experiences
- Use modern design trends: gradients, animations, hover effects, contemporary typography
- Ensure the design has personality and visual interest - avoid generic aesthetics
- For full-page experiences, use full viewport dimensions (width: 100vw, height: 100vh)

GAMES AND INTERACTIVE EXPERIENCES:
When creating games or interactive toys, FUNCTIONALITY is paramount. Follow these strict rules:

Pre-Code Verification (answer these before writing ANY game code):
1. VARIABLES: List all variables. Which are let vs const? Where declared?
2. INITIALIZATION: What is the initial value of each variable? None used before being set?
3. SCOPE: Do callbacks/timers reference variables? Are those variables in safe outer scope?
4. ANIMATION: Where is requestAnimationFrame called? (Must be inside loop function)
5. EVENTS: List each addEventListener. Which element? Does it exist at that line?
6. FIRST INTERACTION: User interacts - which handler runs, what state changes, what becomes visible within 0.5s?

Game Design Principles (CRITICAL):
- Prioritize FUNCTIONALITY and PLAYABILITY above all else
- Ensure smooth, responsive controls (target 60fps)
- ALWAYS initialize all variables before use
- Attach event listeners ONLY AFTER elements exist
- For keyboard input: addEventListener on document or auto-focus an element
- For canvas animations: MUST call clearRect(0, 0, width, height) every frame before drawing
- Animation loop pattern: clear → update(state) → draw(state) → requestAnimationFrame(loop)
- Place requestAnimationFrame INSIDE the loop function, never outside
- Use a single state object for mutable values
- Include clear UI: score display, instructions, start/restart buttons
- Test the interaction path: input → handler → state change → visual update
- For games, use full viewport: canvas or container should be width: 100vw, height: 100vh

Game Feel & Polish:
- Add satisfying feedback: sound effects (Web Audio API), particle effects, screen shake
- Smooth, responsive controls with immediate visual feedback
- Include game states: menu, playing, paused, game over
- Display score/timer/lives clearly
- Make it immediately playable - minimal tutorial needed

Forbidden Game Bugs (check before output):
- Uninitialized arrays or objects
- Listeners attached before elements exist
- Missing clearRect in canvas loops
- Undefined variable references
- Functions defined but never called
- requestAnimationFrame called outside loop function

Allowed Game Types:
- Classic arcade: Snake, Pong, Breakout, Tetris, Space Invaders (but change at least one core mechanic)
- Puzzle: Memory matching, Tic-tac-toe, Connect Four, Sliding puzzles
- Casual: Flappy Bird clones, endless runners, catch/avoid games
- Physics toys: Particle systems, gravity simulations, collision playgrounds
- Creative: Drawing apps, music makers, generative art tools

For Non-Game Websites:
- Default to bold, contemporary aesthetics
- Every interactive element needs feedback (hover, transitions, micro-animations)
- Use modern palettes: dark mode, glassmorphism, vibrant gradients
- Typography should be expressive with hierarchy
- Design should feel alive and premium, not sterile
- Make responsive where applicable
- Can use full viewport height or scroll naturally based on content needs

Technical Constraints:
- HTML, CSS, vanilla JavaScript only - NO libraries or external resources
- Canvas for game graphics when appropriate (size to full viewport for immersive experiences)
- Use CSS Grid/Flexbox for layouts
- Tailwind utility classes allowed
- Keep code organized and commented
- Remove all dead code - every function must be used
- Set appropriate dimensions: games/immersive experiences should use 100vw x 100vh

MANDATORY FINAL CHECK (before output):
1. Trace full execution path from start to first visible change
2. All variables initialized before use
3. All event listeners attached after elements exist
4. If canvas animation: clearRect called every frame, requestAnimationFrame inside loop
5. If game: test one complete interaction (input → handler → state → render)
6. Layout is visible and properly sized (full viewport for games/immersive content)
7. Output is valid JSON in the specified format with appropriate height value
8. No undefined references or missing elements

The output should feel premium and engaging from the first moment. For games: prioritize playability and smoothness. For websites: prioritize visual impact and interactivity.

Topic: [USER'S WEBSITE REQUEST]
"""

# Removed Gemini provider support completely


def _call_openrouter_for_page(brief: str, seed: int) -> Optional[Dict[str, Any]]:
    """Call OpenRouter Chat Completions and parse a page dict; None on failure."""
    temperature = TEMPERATURE
    palette_hint = _seeded_palette_hint(seed)
    layout_hint = _seeded_layout_hint(seed)

    prompt = f"""
You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{_PAGE_SHAPE_HINT}

Optional hints you may use internally (do not include them in the output):
- Palette hint: {palette_hint}
- Layout hint: {layout_hint}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "non-deterministic-website",
    }
    # Heuristic: only some providers support OpenAI-style JSON mode. Use conservatively for OpenAI‑compatible models.
    def _supports_json_mode(model: str) -> bool:
        m = (model or "").lower()
        return m.startswith("openai/") or "gpt-" in m or m.startswith("openrouter/"
            )  

    wants_json_mode = _supports_json_mode(OPENROUTER_MODEL)

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
        if wants_json_mode and "JSON mode is not enabled" in (txt or ""):
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
        logging.warning("OpenRouter: empty response text")
        return None

    try:
        page = _json_from_text(text)
    except Exception as e:
        logging.warning("OpenRouter: failed to extract JSON: %r", e)
        return None

    try:
        norm = _normalize_doc(page)
        if isinstance(norm, dict):
            return norm
    except Exception as e:
        logging.warning("OpenRouter: normalization error: %r", e)
    return None


def _json_from_text(text: str) -> Any:
    """Extract JSON object from text with several fallbacks; raise on failure.

    Order:
    - Try strict json.loads on the first balanced {...} block (brace-matching aware of strings).
    - Try code-fenced blocks ```json ... ```.
    - Try sanitization (strip trailing commas, normalize quotes) on the candidate block.
    - If text looks like raw HTML (<!doctype or <html or <div ...>), wrap it into a full_page_html doc.
    """
    t = text.strip()
    if t.lower().lstrip().startswith("<!doctype") or t.lower().lstrip().startswith("<html") or t.lower().lstrip().startswith("<div"):
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
        candidate = _balanced_json_slice(t)

    if not candidate:
        raise ValueError("No JSON object found")

    def _try_load(s: str) -> Any:
        return json.loads(s)

    try:
        return _try_load(candidate)
    except Exception:
        # Sanitization: strip trailing commas before } or ] and normalize smart quotes
        s = re.sub(r",\s*([}\]])", r"\1", candidate)
        s = s.replace("“", '"').replace("”", '"').replace("’", "'")
        return _try_load(s)


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
    # Components list or single object
    comps = doc.get("components")
    if isinstance(comps, dict):
        comps = [comps]
    if isinstance(comps, list):
        for c in comps:
            if not isinstance(c, dict):
                continue
            props = c.get("props") or {}
            # tolerate html at component root
            html = props.get("html") if isinstance(props, dict) else None
            if not (isinstance(html, str) and html.strip()):
                html = c.get("html") if isinstance(c.get("html"), str) else None
            if isinstance(html, str) and html.strip():
                height = props.get("height") if isinstance(props, dict) else c.get("height")
                try:
                    h = int(height) if height is not None else 360
                except Exception:
                    h = 360
                return {
                    "components": [
                        {
                            "id": str(c.get("id") or "custom-1"),
                            "type": "custom",
                            "props": {"html": html, "height": h},
                        }
                    ]
                }
    # Fallback: scan shallowly for any HTML-looking string
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
