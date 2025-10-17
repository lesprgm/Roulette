from __future__ import annotations
import json
import logging
import os
import random
import re
import subprocess
import threading
import time
from typing import Any, Dict, Optional, Tuple, List
import requests
from api import dedupe


def _testing_stub_enabled() -> bool:
    """Return True when pytest is running and keys match the original environment values."""
    if not os.getenv("PYTEST_CURRENT_TEST"):
        return False
    if os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}:
        return False
    if OPENROUTER_API_KEY != _ENV_OPENROUTER_API_KEY:
        return False
    if GROQ_API_KEY != _ENV_GROQ_API_KEY:
        return False
    return True
log = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3n-e2b-it:free").strip()
OPENROUTER_FALLBACK_MODEL_1 = os.getenv("OPENROUTER_FALLBACK_MODEL_1", "x-ai/grok-4-fast").strip()
OPENROUTER_FALLBACK_MODEL_2 = os.getenv("OPENROUTER_FALLBACK_MODEL_2", "deepseek/deepseek-chat-v3.1:free").strip()
_ENV_OPENROUTER_API_KEY = OPENROUTER_API_KEY
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
FORCE_OPENROUTER_ONLY = os.getenv("FORCE_OPENROUTER_ONLY", "0").lower() in {"1", "true", "yes", "on"}

# Groq (OpenAI-compatible) fallback provider
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
_ENV_GROQ_API_KEY = GROQ_API_KEY
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

_OPENROUTER_BACKOFF_LOCK = threading.Lock()
_OPENROUTER_BACKOFF_UNTIL = 0.0
_OPENROUTER_BACKOFF_DELAY = 0.0
try:
    _OPENROUTER_BACKOFF_INITIAL = float(os.getenv("OPENROUTER_BACKOFF_INITIAL", "3.0") or 3.0)
except Exception:
    _OPENROUTER_BACKOFF_INITIAL = 3.0
try:
    _OPENROUTER_BACKOFF_MAX = float(os.getenv("OPENROUTER_BACKOFF_MAX", "45.0") or 45.0)
except Exception:
    _OPENROUTER_BACKOFF_MAX = 45.0
_OPENROUTER_BACKOFF_FACTOR = 1.5


_SCRIPT_RE = re.compile(r"<script([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)



def _openrouter_sleep_if_needed() -> None:
    now = time.time()
    wait_for = 0.0
    with _OPENROUTER_BACKOFF_LOCK:
        if _OPENROUTER_BACKOFF_UNTIL > now:
            wait_for = _OPENROUTER_BACKOFF_UNTIL - now
    if wait_for > 0:
        logging.info("OpenRouter backoff active; waiting %.2fs before next request", wait_for)
        try:
            time.sleep(min(wait_for, _OPENROUTER_BACKOFF_MAX))
        except Exception:
            pass


def _openrouter_register_rate_limit(retry_after: Optional[str]) -> None:
    delay = None
    if retry_after:
        try:
            delay = float(retry_after)
        except Exception:
            delay = None
    global _OPENROUTER_BACKOFF_DELAY, _OPENROUTER_BACKOFF_UNTIL
    with _OPENROUTER_BACKOFF_LOCK:
        base = _OPENROUTER_BACKOFF_DELAY or _OPENROUTER_BACKOFF_INITIAL
        if delay is None:
            delay = base * _OPENROUTER_BACKOFF_FACTOR
        delay = max(_OPENROUTER_BACKOFF_INITIAL, min(delay, _OPENROUTER_BACKOFF_MAX))
        _OPENROUTER_BACKOFF_DELAY = delay
        _OPENROUTER_BACKOFF_UNTIL = time.time() + delay
        logging.warning("OpenRouter rate limited; backing off for %.2fs", delay)


def _openrouter_reset_backoff() -> None:
    global _OPENROUTER_BACKOFF_DELAY, _OPENROUTER_BACKOFF_UNTIL
    with _OPENROUTER_BACKOFF_LOCK:
        _OPENROUTER_BACKOFF_DELAY = 0.0
        _OPENROUTER_BACKOFF_UNTIL = 0.0


def _extract_inline_scripts(html: str) -> List[str]:
    blocks: List[str] = []
    if not isinstance(html, str) or not html:
        return blocks
    for match in _SCRIPT_RE.findall(html):
        attrs, body = match
        attrs = attrs or ""
        if "src=" in attrs.lower():
            continue
        if body and body.strip():
            blocks.append(body)
    return blocks


def _collect_js_blocks(doc: Dict[str, Any]) -> List[str]:
    blocks: List[str] = []
    if not isinstance(doc, dict):
        return blocks
    kind = doc.get("kind")
    if kind == "ndw_snippet_v1":
        js = doc.get("js")
        if isinstance(js, str) and js.strip():
            blocks.append(js)
        html = doc.get("html")
        if isinstance(html, str):
            blocks.extend(_extract_inline_scripts(html))
    elif kind == "full_page_html":
        html = doc.get("html")
        if isinstance(html, str):
            blocks.extend(_extract_inline_scripts(html))
    if isinstance(doc.get("components"), list):
        for comp in doc["components"]:
            if not isinstance(comp, dict):
                continue
            props = comp.get("props")
            if isinstance(props, dict):
                html = props.get("html")
                if isinstance(html, str):
                    blocks.extend(_extract_inline_scripts(html))
    return [b for b in blocks if b.strip()]


def _first_js_syntax_error(doc: Dict[str, Any]) -> Optional[str]:
    blocks = _collect_js_blocks(doc)
    if not blocks:
        return None
    for block in blocks:
        script = f"new Function({json.dumps(block)});"
        try:
            result = subprocess.run(
                ["node", "-e", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None
        except Exception as exc:
            logging.debug("JS syntax check unexpected error: %r", exc)
            return None
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "JS syntax error").strip()
            return err.splitlines()[0]
    return None

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
_openrouter_max_tokens_raw = os.getenv("OPENROUTER_MAX_TOKENS", "").strip()
if _openrouter_max_tokens_raw:
    try:
        OPENROUTER_MAX_TOKENS = int(_openrouter_max_tokens_raw)
    except Exception:
        OPENROUTER_MAX_TOKENS = None
else:
    OPENROUTER_MAX_TOKENS = None
try:
    LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "75"))
