from __future__ import annotations


HARD_RUNTIME_RULES = """
GENERAL RULES:
- No external scripts, styles, images, fonts, fetch, iframes, document.write, localStorage, or sessionStorage.
- Use only local scripts: `/static/vendor/gsap.min.js`, `/static/vendor/Draggable.min.js`, `/static/vendor/lucide.min.js`, `/static/vendor/alpine.min.js`, `/static/vendor/matter.min.js`, `/static/vendor/paper-shaders/ndw-paper.js`, and `/static/js/ndw.js`.
- Matter.js is only for physics-first games and toys. Alpine UI state profiles are for carts, filters, drawers, selected records, and configuration.
- Three.js uses `import * as THREE from '/static/vendor/three.module.js'` and only the available local addon paths. Never use a bare `three` import or invent plugin paths such as ScrollTrigger.
- Use `id="ndw-content"` for the main stage. DOM references must exist before handlers run.
- Use addEventListener or Alpine x-on; never inline onclick/oninput/onchange handlers.
- The page runs in an iframe. Do not add host cleanup code. Keep one canvas/WebGL stage at most, use transforms/opacity, and avoid stacked blur/filter effects.

SELF QA:
1. Every visible control changes a named visible result, subject, score, selection, cart, preview, or payoff state.
2. First paint shows the primary subject and usable controls; no blank stage or placeholder shell.
3. No duplicate IDs, undefined text, raw TODO, visible `//`, planning headings, footer, or fake telemetry chrome.
4. Use readable contrast and the supplied palette roles, or a coherent authored palette when roles are intentionally absent. Do not default to dark/slate shells unless the selected playfield needs contrast.
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
- Use Canvas for game boards, drawing surfaces, and genuine simulations. Render a complete initial frame before interaction. Do not use Canvas as the primary surface for ordinary apps, commerce, booking, product pages, or record workflows.
""".strip()


PREMIUM_STYLE_GUIDANCE = """
PREMIUM BUILD GUIDANCE:
- The concrete format is the product. Use the task model and visual specification as the source of truth.
- Build the task itself with the visual specification's primary renderer, then use supporting renderers only where they reinforce its subject or state changes. `semantic_dom` means real HTML/CSS controls, records, products, and workflow state; it is not permission to make a generic dashboard.
- In guided mode, use `visual_spec.palette` as a reference strategy rather than a color quota. In authored mode, create a coherent light-first palette from the format and subject. White, near-white, neutral, or one-hue tonal pages are complete choices.
- Follow `visual_spec.visual_direction`: implement its content-bearing subject artwork and palette behavior, then author typography and component geometry as a coherent identity. Icons, wallpaper, and text labels are not substitutes for the subject.
- Implement `visual_spec.layout_model` according to its `composition_mode`: structured pages apply the viewport contract at the page root; authored pages preserve required regions and relationships while freely composing around the primary subject.
- Size `#ndw-content` around the selected topology and useful content. Avoid both a narrow centered card and artificially enlarged empty regions.
- Stay within `visual_spec.copy_budget`. Prefer visible state, objects, and affordances over explanatory paragraphs.
- A strong visual stack has a dominant subject, the supporting visual elements its composition actually needs, and one state-linked motion moment. It does not mean every available library must be loaded or that every site is limited to one primitive.
- Keep copy short, controls attached to what they affect, and make the site identifiable from the subject before body copy is read.
- Avoid generic AI-generated aesthetics: purple/blue gradients, centered card shells, dashboard telemetry, repetitive wave/grid wallpaper, emoji illustration systems, and arbitrary pastel combinations.
- Use original inline SVG, Canvas, CSS shapes, Paper Shaders, Matter bodies, or Three.js only when the visual specification calls for them.
""".strip()
