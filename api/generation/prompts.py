from __future__ import annotations

from api.design_kit import DESIGN_KIT_MANIFEST
from api.generation.experience_grammar import (
    AFFORDANCE_PATTERNS,
    ACTIVITY_TYPES,
    ALL_FORMATS,
    BORING_INTERACTION_PATTERNS,
    CHROME_POLICIES,
    COPY_DENSITIES,
    EXPERIENCE_ARCHETYPES,
    FEEDBACK_PATTERNS,
    GENRE_VISUAL_DENSITIES,
    INSTRUCTION_POLICIES,
    LIBRARY_PROFILES,
    MECHANIC_PATTERNS,
    MOTION_LANGUAGES,
    PAGE_GENRES,
    PALETTE_STRATEGIES,
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
- Obey the activity_contract before visual decoration: the page must have a concrete task, a real mechanic, visible state, and a payoff.
- Obey the genre_contract above all style impulses: copy density, palette strategy, instruction policy, chrome policy, and motion language must match the page genre.
- Use the selected layout, palette, and motion preset intentionally. A local overlay is optional.
- Prefer original inline SVG, CSS-generated artwork, Canvas, or Three.js when it better serves the format. Do not force a stock texture onto every page.
- Favor cinematic depth, layered parallax, responsive canvases, or restrained Three.js over flat static UI.
- Preserve clarity through hierarchy and affordances, not tutorial panels.
- Aim for genre-appropriate polish: weird is fine, tacky clutter is not.
- Never use generic AI-generated aesthetics: avoid cliched purple/blue gradients, center-aligned white cards, predictable landing-page shells, and timid non-committal color.
- Commit to a distinct direction: brutally minimal, maximalist, refined luxury, lo-fi/zine, arcade, editorial, playful toy, or another clear genre. The page should answer: what makes this unforgettable?
- Use spatial composition intentionally: asymmetry, overlap, z-depth, diagonal flow, grid-breaking elements, dramatic scale jumps, full-bleed moments, generous negative space, or controlled density.
- Prefer one high-impact motion moment such as an orchestrated load, staggered reveal, transformation, or payoff over scattered distracting micro-interactions.
""".strip()

HARD_RUNTIME_RULES = """
GENERAL RULES:
- STRICT: No external scripts or styles via CDN. No external fonts/images/fetch. No iframes or document.write.
  Inline SVG, data:image/svg+xml, Lucide icons, and CSS-generated visuals are allowed and preferred.
- Tailwind runtime is local; do not include CDN imports. GSAP core and Lucide are available through local scripts; include the matching local script before using those globals inside the iframe.
- Alpine.js and Matter.js are local-only optional primitives. Include `/static/vendor/alpine.min.js` only for app/tool/commerce UI state. Include `/static/vendor/matter.min.js` only for physics-first games/toys.
- Three.js is available locally in module scripts via `import * as THREE from '/static/vendor/three.module.js'`.
- Three addons are available only via local paths such as `/static/vendor/three-addons/controls/OrbitControls.js` and `/static/vendor/three-addons/postprocessing/UnrealBloomPass.js`. Never import remote modules.
- Use the ID `ndw-content` for the main app container when you need a primary stage.
- Every interactive element referenced in JS must already exist in the DOM before scripts run.
- CONTROL CONSISTENCY: buttons and keyboard shortcuts must trigger the same function, not near-duplicates.
- The generated page runs in an iframe sandbox. Do not write host cleanup code; iframe teardown destroys timers, listeners, styles, and WebGL contexts on the next generation.

DO NOT:
- Do not use inline event handlers (`onclick=""`, `oninput=""`, etc.). Use `addEventListener` after DOM refs exist, or Alpine `x-on`/`@click` for Alpine pages.
- Do not reference external fonts, CDNs, or fetch remote data.
- Do not leave empty containers or placeholder text like TODO.
- Do not create duplicate IDs or register duplicate NDW.onPointer/onKey handlers inside loops.

SELF QA:
1. Pretend to click every button and verify the described behavior occurs.
2. Verify headings, instructions, and controls are visible on first paint.
3. Ensure result text never becomes `undefined`.
4. Check contrast and readability. No white-on-white, black-on-black, or muddy medium-on-medium text.
5. Check runtime weight: keep first paint lightweight, cap particle counts near 120, avoid giant DOM grids, avoid stacked full-screen blur filters, and set WebGL pixel ratio to `Math.min(window.devicePixelRatio, 2)`.
6. Check design discipline: one focal area, controls near what they affect, no literal planning-section headings, no visible code-comment debris like `//`, no raw TODO/undefined/null text.
7. Check activity depth: no slider-only pages unless activity_type is interactive_instrument or simulation; every control must advance a goal, create an output, unlock content, configure a result, or change persistent visible state.
8. Check naming: games and quizzes must expose the recognizable format in the title, such as Snake, Platform, Tic-Tac-Toe, Quiz, Memory Match, or Word Game.
""".strip()

PREMIUM_RUNTIME_GUIDANCE = """
PREMIUM ICONOGRAPHY:
- Use Lucide icons through local runtime only: `<i data-lucide="icon-name"></i>` and call `lucide.createIcons()` after render.

PRODUCT VISUALS:
- For product/storefront pages: generate SVG product illustrations inline using `<svg>` elements with gradients, paths, and shapes. Draw the product hero — book cover, candle, sneaker, jewelry, skincare bottle, electronics device — as a styled SVG illustration in the product hero area.
- For app pages: Lucide icons cover UI chrome. Use CSS-styled cards, badges, colored sections, and gradients for visual richness.
- Never use `<img>` tags pointing to remote URLs. All visuals must be inline SVG, data:image/svg+xml, Lucide icons, CSS gradients/shapes, or Canvas/Three.js.

PREMIUM UI STATE:
- Alpine.js is available locally through `<script defer src="/static/vendor/alpine.min.js"></script>`. Use it for app/tool/commerce state such as filters, carts, drawers, tabs, selected records, and multi-step forms. Do not use Alpine for canvas/game loops.

PREMIUM PHYSICS:
- Matter.js is available locally through `<script src="/static/vendor/matter.min.js"></script>`. Use it only for physics-first games/toys with collisions, gravity, constraints, scoring, reset, and visible cause/effect.

INITIAL VISUAL STATE:
- First paint must be visibly complete before interaction: background treatment, headline, instructions, controls, and ambient motion or particles.

PREMIUM INTROS:
- GSAP core is a local global. Use it for short intro/reveal sequences, not for hiding all content until animation completes.
- In generated iframe pages, include `<script src="/static/vendor/gsap.min.js"></script>` before using `gsap`.

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
- `NDW.audio.playTone(freq, durationMs, type, gain)` is available for optional sound cues. Browser audio must be triggered from a real click, tap, key, or pointer handler; never rely on autoplay or page-load sound.
- `NDW.juice.shake(intensity, durationMs)` and `NDW.particles.spawn(...)` support feedback effects.
- `NDW.makeCanvas({ parent, width, height })` creates a managed canvas helper.
- `NDW.utils.dist`, `NDW.utils.angle`, `NDW.utils.rng(seed)`, `NDW.utils.clamp`, and `NDW.utils.lerp` support deterministic motion and physics.
- `NDW.utils.store.get(key)` and `NDW.utils.store.set(key, value)` support simple local persistence.

DESIGN QUALITY:
- Aim for premium design quality: modern, harmonious contrast, distinctive hierarchy, and rich aesthetic structure.
- Category assignment is replaced by premium planner axes and novelty fingerprints; obey those axes instead of repeating recent trends.
- Provide visible affordances for the signature interaction. Do not create a section titled "Instructions", "Onboarding", "Visitor Role", "Primary Loop", or similar planning language unless the genre_contract explicitly allows documentation.
- Keep copy inside the genre_contract copy budget. Toy/game/app pages should use microcopy and labels, not explanatory paragraphs.
- Use palette roles, not random color collisions: background, surface, primary accent, optional secondary accent, readable text, and state color only when needed.
- Do not make the page merely "interactive-looking." Build a mini activity: browser game, tool, puzzle, SaaS-like app, simulator, narrative explorer, fake OS, commerce/booking flow, or data investigation.
- For game/quiz pages, use legible format names. The title should say Snake, Platform, Tic-Tac-Toe, Quiz, Memory Match, or Word Game, with semantic anchors as flavor only.
- Avoid slider-only pages. Sliders are allowed only when they are one part of a larger task with visible consequences and payoff.
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
    "everyday_object",
    "layout_metaphor",
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
        "activity_type": {"type": "string", "enum": ACTIVITY_TYPES},
        "activity_contract": {
            "type": "object",
            "properties": {
                "activity_type": {"type": "string", "enum": ACTIVITY_TYPES},
                "activity_variant": {
                    "type": "string",
                    "enum": ALL_FORMATS,
                },
                "core_mechanic": {"type": "string", "enum": MECHANIC_PATTERNS},
                "library_profile": {"type": "string", "enum": LIBRARY_PROFILES},
                "activity_goal": {"type": "string", "minLength": 8},
                "required_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "required_state": {"type": "string", "minLength": 8},
                "payoff": {"type": "string", "minLength": 8},
                "boredom_risks": {
                    "type": "array",
                    "items": {"type": "string", "enum": BORING_INTERACTION_PATTERNS},
                },
                "success_signal": {"type": "string", "minLength": 8},
            },
            "required": [
                "activity_type",
                "activity_variant",
                "core_mechanic",
                "library_profile",
                "activity_goal",
                "required_actions",
                "required_state",
                "payoff",
                "boredom_risks",
                "success_signal",
            ],
        },
        "task_contract": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "minLength": 3},
                "user_goal": {"type": "string", "minLength": 8},
                "domain_objects": {"type": "array", "items": {"type": "string"}},
                "state_variables": {"type": "array", "items": {"type": "string"}},
                "controls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "type": {"type": "string"},
                            "must_change_state": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["label", "type", "must_change_state"],
                    },
                },
                "completion_condition": {"type": "string", "minLength": 8},
                "payoff_scene": {
                    "type": "object",
                    "properties": {
                        "trigger": {"type": "string", "minLength": 4},
                        "scene": {"type": "string", "minLength": 8},
                        "continue_action": {"type": "string", "minLength": 4},
                    },
                    "required": ["trigger", "scene", "continue_action"],
                },
                "error_states": {"type": "array", "items": {"type": "string"}},
                "allowed_patterns": {"type": "array", "items": {"type": "string"}},
                "visual_budget": {
                    "type": "object",
                    "properties": {
                        "ambient_background": {"type": "string"},
                        "motion_only_for": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["ambient_background", "motion_only_for"],
                },
            },
            "required": [
                "format",
                "user_goal",
                "domain_objects",
                "state_variables",
                "controls",
                "completion_condition",
                "payoff_scene",
                "error_states",
                "allowed_patterns",
                "visual_budget",
            ],
        },
        "genre_contract": {
            "type": "object",
            "properties": {
                "page_genre": {"type": "string", "enum": PAGE_GENRES},
                "copy_density": {"type": "string", "enum": COPY_DENSITIES},
                "visual_density": {"type": "string", "enum": GENRE_VISUAL_DENSITIES},
                "palette_strategy": {"type": "string", "enum": PALETTE_STRATEGIES},
                "motion_language": {"type": "string", "enum": MOTION_LANGUAGES},
                "instruction_policy": {"type": "string", "enum": INSTRUCTION_POLICIES},
                "chrome_policy": {"type": "string", "enum": CHROME_POLICIES},
                "focal_rule": {"type": "string", "minLength": 8},
                "copy_budget": {"type": "string", "minLength": 4},
                "palette_roles": {
                    "type": "object",
                    "properties": {
                        "background": {"type": "string"},
                        "surface": {"type": "string"},
                        "primary_accent": {"type": "string"},
                        "secondary_accent": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["background", "surface", "primary_accent", "text"],
                },
            },
            "required": [
                "page_genre",
                "copy_density",
                "visual_density",
                "palette_strategy",
                "motion_language",
                "instruction_policy",
                "chrome_policy",
                "focal_rule",
                "copy_budget",
                "palette_roles",
            ],
        },
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
            "enum": list(DESIGN_KIT_MANIFEST["layouts"].keys()),
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
        "activity_type",
        "activity_contract",
        "task_contract",
        "genre_contract",
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
        "layout_key",
        "motion_preset",
        "display_font_key",
        "body_font_key",
        "three_scene_key",
        "art_direction",
        "prompt_genome",
        "fingerprint",
    ],
}