except Exception:
    LLM_TIMEOUT_SECS = 75
try:
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", str(LLM_MAX_TOKENS)))
except Exception:
    GROQ_MAX_TOKENS = LLM_MAX_TOKENS

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_REVIEW_MODEL = os.getenv("GEMINI_REVIEW_MODEL", "gemini-1.5-flash-latest").strip()
GEMINI_REVIEW_ENABLED = os.getenv("GEMINI_REVIEW_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
GEMINI_REVIEW_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_REVIEW_MODEL}:generateContent"
    if GEMINI_REVIEW_MODEL
    else ""
)
"""
This module now only calls the LLM. No local library or stub fallbacks.
If generation fails, we return {"error": "..."} and the API returns 200 with that body,
or 503 earlier in the /generate endpoint if credentials are missing.
"""

def status() -> Dict[str, Any]:
    reviewer = "gemini" if _gemini_review_active() else None
    if _testing_stub_enabled():
        return {
            "provider": None,
            "model": None,
            "has_token": False,
            "using": "stub",
            "testing": True,
            "reviewer": reviewer,
        }
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {
            "provider": "openrouter",
            "model": OPENROUTER_MODEL,
            "has_token": bool(OPENROUTER_API_KEY),
            "using": "openrouter",
            "reviewer": reviewer,
        }
    if GROQ_API_KEY:
        return {
            "provider": "groq",
            "model": GROQ_MODEL,
            "has_token": True,
            "using": "groq",
            "reviewer": reviewer,
        }
    return {
        "provider": None,
        "model": None,
        "has_token": False,
        "using": "stub",
        "reviewer": reviewer,
    }


def probe() -> Dict[str, Any]:
    if _testing_stub_enabled():
        return {"ok": False, "using": "stub", "testing": True}
    if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
        return {"ok": bool(OPENROUTER_API_KEY), "using": "openrouter"}
    if GROQ_API_KEY:
        return {"ok": True, "using": "groq"}
    return {"ok": False, "using": "stub"}


