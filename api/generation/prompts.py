from __future__ import annotations

from api.design_kit import DESIGN_KIT_MANIFEST
from api.generation.experience_grammar import (
    AFFORDANCE_PATTERNS,
    EXPERIENCE_ARCHETYPES,
    FEEDBACK_PATTERNS,
    PRIMARY_LOOP_TYPES,
    PROGRESSION_PATTERNS,
    REPLAYABILITY_PATTERNS,
)

FINAL_HTML_OUTPUT_FORMAT = """
FINAL OUTPUT FORMAT:
- Output one complete final page inside a fenced `html` code block.
- The fenced HTML must start with `<!doctype html>` and include `<html>`, `<head>`, and `<body>`.
- Do not output JSON, snippet documents, component arrays, Markdown explanations, or extra prose after the final fenced HTML.
- For immersive 3D or WebGL concepts, use `<script type="module">import * as THREE from '/static/vendor/three.module.js'; ...</script>`.
""".strip()

PREMIUM_STYLE_GUIDANCE = """
PREMIUM BUILD GUIDANCE:
- Treat the approved plan as a creative director's brief.
- Use the selected layout, palette, motion preset, and overlay intentionally.
- Favor cinematic depth, layered parallax, responsive canvases, or restrained Three.js over flat static UI.
- Preserve clarity: strong hierarchy, readable controls, and no tone-on-tone text.
""".strip()

HARD_RUNTIME_RULES = """
GENERAL RULES:
- STRICT: No external scripts or styles via CDN. No external fonts/images/fetch. No iframes or document.write.
- Tailwind runtime is local; do not include CDN imports. GSAP, ScrollTrigger, and Lucide are already provided globally.
- Three.js is available locally in module scripts via `import * as THREE from '/static/vendor/three.module.js'`.
- Three addons are available only via local paths such as `/static/vendor/three-addons/controls/OrbitControls.js` and `/static/vendor/three-addons/postprocessing/UnrealBloomPass.js`. Never import remote modules.
- Use the ID `ndw-content` for the main app container when you need a primary stage.
- Every interactive element referenced in JS must already exist in the DOM before scripts run.
- CONTROL CONSISTENCY: buttons and keyboard shortcuts must trigger the same function, not near-duplicates.
- The generated page runs in an iframe sandbox. Do not write host cleanup code; iframe teardown destroys timers, listeners, styles, and WebGL contexts on the next generation.

DO NOT:
- Do not use inline event handlers (`onclick=""`, etc.) when a named listener is practical.
- Do not reference external fonts, CDNs, or fetch remote data.
- Do not leave empty containers or placeholder text like TODO.
- Do not create duplicate IDs or register duplicate NDW.onPointer/onKey handlers inside loops.

SELF QA:
1. Pretend to click every button and verify the described behavior occurs.
2. Verify headings, instructions, and controls are visible on first paint.
3. Ensure result text never becomes `undefined`.
4. Check contrast and readability. No white-on-white, black-on-black, or muddy medium-on-medium text.
5. Check runtime weight: keep first paint lightweight, cap particle counts near 120, avoid giant DOM grids, avoid stacked full-screen blur filters, and set WebGL pixel ratio to `Math.min(window.devicePixelRatio, 2)`.
""".strip()

