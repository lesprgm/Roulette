from __future__ import annotations


HARD_RUNTIME_RULES = """
GENERAL RULES:
- No external scripts, styles, images, fonts, fetch, iframes, document.write, localStorage, or sessionStorage.
- Use only local scripts: `/static/vendor/gsap.min.js`, `/static/vendor/Draggable.min.js`, `/static/vendor/lucide.min.js`, `/static/vendor/alpine.min.js`, `/static/vendor/matter.min.js`, `/static/vendor/paper-shaders/ndw-paper.js`, and `/static/js/ndw.js`.
- Matter.js is only for physics-first games and toys. Alpine UI state profiles are for carts, filters, drawers, selected records, and configuration.
- Three.js uses direct local module imports. Do not invent plugin paths such as ScrollTrigger.
- Use `id="ndw-content"` for the main stage. DOM references must exist before handlers run.
- Use addEventListener or Alpine x-on; never inline onclick/oninput/onchange handlers.
- The page runs in an iframe. Do not add host cleanup code. Keep one canvas/WebGL stage at most, use transforms/opacity, and avoid stacked blur/filter effects.

SELF QA:
1. Every visible control changes a named visible result, subject, score, selection, cart, preview, or payoff state.
2. First paint shows the primary subject and usable controls; no blank stage or placeholder shell.
3. No duplicate IDs, undefined text, raw TODO, visible `//`, planning headings, footer, or fake telemetry chrome.
4. Use readable contrast and the target palette roles. Do not default to dark/slate shells unless the selected playfield needs contrast.
""".strip()


PREMIUM_RUNTIME_GUIDANCE = """
PREMIUM ICONOGRAPHY:
- Use Lucide through `<i data-lucide="icon-name"></i>` and `lucide.createIcons()` only when the target needs app chrome.

PREMIUM UI STATE:
- Alpine.js is for app/tool/commerce state: carts, filters, drawers, tabs, selected records, and forms.
- Define `window.storeName = () => ({ ... })` in a plain inline script before `<script defer src="/static/vendor/alpine.min.js"></script>` when using `x-data="storeName()"`. The store must exist before Alpine loads; never load Alpine synchronously before the store definition.
- Keep generated state in memory for the iframe session. Scores, streaks, drafts, and selections are ordinary JS or Alpine variables; never persist them with localStorage/sessionStorage.
- Do not put Alpine `x-for` or bound geometry attributes inside SVG. Render dynamic SVG geometry with plain JavaScript, or use Canvas for highly dynamic scenes.

PREMIUM PHYSICS:
- Matter.js is only for physics-first games and toys with visible collision, scoring, reset, and cause/effect.

PREMIUM SHADERS:
- Paper Shaders is local through `/static/vendor/paper-shaders/ndw-paper.js` and `mountPaperShader(...)`.
- Use it only on the target visual specification's named surface. Keep a CSS fallback, modest pixel budget, and never use it as generic wallpaper.

INITIAL VISUAL STATE:
- First paint must include the target visual subject, not merely panels, icons, buttons, gradients, or wallpaper. ambient motion or particles may support it but cannot replace it.

PREMIUM INTROS:
- GSAP creates one state-linked reveal, transformation, or payoff. Do not hide all content until animation completes.

CANONICAL CANVAS TEMPLATE:
- Use Canvas for game boards, drawing tools, maps, product views, and simulations. Render a complete initial frame before interaction.
""".strip()


PREMIUM_STYLE_GUIDANCE = """
PREMIUM BUILD GUIDANCE:
- The concrete format is the product. Use the task model and visual specification as the source of truth.
- Build the named primary subject with the visual specification's primary renderer, then use supporting renderers only where they reinforce that subject or its state changes.
- Use `visual_spec.palette` as an anchor system. Derive coherent tonal variants for hierarchy and state instead of repeating generic white cards, and use `surface_ink` on the supplied surface color.
- Implement `visual_spec.layout_model` as the page structure: preserve its nodes, spatial relations, desktop geometry, and mobile transformation. The model is geometry, not a mood label.
- Make `#ndw-content` a true viewport composition. Do not put the complete experience inside a narrow centered card or leave most of the viewport as decorative empty background.
- Stay within `visual_spec.copy_budget`. Prefer visible state, objects, and affordances over explanatory paragraphs.
- A strong visual stack has a dominant subject, one or two supporting layers, and one state-linked motion moment. It does not mean every available library must be loaded.
- Keep copy short, controls attached to what they affect, and make the site identifiable from the subject before body copy is read.
- Avoid generic AI-generated aesthetics: purple/blue gradients, centered white-card shells, dashboard telemetry, repetitive wave/grid wallpaper, emoji illustration systems, and timid color use.
- Use original inline SVG, Canvas, CSS shapes, Paper Shaders, Matter bodies, or Three.js only when the visual specification calls for them.
""".strip()


# The LLM plans only the decisions it can improve. The backend supplies the
# format, task, state, reward, visual specification, and runtime contracts.
PREMIUM_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "art_direction": {"type": "string", "minLength": 12, "maxLength": 180},
        "signature_moment": {"type": "string", "minLength": 8, "maxLength": 140},
        "copy_treatment": {"type": "string", "minLength": 8, "maxLength": 120},
        "mobile_adaptation": {"type": "string", "minLength": 8, "maxLength": 140},
        "risk_to_avoid": {"type": "string", "minLength": 8, "maxLength": 140},
    },
    "required": [
        "art_direction",
        "signature_moment",
        "copy_treatment",
        "mobile_adaptation",
        "risk_to_avoid",
    ],
}