def generate_page(brief: str, seed: int, user_key: Optional[str] = None, run_review: bool = True) -> Dict[str, Any]:
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

    category_note = _next_category_note(user_key)

    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        attempts += 1
        doc: Optional[Dict[str, Any]] = None
        providers: list[str] = []
        if OPENROUTER_API_KEY or FORCE_OPENROUTER_ONLY:
            providers.append("openrouter")
        if GROQ_API_KEY and not FORCE_OPENROUTER_ONLY:
            providers.append("groq")
        logging.warning("llm providers_order=%s force_openrouter_only=%s", providers, FORCE_OPENROUTER_ONLY)
        for p in providers:
            logging.warning("llm attempting provider=%s", p)
            if p == "groq":
                doc = _call_groq_for_page(brief_str, seed_val, category_note)
            elif p == "openrouter":
                doc = _call_openrouter_for_page(brief_str, seed_val, category_note)
            if doc:
                logging.warning("llm chosen provider=%s", p)
                break
        if not doc:
            logging.warning("All providers failed; returning error doc.")
            return {"error": "Model generation failed"}

        if not doc:
            logging.warning("Model call failed or returned invalid JSON; returning error doc.")
            return {"error": "Model generation failed"}

        skip_dedupe = bool(os.getenv("PYTEST_CURRENT_TEST"))
        sig = "" if skip_dedupe else dedupe.signature_for_doc(doc)
        if sig and dedupe.has(sig):
            logging.info("Duplicate app signature encountered; retrying another generation (attempt %d)", attempts)
            doc = None
            seed_val = (seed_val + 7919) % 10_000_019
            continue

        if run_review:
            review_data, corrected_doc, review_ok = _maybe_run_compliance_review(doc, brief_str, category_note)
            if corrected_doc is not None:
                doc = corrected_doc
                logging.info("Compliance review applied corrections to doc (attempt %d)", attempts)
            if review_data:
                doc = dict(doc)
                doc["review"] = review_data
                logging.info(
                    "Compliance review summary ok=%s issues=%s",
                    review_data.get("ok"),
                    len(review_data.get("issues", [])),
                )
            if not review_ok:
                logging.info("Compliance review rejected doc; retrying another generation (attempt %d)", attempts)
                doc = None
                seed_val = (seed_val + 7919) % 10_000_019
                continue
        js_error = _first_js_syntax_error(doc)
        if js_error:
            logging.warning("JS syntax validation failed (attempt %d): %s", attempts, js_error)
            doc = None
            seed_val = (seed_val + 7919) % 10_000_019
            continue
        final_sig = ""
        if not skip_dedupe:
            final_sig = dedupe.signature_for_doc(doc)
            if final_sig and dedupe.has(final_sig):
                duplicate_msg = "Compliance-adjusted doc duplicate" if run_review else "Unreviewed doc duplicate"
                logging.info("%s; retrying another generation (attempt %d)", duplicate_msg, attempts)
                doc = None
                seed_val = (seed_val + 7919) % 10_000_019
                continue
        if final_sig:
            dedupe.add(final_sig)
        return doc

    return doc or {"error": "Model generation failed"}


def _call_groq_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call Groq (OpenAI-compatible) and parse a page dict; None on failure."""
    temperature = TEMPERATURE

    prompt = f"""
You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{category_note}

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