PREMIUM_RUNTIME_GUIDANCE = """
PREMIUM ICONOGRAPHY:
- Use Lucide icons through local runtime only: `<i data-lucide="icon-name"></i>` and call `lucide.createIcons()` after render.

INITIAL VISUAL STATE:
- First paint must be visibly complete before interaction: background treatment, headline, instructions, controls, and ambient motion or particles.

PREMIUM INTROS:
- GSAP and ScrollTrigger are local globals. Use them for short intro/reveal sequences, not for hiding all content until animation completes.

CANONICAL CANVAS TEMPLATE:
```js
const canvas = NDW.makeCanvas({ parent: document.getElementById('ndw-content'), width: 960, height: 540 });
const ctx = canvas.ctx;
const rng = NDW.utils.rng(seed);
const state = { x: 100, velocity: 80 };
NDW.onPointer((event) => { state.x = event.x; });
NDW.loop((dt) => {
  const seconds = dt / 1000;
  state.x += state.velocity * seconds;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
});
```

NDW SDK CHEAT SHEET:
- `NDW.loop((dt) => { ... })` receives `dt` in milliseconds.
- Convert timing with `const seconds = dt/1000` or `(dt / 1000)` before applying velocity.
- No manual time tracking: never use Date.now() or performance.now() for animation timing.
- Initialize state, DOM references, event handlers, and assets before NDW.loop.
- `NDW.pointer` exposes mouse/touch state; pair pointer affordances with keyboard or tap fallbacks.
- `NDW.isPressed(key)` and `NDW.isDown(key)` support keyboard controls.
- `NDW.jump()`, `NDW.shot()`, and `NDW.action()` are semantic input aliases.
- `NDW.audio.playTone(freq, durationMs, type, gain)` is available for optional sound cues.
- `NDW.juice.shake(intensity, durationMs)` and `NDW.particles.spawn(...)` support feedback effects.
- `NDW.makeCanvas({ parent, width, height })` creates a managed canvas helper.
- `NDW.utils.dist`, `NDW.utils.angle`, `NDW.utils.rng(seed)`, `NDW.utils.clamp`, and `NDW.utils.lerp` support deterministic motion and physics.
- `NDW.utils.store.get(key)` and `NDW.utils.store.set(key, value)` support simple local persistence.

DESIGN QUALITY:
- Aim for premium design quality: modern, harmonious contrast, distinctive hierarchy, and rich aesthetic structure.
- Category assignment is replaced by premium planner axes and novelty fingerprints; obey those axes instead of repeating recent trends.
- Provide visible instructions for the signature interaction.
- Never chain NDW calls off other expressions; call NDW helpers as clear standalone statements.
- PERFORMANCE BUDGET: the site must feel rich without melting laptops. Prefer transforms and opacity, keep DOM node counts modest, use one primary canvas/WebGL stage at most, avoid expensive blur/filter stacks, and never spawn unbounded particles or intervals.
""".strip()

PAGE_SHAPE_HINT = "\n\n".join(
    [FINAL_HTML_OUTPUT_FORMAT, HARD_RUNTIME_RULES, PREMIUM_RUNTIME_GUIDANCE]
)


def _semantic_role_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "visual_role": {"type": "string"},
            "interaction_role": {"type": "string"},
            "content_role": {"type": "string"},
            "motion_role": {"type": "string"},
        },
        "required": ["visual_role", "interaction_role", "content_role", "motion_role"],
    }


_ANCHOR_KEYS = [
    "material",
    "natural_phenomenon",
    "cultural_object",
    "system_metaphor",
    "interaction_verb",
]

PREMIUM_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "experience_archetype": {"type": "string", "enum": EXPERIENCE_ARCHETYPES},
        "primary_loop_type": {"type": "string", "enum": PRIMARY_LOOP_TYPES},
        "semantic_anchors": {
            "type": "object",
            "properties": {key: {"type": "string"} for key in _ANCHOR_KEYS},
            "required": _ANCHOR_KEYS,
        },
        "semantic_translation": {
            "type": "object",
            "properties": {key: _semantic_role_schema() for key in _ANCHOR_KEYS},
            "required": _ANCHOR_KEYS,
        },
        "visitor_role": {"type": "string", "minLength": 4},
        "visitor_goal": {"type": "string", "minLength": 8},
        "first_interaction": {"type": "string", "minLength": 8},
        "primary_loop": {
            "type": "object",
            "properties": {
                "user_action": {"type": "string"},
                "visible_response": {"type": "string"},
                "state_change": {"type": "string"},
                "reward_or_payoff": {"type": "string"},
                "continue_reason": {"type": "string"},
            },
            "required": [
                "user_action",
                "visible_response",
                "state_change",
                "reward_or_payoff",
                "continue_reason",
            ],
        },
        "secondary_interactions": {"type": "array", "items": {"type": "string"}},
        "feedback_contract": {"type": "string", "minLength": 12},
        "feedback_pattern": {"type": "string", "enum": FEEDBACK_PATTERNS},
        "progression_model": {"type": "string", "minLength": 6},
        "progression_pattern": {"type": "string", "enum": PROGRESSION_PATTERNS},
        "reset_or_replay": {"type": "string", "minLength": 6},
        "replayability_pattern": {"type": "string", "enum": REPLAYABILITY_PATTERNS},
        "onboarding_cue": {"type": "string", "minLength": 6},
        "mobile_interaction": {"type": "string", "minLength": 6},
        "affordance_pattern": {"type": "string", "enum": AFFORDANCE_PATTERNS},
        "input_modality": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["keyboard", "pointer", "touch", "scroll", "voice_simulated", "passive"],
            },
        },
        "layout_archetype": {
            "type": "string",
            "enum": ["split_lens", "stage_focus", "bento_magazine", "immersive_poster"],
        },
        "motion_archetype": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["motion_presets"].keys())},
        "visual_density": {"type": "string", "enum": ["airy", "layered", "dense"]},
        "interaction_model": {
            "type": "string",
            "enum": ["pointer_reactive", "scroll_story", "tool_driven", "playful_loop"],
        },
        "rendering_mode": {"type": "string", "enum": ["dom", "canvas", "three", "hybrid"]},
        "tone": {
            "type": "string",
            "enum": ["luminous", "editorial", "playful", "brutalist_softened", "cinematic"],
        },
        "signature_interaction": {"type": "string"},
        "hero_treatment": {"type": "string"},
        "palette_key": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["palettes"].keys())},
        "layout_key": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["layouts"].keys())},
        "motion_preset": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["motion_presets"].keys())},
        "overlay_key": {"type": "string", "enum": list(DESIGN_KIT_MANIFEST["overlays"].keys())},
        "display_font_key": {
            "type": "string",
            "enum": ["display_orbit", "display_editorial", "display_grotesk"],
        },
        "body_font_key": {"type": "string", "enum": ["body_clean", "body_soft"]},
        "three_scene_key": {"type": "string", "enum": ["glass_orbit", "particle_ribbon", "terrain_glow"]},
        "art_direction": {"type": "string", "minLength": 12, "maxLength": 180},
        "prompt_genome": {
            "type": "object",
            "properties": {
                "world_seed": {"type": "string"},
                "layout_pressure": {"type": "string"},
                "material_language": {"type": "string"},
                "motion_signature": {"type": "string"},
                "interaction_constraint": {"type": "string"},
                "rendering_pressure": {"type": "string"},
                "avoid_recent": {"type": "array", "items": {"type": "string"}},
                "novelty_target": {"type": "string"},
            },
            "required": [
                "world_seed",
                "layout_pressure",
                "material_language",
                "motion_signature",
                "interaction_constraint",
                "rendering_pressure",
                "avoid_recent",
                "novelty_target",
            ],
        },
        "fingerprint": {
            "type": "object",
            "properties": {
                "layout": {"type": "string"},
                "palette": {"type": "string"},
                "motion": {"type": "string"},
                "interaction": {"type": "string"},
                "rendering": {"type": "string"},
                "theme_terms": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["layout", "palette", "motion", "interaction", "rendering", "theme_terms"],
        },
    },
    "required": [
        "experience_archetype",
        "primary_loop_type",
        "semantic_anchors",
        "semantic_translation",
        "visitor_role",
        "visitor_goal",
        "first_interaction",
        "primary_loop",
        "secondary_interactions",
        "feedback_contract",
        "feedback_pattern",
        "progression_model",
        "progression_pattern",
        "reset_or_replay",
        "replayability_pattern",
        "onboarding_cue",
        "mobile_interaction",
        "affordance_pattern",
        "input_modality",
        "layout_archetype",
        "motion_archetype",
        "visual_density",
        "interaction_model",
        "rendering_mode",
        "tone",
        "signature_interaction",
        "hero_treatment",
        "palette_key",
        "layout_key",
        "motion_preset",
        "overlay_key",
        "display_font_key",
        "body_font_key",
        "three_scene_key",
        "art_direction",
        "prompt_genome",
        "fingerprint",
    ],
}