FORMATS (prefer #2 for websites/quizzes; only use snippets/components when absolutely necessary):
1. {"kind":"ndw_snippet_v1","title":"...","background":{"style":"css","class":""},"css":"...","html":"...","js":"..."}  ← only use when a self-contained widget fits within the host page.
2. {"kind":"full_page_html","html":"<!doctype html>..."}  ← preferred shape; include complete <head>, <body>, semantic sections, and inline CSS/JS.
3. {"components":[{"id":"hero","type":"custom","props":{"html":"...","height":360}}]}  ← only when multiple iframe-style embeds are unavoidable; ensure each component supplies props.html and props.height (px number).

GENERAL RULES:
- No external resources (scripts/fonts/images/fetch); inline all CSS/JS.
- Output HTML without stray prefixes; host injects it directly.
- Provide clear instructions in the HTML (outside canvas) and rotate categories so each run feels different.
- Maintain high contrast between foreground text and backgrounds (e.g., do not leave white text on white/pale backgrounds; always pair light backgrounds with dark text and vice versa).
- Rotate palettes: declare CSS custom properties or utility classes so each experience chooses colors that fit the theme (light, pastel, dark, neon). Do not reuse the same navy blueprint; treat the sample layout as structure only.
- Use the provided examples as inspiration and feel free to remix their spirit, but avoid repeating the exact same names or layouts verbatim run after run.
- Keep the entire experience around 3000 tokens so responses stay snappy; prefer concise layouts, reusable utility classes, and focused copy.
- Every interactive element referenced in JS must already exist in the DOM with matching IDs/classes before scripts run.

BASE HTML BLUEPRINT (adapt, do not return empty sections):
<main id="ndw-shell" class="min-h-screen text-slate-900" style="--bg-100:#f8fafc;--bg-300:#e0f2fe;--accent-500:#2563eb;--text-900:#0f172a;background:linear-gradient(135deg,var(--bg-100),var(--bg-300));">
  <section class="mx-auto max-w-4xl px-6 py-12">
    <div class="rounded-3xl bg-white/85 backdrop-blur shadow-xl ring-1 ring-slate-200/70 p-8">
      <header class="mb-8 space-y-3 text-center text-slate-900">
        <p class="text-xs uppercase tracking-[0.3em] text-[color:var(--accent-500)]">[[category label here]]</p>
        <h1 class="text-4xl font-bold">[[hero headline]]</h1>
        <p class="text-slate-600">[[one-sentence instructions]]</p>
      </header>
      <div id="ndw-instructions" class="mb-6 rounded-2xl bg-slate-100/90 p-4 text-sm leading-relaxed text-slate-600">
        [[step-by-step guidance or flavor text]]
      </div>
      <div id="ndw-content" class="space-y-6 text-slate-700">
        [[dynamic cards, tools, or canvas container live here]]
      </div>
    </div>
  </section>
</main>
NOTE: Replace the CSS variables in the style attribute above to match the chosen palette; the light gradient shown is just an example.

SNIPPET RUNTIME (NDW APIs):
- NDW.loop((dt) => ...) → dt in milliseconds. DO NOT manually track time (no Date.now(), performance.now(), NDW.time.elapsed).
- Physics: velocity += accel * (dt/1000); position += velocity * (dt/1000).
- NDW.makeCanvas({fullScreen,width,height,parent,dpr}) returns canvas with .ctx, .dpr (NOT canvas.canvas.width).
- Use canvas.ctx.width/height (or canvas.width / canvas.dpr) for layout math; NDW scales the backing buffer for HiDPI so raw canvas.width is larger than the visible area.
- NDW.onKey((e) => ...) / NDW.onPointer((e) => ...) register once outside NDW.loop; use NDW.isDown inside the loop for continuous input.
- NDW.isDown('ArrowLeft' | 'mouse' | ...), NDW.onResize, NDW.utils (clamp, lerp, rng(seed), hash(seed)), NDW.pointer {x,y,down}.
- Initialize all state before NDW.loop; register handlers before NDW.loop; never declare them inside the loop.
- Never chain NDW.* off other expressions (no `.NDW`). Call each NDW method as its own statement.
- Canvas scenes must call ctx.clearRect(0, 0, ctx.width, ctx.height) each frame.
- Declare all state objects/arrays before NDW.loop; do not redeclare inside the loop.

JS GUARDRAILS:
- Wrap DOM queries inside DOMContentLoaded if scripts appear before the HTML (`document.addEventListener('DOMContentLoaded', () => { ... });`).
- Declare every variable with `const`/`let`; no implicit globals. Initialize counters/arrays with sensible defaults before using them.
- Avoid setInterval/setTimeout for animation; use NDW.loop and the provided `dt`.
- Remove unused listeners on reset paths and ensure buttons update text without referencing undefined nodes.

CATEGORY ROTATION — choose exactly one (avoid repeating the same category twice):
1. INTERACTIVE ENTERTAINMENT / WEB TOYS (Novelty/Experimental):
    - Focus on playful, unexpected interactions that delight users.
    - Example inspirations (remix as you like): dodging buttons, mischievous cat disco pads, haunted hallway door dodgers, emoji slingshot carnivals, digital lava lamps, confetti cannons that dodge the cursor, wiggly slider playgrounds, mini rhythm mashers, pixel pet playgrounds, memory firefly cascades.
    - Use expressive HTML/CSS and light JS—no physics engines. Think whimsy, surprise, and visual flair over utility.
2. UTILITY MICRO-TOOLS (Productivity):
    - Single-purpose web apps that solve a focused problem: pet age dashboards, is-it-Friday checkers, commute mood logs, meeting note distillers, micro gratitude journals.
    - Build clear layouts with input fields, results panels, and helpful microcopy; ensure accessibility for forms and buttons.
    - Highlight “next steps” or tips so users feel guided through the workflow.
    - Avoid relying solely on a canvas; craft a complete webpage layout.
3. GENERATIVE / RANDOMIZER SITES:
    - Produce random or algorithmic content (feel free to riff on these examples): story spark forges, NPC personality builders, cozy cocktail namers, doodle idea decks, playlist vibe spinners, random compliment generators, outrageous excuse oracles, travel daydream decks, micro poem whisperers.
    - Provide controls for refreshing or customizing the output (buttons, toggles) and showcase the generated content prominently.
4. INTERACTIVE ART (canvas-driven):
    - Use NDW.makeCanvas({fullScreen:true}); initialize particle arrays before the loop with NDW.utils.rng(seed).
    - Example: const rand = NDW.utils.rng(seed); const x = rand();
    - Ensure visible motion within 1 second. Pointer handlers live outside NDW.loop; read NDW.pointer inside. Think aurora ribbon fields, neon lattice tunnels, ripple ink pools, lantern glow swarms, mosaic bloom clouds for motion inspiration.
    - Add an HTML caption describing the concept or interaction.
5. QUIZZES / LEARNING CARDS:
    - Use semantic HTML sections with question cards, labeled inputs (radio/checkbox/text), progress indicators, and CTA buttons.
    - Provide clear instructions and a scoring/reveal mechanic using plain JS DOM updates (no canvas, no NDW.makeCanvas). Consider movie-night matchup quizzes, mythology flashcards, constellation spotters, onboarding checklists, tiny science trivia showdowns.
    - Prefer FORMAT #2 or #1 with rich HTML structure; ensure accessibility with labels and logical grouping.

CONTROLS & INPUT REFERENCE (canvas categories only):
- Keyboard discrete: NDW.onKey((e) => { if (e.key === 'ArrowUp') jump(); });
- Keyboard continuous: if (NDW.isDown('ArrowLeft')) x -= speed * (dt/1000);
- Mouse/touch: NDW.onPointer((e) => { if (e.down) shoot(e.x, e.y); });
- Mouse held: if (NDW.isDown('mouse')) dragObject();

DO NOT:
- Do not use inline event handlers (`onclick=""`, etc.) or global window timers.
- Do not reference external fonts, CDNs, or fetch remote data.
- Do not leave empty containers (e.g., an `#ndw-app` with no children) or placeholder text like “TODO”.
- Do not create duplicate IDs or register multiple identical NDW.onPointer/onKey handlers inside loops.

SELF QA BEFORE RETURNING:
1. Pretend to click every button/toggle and ensure the described behaviour occurs; fix mismatched selectors.
2. Verify headings, instructions, and controls are visible on first paint (no hidden `display:none` wrappers).
3. For quizzes/tools, ensure result text updates and reset flows always set meaningful copy (never `undefined`).

CANONICAL CANVAS TEMPLATE:
const stage = document.createElement('section');
stage.className = 'mx-auto my-6 w-full max-w-4xl rounded-xl bg-white/85 backdrop-blur p-6 shadow-lg ring-1 ring-slate-200/70';
document.getElementById('ndw-app')?.appendChild(stage);

const canvas = NDW.makeCanvas({ parent: stage, width: 960, height: 560 });
const ctx = canvas.ctx;
const rand = NDW.utils.rng(seed);
let state = { x: ctx.width / 2, vx: 0 };

NDW.onKey((e) => {
     if (e.key === 'ArrowLeft') state.vx = -1;
     if (e.key === 'ArrowRight') state.vx = 1;
});

NDW.loop((dt) => {
     const seconds = dt / 1000;
     const width = ctx.width;
     const height = ctx.height;
     state.x = Math.max(20, Math.min(width - 20, state.x + state.vx * seconds * 200));
     ctx.clearRect(0, 0, width, height);
     ctx.fillStyle = '#10b981';
     ctx.fillRect(state.x - 20, height - 60, 40, 40);
});

OUTPUT CHECKLIST:
✓ Valid JSON in format #1, #2, or #3
✓ Title present (if snippet) and used; or omit cleanly
✓ All vars initialized; listeners bound before use
✓ Canvas flows (categories 1 & 3 only): clearRect each frame, use dt parameter, no manual timers
✓ Websites/Quizzes: multi-section DOM layout, accessible labels, no canvas usage
✓ No undefined refs or missing elements
"""

_CATEGORY_ROTATION_NOTES = [
    ("CATEGORY ASSIGNMENT (1/5): Interactive Entertainment / Web Toy",
     "CATEGORY ASSIGNMENT (1/5): You MUST build an Interactive Entertainment / Web Toy. Focus on playful, unexpected interactions (dodging buttons, mischievous cat disco pads, haunted hallway dodgers, emoji slingshot carnivals, digital lava lamps, confetti cannons that dodge the cursor, wiggly slider playgrounds, mini rhythm mashers, pixel pet playgrounds, memory firefly cascades). Use these ideas as flavor prompts—remix or combine them, but avoid carbon-copying the exact name/layout back to back. Use expressive HTML/CSS and light JS—no heavy physics engines—and stay whimsical."),
    ("CATEGORY ASSIGNMENT (2/5): Utility Micro-Tool",
     "CATEGORY ASSIGNMENT (2/5): You MUST build a Utility Micro-Tool solving one focused task (pet age dashboards, is-it-Friday checkers, commute mood logs, meeting note distillers, micro gratitude journals). You can revisit similar problem spaces, but vary the branding, copy, and UI details so repeated runs feel distinct. Deliver clear inputs, result panels, accessibility-friendly labels, and next-step tips—avoid canvas-only layouts and keep it practical."),
    ("CATEGORY ASSIGNMENT (3/5): Generative Randomizer",
     "CATEGORY ASSIGNMENT (3/5): You MUST build a Generative / Randomizer experience that produces fresh content (story spark forges, NPC personality builders, cozy cocktail namers, doodle idea decks, playlist vibe spinners, random compliment generators, outrageous excuse oracles, travel daydream decks, micro poem whisperers). Feel free to riff on these examples, but rotate the theme, framing, and output tone so consecutive apps don’t feel identical. Include controls to refresh or customize output and keep the generative theme central."),
    ("CATEGORY ASSIGNMENT (4/5): Interactive Art",
     "CATEGORY ASSIGNMENT (4/5): You MUST build Interactive Art with NDW.makeCanvas. Initialize arrays with NDW.utils.rng(seed), create visible motion within 1 second, and read NDW.pointer inside the loop while handlers stay outside. Draw inspiration from aurora ribbon fields, neon lattice tunnels, ripple ink pools, lantern glow swarms, mosaic bloom clouds—remix palettes and motion patterns so repeat generations stay varied. Include an HTML caption describing the piece."),
    ("CATEGORY ASSIGNMENT (5/5): Quizzes / Learning Cards",
     "CATEGORY ASSIGNMENT (5/5): You MUST build Quizzes / Learning Cards using semantic sections, labeled inputs, progress indicators, and reveal/score mechanics (movie-night matchup quizzes, mythology flashcards, constellation spotters, onboarding checklists, tiny science trivia showdowns). You can revisit similar trivia genres, but change the scenario, question text, and styling so each iteration feels new. Prefer rich HTML layouts—no canvas—and keep everything accessible."),
]

_category_lock = threading.Lock()
_category_indices: Dict[str, int] = {}


def _next_category_note(user_key: Optional[str] = None) -> str:
    key = (user_key or "").strip() or "__global__"
    with _category_lock:
        idx = (_category_indices.get(key, -1) + 1) % len(_CATEGORY_ROTATION_NOTES)
        _category_indices[key] = idx
        # Avoid unbounded growth if many unique keys appear
        if len(_category_indices) > 4096:
            # Drop oldest half excluding the active key to keep footprint bounded
            for stale in list(_category_indices.keys()):
                if stale == key:
                    continue
                _category_indices.pop(stale, None)
                if len(_category_indices) <= 2048:
                    break
        heading, note = _CATEGORY_ROTATION_NOTES[idx]
    logging.info("llm category_assignment=%s index=%d key=%s", heading, idx + 1, key)
    return note

# Removed Gemini provider support completely


def _call_openrouter_for_page(brief: str, seed: int, category_note: str = "") -> Optional[Dict[str, Any]]:
    """Call OpenRouter Chat Completions and parse a page dict; None on failure."""
    temperature = TEMPERATURE

    prompt = f"""
You generate exactly one self-contained interactive web app per request.
Output valid JSON only. No backticks. No explanations.

Brief (may be empty → you choose a theme): {brief}
Seed: {seed}

{category_note}

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
    }
    if OPENROUTER_MAX_TOKENS is not None:
        body["max_tokens"] = OPENROUTER_MAX_TOKENS
    if wants_json_mode:
        body["response_format"] = {"type": "json_object"}

    def _send_openrouter(payload: Dict[str, Any]):
        _openrouter_sleep_if_needed()
        try:
            response = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, timeout=LLM_TIMEOUT_SECS)
        except Exception as exc:
            logging.warning("OpenRouter request error: %r", exc)
            return None
        if response.status_code == 429:
            _openrouter_register_rate_limit(response.headers.get("Retry-After"))
        elif response.status_code == 200:
            _openrouter_reset_backoff()
        return response

    resp = _send_openrouter(body)
    if resp is None:
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
            body.pop("response_format", None)
            resp = _send_openrouter(body)
            if resp is None:
                return None
            if resp.status_code != 200:
                try:
                    msg = resp.text[:400]
                except Exception:
                    msg = str(resp.status_code)
                logging.warning("OpenRouter HTTP %s after retry: %s", resp.status_code, msg)
                # Try fallback models before giving up
                fallback_models = [OPENROUTER_FALLBACK_MODEL_1, OPENROUTER_FALLBACK_MODEL_2]
                for fallback_model in fallback_models:
                    if fallback_model and fallback_model != OPENROUTER_MODEL:
                        logging.warning("OpenRouter model '%s' failed; retrying with fallback '%s'", OPENROUTER_MODEL, fallback_model)
                        body_fallback = dict(body)
                        body_fallback["model"] = fallback_model
                        resp_fb = _send_openrouter(body_fallback)
                        if resp_fb is None:
                            continue
                        if resp_fb.status_code != 200:
                            try:
                                msg_fb = resp_fb.text[:400]
                            except Exception:
                                msg_fb = str(resp_fb.status_code)
                            logging.warning("OpenRouter HTTP %s with fallback '%s': %s", resp_fb.status_code, fallback_model, msg_fb)
                            continue
                        # Use fallback response as success
                        resp = resp_fb
                        break
                else:
                    # All fallbacks failed
                    return None
        else:
            logging.warning("OpenRouter HTTP %s: %s", resp.status_code, msg)
            # Try fallback models before giving up
            fallback_models = [OPENROUTER_FALLBACK_MODEL_1, OPENROUTER_FALLBACK_MODEL_2]
            for fallback_model in fallback_models:
                if fallback_model and fallback_model != OPENROUTER_MODEL:
                    logging.warning("OpenRouter model '%s' failed; retrying with fallback '%s'", OPENROUTER_MODEL, fallback_model)
                    body_fallback = dict(body)
                    body_fallback["model"] = fallback_model
                    resp_fb = _send_openrouter(body_fallback)
                    if resp_fb is None:
                        continue
                    if resp_fb.status_code != 200:
                        try:
                            msg_fb = resp_fb.text[:400]
                        except Exception:
                            msg_fb = str(resp_fb.status_code)
                        logging.warning("OpenRouter HTTP %s with fallback '%s': %s", resp_fb.status_code, fallback_model, msg_fb)
                        continue
                    # Use fallback response as success
                    resp = resp_fb
                    break
            else:
                # All fallbacks failed
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


def _gemini_review_active() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return bool(GEMINI_REVIEW_ENABLED and GEMINI_API_KEY and GEMINI_REVIEW_ENDPOINT)


def _call_gemini_review(doc: Dict[str, Any], brief: str, category_note: str) -> Optional[Dict[str, Any]]:
    if not _gemini_review_active():
        return None
    try:
        serialized = json.dumps(doc, ensure_ascii=False, indent=2)
    except Exception:
        serialized = str(doc)
    instructions = (
        "You are a compliance reviewer and fixer for interactive web apps. "
        "Inspect the provided JSON payload for safety, policy violations, markup/runtime bugs, or accessibility issues. "
        "If problems are minor, repair them directly and return the corrected payload. "
        "If the experience is unsafe or too broken to repair confidently, reject it. "
        "Respond with compact JSON using this schema:\n"
        '{"ok": true|false, "issues":[{"severity":"info|warn|block","field":"...","message":"..."}],'
        '"notes":"optional summary","doc":{...optional corrected payload...}}\n'
        "Only set ok=true if the final payload (original or corrected) is safe, functional, and accessible."
    )
    prompt = (
        f"{instructions}\n\n"
        f"Brief: {brief or '(auto generated)'}\n"
        f"Category Instruction: {category_note}\n\n"
        "App JSON:\n"
        f"{serialized}\n"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 250000,
        },
    }
    try:
        resp = requests.post(
            GEMINI_REVIEW_ENDPOINT,
            params={"key": GEMINI_API_KEY},
            json=body,
            timeout=min(LLM_TIMEOUT_SECS, 45),
        )
    except Exception as exc:
        logging.warning("Gemini review request error: %r", exc)
        return None
    if resp.status_code != 200:
        try:
            msg = resp.text[:400]
        except Exception:
            msg = str(resp.status_code)
        logging.warning("Gemini review HTTP %s: %s", resp.status_code, msg)
        return None
    try:
        payload = resp.json()
    except Exception as exc:
        logging.warning("Gemini review non-JSON body: %r", exc)
        return None
    text = _extract_gemini_text(payload)
    if not text or not isinstance(text, str):
        try:
            raw = resp.text[:400]
        except Exception:
            raw = "<unavailable>"
        logging.warning("Gemini review empty content; raw response snippet=%s", raw)
        return None
    text = text.strip()
    try:
        review = json.loads(text)
    except Exception:
        try:
            any_json = _json_from_text(text)
            review = any_json if isinstance(any_json, dict) else None
        except Exception:
            review = None
    if not isinstance(review, dict):
        logging.warning("Gemini review response unparsable: %s", text[:200])
        return None
    return review


def _extract_gemini_text(payload: Dict[str, Any]) -> Optional[str]:
    try:
        candidates = payload.get("candidates") or []
        for cand in candidates:
            content = cand.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                txt = part.get("text")
                if isinstance(txt, str) and txt.strip():
                    return txt
                function_call = part.get("functionCall")
                if isinstance(function_call, dict):
                    args = function_call.get("arguments")
                    if isinstance(args, str) and args.strip():
                        return args
                    try:
                        return json.dumps(function_call, ensure_ascii=False)
                    except Exception:
                        pass
                data_blob = part.get("data") or part.get("json") or part.get("structValue")
                if data_blob:
                    try:
                        return json.dumps(data_blob, ensure_ascii=False)
                    except Exception:
                        pass
    except Exception:
        pass
    return None


def _maybe_run_compliance_review(
    doc: Dict[str, Any], brief: str, category_note: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool]:
    if not isinstance(doc, dict):
        return None, None, True
    if not _gemini_review_active():
        return None, None, True
    logging.info("Compliance review: submitting doc for Gemini evaluation")
    review = _call_gemini_review(doc, brief, category_note)
    if not isinstance(review, dict):
        logging.info("Compliance review: Gemini response missing or unusable; skipping")
        return None, None, True
    corrected_doc = None
    for key in ("doc", "fixed_doc", "corrected_doc", "patched_doc"):
        maybe_doc = review.get(key)
        if isinstance(maybe_doc, dict):
            corrected_doc = maybe_doc
            break
    ok_value = review.get("ok")
    if ok_value is False:
        logging.info("Compliance review: Gemini blocked doc with %d issues", len(review.get("issues", [])))
        return review, None, False
    if corrected_doc is not None:
        logging.info("Compliance review: Gemini returned corrected payload")
        return review, corrected_doc, True
    logging.info("Compliance review: Gemini approved without changes")
    return review, None, True


def run_compliance_batch(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not documents:
        return None
    if not _gemini_review_active():
        return None
    try:
        return _call_gemini_review_batch(documents)
    except Exception as exc:
        logging.warning("Gemini batch review error: %r", exc)
        return None


def _call_gemini_review_batch(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not documents:
        return None
    prompt_sections = []
    for idx, doc in enumerate(documents):
        try:
            serialized = json.dumps(doc, ensure_ascii=False, indent=2)
        except Exception:
            serialized = str(doc)
        prompt_sections.append(
            f"APP_INDEX: {idx}\nJSON:\n{serialized}\n"
        )
    instructions = (
        "You are a compliance reviewer and fixer for interactive web apps. "
        "Evaluate each document below. Return a JSON array where each element is:\n"
        '{"index": <matching APP_INDEX>, "ok": true|false, '
        '"issues":[{"severity":"info|warn|block","field":"...","message":"..."}], '
        '"notes":"optional summary", "doc":{...optional corrected payload...}}\n'
        "Only set ok=true if the payload (original or corrected) is safe, functional, and accessible. "
        "If a document is irreparable, set ok=false and omit the doc field."
    )
    prompt = instructions + "\n\n---\n" + "\n---\n".join(prompt_sections)
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": min(8192, 2048 * len(documents)),
        },
    }
    try:
        resp = requests.post(
            GEMINI_REVIEW_ENDPOINT,
            params={"key": GEMINI_API_KEY},
            json=body,
            timeout=max(LLM_TIMEOUT_SECS, 120),
        )
    except Exception as exc:
        logging.warning("Gemini batch review request error: %r", exc)
        return None
    if resp.status_code != 200:
        try:
            msg = resp.text[:400]
        except Exception:
            msg = str(resp.status_code)
        logging.warning("Gemini batch review HTTP %s: %s", resp.status_code, msg)
        return None
    try:
        payload = resp.json()
    except Exception as exc:
        logging.warning("Gemini batch review non-JSON body: %r", exc)
        return None
    text = _extract_gemini_text(payload)
    if not text or not isinstance(text, str):
        try:
            raw = resp.text[:400]
        except Exception:
            raw = "<unavailable>"
        logging.warning("Gemini batch review empty content; raw response snippet=%s", raw)
        return None
    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        try:
            data = _json_from_text(text)
        except Exception:
            logging.warning("Gemini batch review response unparsable: %s", text[:200])
            return None
    if isinstance(data, dict):
        data = data.get("results") or data.get("reviews")
    if not isinstance(data, list):
        logging.warning("Gemini batch review invalid payload type: %s", type(data))
        return None
    return data


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
    if re.search(r"<\s*(?:!doctype|html|body|main|header|section|footer)\b", t, re.IGNORECASE):
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
        normalized_components: list[Dict[str, Any]] = []
        for idx, c in enumerate(comps):
            if not isinstance(c, dict):
                continue
            raw_props = c.get("props")
            props = dict(raw_props) if isinstance(raw_props, dict) else {}
            html = props.get("html")
            if not (isinstance(html, str) and html.strip()):
                html = c.get("html") if isinstance(c.get("html"), str) else None
            if not (isinstance(html, str) and html.strip()):
                continue
            height_val = props.get("height") if isinstance(props, dict) else c.get("height")
            try:
                height = int(height_val) if height_val is not None else 360
            except Exception:
                # If height is a string like "100vh", fall back to a generous default
                height = 720
            # Ensure html/height are present and sanitized
            props["html"] = html.strip()
            props["height"] = height
            normalized_components.append(
                {
                    "id": str(c.get("id") or f"custom-{idx + 1}"),
                    "type": "custom",
                    "props": props,
                }
            )
        if normalized_components:
            return {"components": normalized_components}
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
