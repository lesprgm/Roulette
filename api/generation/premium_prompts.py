from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from api.design_kit import compact_design_kit_manifest
from api.generation.prompts import HARD_RUNTIME_RULES, PREMIUM_STYLE_GUIDANCE


try:
    PREMIUM_BURST_MIN_HTML_BYTES = int(os.getenv("PREMIUM_BURST_MIN_HTML_BYTES", "3000"))
except Exception:
    PREMIUM_BURST_MIN_HTML_BYTES = 3000


PREMIUM_SELF_REVIEW_CHECKLIST = f"""
Before final HTML, verify and fix:
- Forbidden APIs used? no. Do not use fetch, XMLHttpRequest, WebSocket, Worker, SharedWorker, eval, Function, or document.write.
- Remote resources used? no. No remote scripts, styles, images, media, fonts, or CSS url() assets.
- Local scripts/imports only? yes. Allowed script src values are `/static/vendor/tailwind-play.js`, `/static/vendor/gsap.min.js`, `/static/vendor/Draggable.min.js`, `/static/vendor/lucide.min.js`, `/static/vendor/alpine.min.js`, `/static/vendor/matter.min.js`, `/static/vendor/paper-shaders/ndw-paper.js`, and `/static/js/ndw.js`; do not invent plugin paths such as ScrollTrigger. Three.js imports must use `/static/vendor/three.module.js`; addons may only use local OrbitControls, DragControls, TransformControls, CSS2DRenderer, EffectComposer, RenderPass, or UnrealBloomPass files. Paper Shaders should use the allowed script src and global `mountPaperShader(...)`; module imports are also allowed from local `/static/vendor/paper-shaders/` modules.
- Complete and substantial? yes. Include doctype/html/head/body, visible #ndw-content, and Final HTML must be at least {PREMIUM_BURST_MIN_HTML_BYTES} bytes.
- Format and task intact? yes. activity_contract.activity_variant is the product; semantic anchors flavor it but must never rename, obscure, or replace it.
- Useful first screen? yes. Show the board/stage/cards/player/products/sample records/starter artifact immediately; no blank splash, empty container, or generic centered-card shell.
- Interaction real? yes. Controls visibly change state, score/progress/result, created output, saved selection, checkout/receipt, win/loss, or replay state.
- Payoff scene real? yes. After the primary action, the page shows the task_contract.payoff_scene result moment, not just a button color change or static confirmation line.
- Reward contract real? yes. Implement reward_contract.user_action -> immediate_feedback -> progress_state_change -> payoff_moment within 5-15 seconds -> continue_reason.
- Event wiring reliable? yes. No inline onclick/oninput/onchange handlers; use addEventListener after DOM refs exist, or Alpine x-on/@click when the selected library_profile is alpine_ui_state.
- Alpine state order reliable? yes. If using `x-data="storeName()"`, define `window.storeName = () => ({...})` before loading `/static/vendor/alpine.min.js`, or use an inline x-data object.
- Control inventory complete? yes. List every visible button/input/select/slider/key action in self_review, name the handler/state it changes, and remove any control that cannot produce visible feedback. No empty button labels, icon-only mystery buttons, disabled-looking controls, or decorative controls.
- Runtime click-through mentally simulated? yes. For each primary control, trace: DOM element exists -> handler exists in the same scope -> state variable changes -> visible text/DOM/canvas/SVG/class/style changes -> payoff/result remains visible. Fix any broken link in that chain before final HTML.
- Result surfaces visible? yes. The page has named places where changed state appears: score, cart, receipt, route, ticket, selected card, saved row, generated preview, before/after, level clear, or completion panel. Do not rely on hidden state or console logs.
- Genre disciplined? yes. Follow genre_contract.copy_density, palette strategy, instruction policy, visual density, motion language, and chrome policy.
- Palette coherent? yes. Use a deliberate color system, not random color soup: one background family, one surface family, one dominant action accent, optional secondary accent, clear state colors, and readable text contrast. Avoid generic AI palettes such as purple/blue gradients, neon soup, cream/orange dashboard defaults, and glassy glowing cards unless the selected genre explicitly needs that look.
- Background appropriate? yes. Do not default to dark/slate/black/terminal shells. Use light, warm, bright, or neutral page backgrounds unless the selected game/canvas explicitly needs a dark playfield for contrast.
- Semantic anchors embodied or hidden? yes. Any visible anchor word in title/copy is also expressed through material, shape, texture, motion, interaction feedback, or UI metaphor. Do not expose material anchors as spec labels such as "Material:", "Finish:", "Chassis material:", or "[material] finish"; if the material is not part of a real product spec, keep it visual only.
- Copy clean? yes. No literal "Onboarding", "Instructions", "Visitor Role", "Primary Loop", "Feedback Contract", jargon/host-brand words, `//`, TODO, undefined, null, markdown fences, raw JSON, or code-comment debris.
- Content complete? yes. No empty slots, missing images, placeholder-only panels, blank products, blank tables, or controls that do not visibly change page state.
- Chrome restrained? yes. No footer, copyright strip, fake department/division sign-off, telemetry rail, protocol label, calibration readout, or decorative dashboard chrome unless it is the selected app's actual functional content.
- Content-bearing visual artifacts? yes. The page includes at least one visual object/stage/output users can name. More is welcome when it supports the format. Panels, buttons, badges, icons, gradients, and wallpaper do not count.
- Game/app specifics correct? yes. Games show a high-contrast first frame, score/result/restart, and recognizable names such as Snake, Breakout, Platform, Tic-Tac-Toe, Quiz, Memory Match, or Word Game. Apps/products show sample content, one obvious action, and useful feedback.
- Runtime safe? yes. DOM references exist before use; audio only starts from a click/tap/key/pointer handler; WebGL/canvas/particles stay lightweight.
If any answer is not safe/yes, rewrite before the final fenced HTML block.
""".strip()


VISUAL_ARTIFACT_GUIDANCE = """
Content-bearing visual rule:
- Every site needs at least one content-bearing visual artifact, not just styled UI chrome.
- Games: visible board/stage/player/enemies/items/targets, preferably Canvas/SVG/CSS shapes.
- Product/storefront: generated product illustration, package/device/item, variants/thumbnails, cart/receipt.
- Restaurant/commerce/booking: menu/product cards plus route/map/ticket/calendar/receipt/tracker visual.
- SaaS/workspace/data: realistic records, chart/table/kanban/map/inbox/file cards with meaningful sample content.
- Creative tools/editors: visible canvas, artifact, preview, sequencer grid, drawing, palette, or export result.
- Simulators/toys: visible object/world/stage whose state changes, not just sliders/meters.
- Backgrounds, gradients, icons, panels, badges, buttons, and text do not count as content-bearing visual artifacts.
- Use inline SVG, CSS shape systems, Canvas, Matter.js, or Three.js when useful; keep it lightweight and tied to the selected format.
""".strip()


def build_premium_burst_prompt(brief: str, seed: int, targets: List[Dict[str, Any]]) -> str:
    return f"""
Build {len(targets)} distinct premium interactive web experiences in one streaming response.

Output format is mandatory and repeated once per site:
===NDW_SITE_1_START===
	<thinking>One short semantic plan for site 1.</thinking>
	<draft>Initial complete HTML draft.</draft>
	<self_review>Answer the hard reject checklist below, then list concrete fixes applied before final HTML.</self_review>
```html
<!doctype html>
...
```
===NDW_SITE_1_END===

Then site 2, site 3, etc. Use matching numbers in START and END markers.
Do not output JSON. Do not include prose outside site markers.

Brief: {brief or 'Surprise me with bold, replayable mini-experiences.'}
Seed: {seed}

Per-site creative targets. Each site must feel unrelated to the others:
{json.dumps(targets, indent=2)}

Experience contract for every site:
- Build the activity_contract, not just the aesthetic. Each site must be a mini app/game/tool/workflow with goal, visible state, and payoff.
- Use activity_contract.activity_variant as the exact concrete format. Do not collapse it into snake, tic-tac-toe, quiz, sliders, or a hidden-object reveal unless that exact variant was selected.
- Retention first: within three seconds the visitor should know what it is, what to do, and why trying again could be fun/useful.
- Payoff first: every site must implement task_contract.payoff_scene as a visible result moment after the primary action, then offer the listed continue_action.
- Static first content rule: Games need a visible board/stage/cards/player/towers on first paint, controls, score/result, restart, win/loss/completion, and at least one meta-reward: streak, combo, lives, best score, tickets, medals, levels, or unlocks. Use clear names such as Breakout, Minesweeper, 2048, Rhythm Tap, Maze, Snake, Platform, Tic-Tac-Toe, Quiz, Memory Match, or Word Game.
- Simple game visibility rule: do not ship a splash-only start; show the playable board/stage/cards/player immediately.
- Apps/workspaces/commerce/products, including saas_replica targets, must preload realistic sample data: representative cards, records, products, rows, items, thumbnails, or options directly in initial HTML; one click/edit must produce a useful result. No blank tables, empty slots, or placeholder-only workflow.
- Product/storefront pages need product hero, price/plan, benefits/specs, variant selector, and add-to-cart/reserve/buy/compare action with checkout/cart/receipt/selected-plan payoff.
- Creative tools need a created/configured/composed output. Puzzle boxes need clues or visible puzzle-state changes; do not default to hidden-object reveals.
- Use physical metaphors only when they clarify interaction: arcade cabinet, board, deck, receipt, ticket printer, paper tray, counter, dial, workbench, cards, shelves, map, or machine.
- Paper Shaders is optional for one content-bearing material/hero surface only. If used, include `<script src="/static/vendor/paper-shaders/ndw-paper.js"></script>`, call global `mountPaperShader(...)`, choose one preset from `paperTexture`, `staticMeshGradient`, `grainGradient`, `halftoneDots`, `halftoneCMYK`, `flutedGlass`, `liquidMetal`, `godRays`, `smokeRing`, `gemSmoke`, `water`, `neuroNoise`, `voronoi`, or `metaballs`, and keep it tied to the selected format. Do not use it as generic wave/grid wallpaper.
- Follow activity_contract.library_profile. Use the matching local primitive deeply: NDW for canvas/game loops, Alpine for app/tool/commerce UI state, Matter for physics games/toys, GSAP for DOM state choreography, Lucide for app/workspace affordances, or Three.js for one explorable spatial focal scene.
- Make the premise and first action visible without literal planning labels or tutorial sections. Ban visible headings like "Onboarding", "Instructions", "Visitor Role", "Primary Loop", and "Feedback Contract" unless documentation_allowed.
- Respect each site's genre_contract when present: copy density, instruction policy, chrome policy, palette strategy, and motion language.
- Implement a primary loop: user action -> visible response -> state change -> reward/payoff -> continue reason. Avoid slider-only sites unless activity_type is interactive_instrument or simulation, and never let controls merely change ambient visuals.
- The reward/payoff must feel like a mini climax: delivery tracker, receipt, ticket, score burst, win/loss, generated artifact, saved workflow, comparison result, route, report, or configured preview depending on the format.
- Build from a small explicit state model. Define the core state object/Alpine store first, then render controls and outputs from it. Avoid scattered one-off handlers that mutate unrelated DOM nodes.
- Every visible control must have a nearby visible output/result it affects. If a control cannot update score/progress/selection/cart/result/preview/canvas/SVG/class/text, remove it before final HTML.
- Button labels must be concrete user actions such as Play, Reset, Add to cart, Compare, Save, Shuffle, Draw, Filter, Book, Launch, Match, or Export. Do not use internal words such as calibrate, protocol, flush, manifest, system, simulation, or division.
- Use semantic anchors as interaction/content/motion logic, not just labels or colors.
- Embody or hide semantic anchors: if a material/object/metaphor word appears visibly, express it in the interface. Materials must affect at least two layers such as texture, border, shape, shadow, motion, interaction feedback, inline SVG, Canvas, or 3D material. Do not render generic material-spec copy like "MATERIAL:", "FINISH:", "NATURAL RED CLAY FINISH", "Chassis material", or "[anchor] alloy"; those labels are plan leakage unless the selected format is genuinely a product spec page.
- Include reset/replay when appropriate.
- Include mobile-friendly pointer/touch/keyboard fallback.

{VISUAL_ARTIFACT_GUIDANCE}

Local design kit manifest:
{compact_design_kit_manifest()}

	Premium burst requirements:
- Each site must include a complete final fenced html block inside its markers.
- Each site must be a complete document with `<html>`, `<head>`, and `<body>`.
- Each site must have a different layout/composition and primary interaction model.
- Use at least one local design-kit asset or font in each site.
- Use GSAP for at least one timeline on non-canvas, non-game pages by including `<script src="/static/vendor/gsap.min.js"></script>` and calling `gsap.timeline(...)`; game pages may use requestAnimationFrame instead.
- Keep one focal area, short human-facing copy, controls near what they affect, and no cluttered multi-panel shell unless genre_contract calls for dense/maximal.
- Do not add a footer, copyright bar, division label, legal strip, or fake organization sign-off. End with the actual activity result, replay/reset, receipt, score, generated artifact, or next useful action.
- Use palette roles, not scattered colors: 60/30/10 balance, readable contrast, one dominant action accent, one optional secondary accent, and no clashing neon-on-neon unless the genre is explicitly arcade/maximal. Avoid generic AI palettes: purple/blue gradients, neon soup, cream/orange dashboard defaults, and glassy glowing cards unless the selected format specifically calls for them.
- Non-empty first screen rule: every site must show player/targets, sample cards, product hero, prefilled records, starter artwork, furnished layout, route, thumbnails, seed cards, or preview artifact before interaction.
- Visual artifact rule: each site must include at least one content-bearing visual object/stage/output. UI chrome alone is not enough.
- Canvas/game first paint rule: draw a high-contrast stage immediately; a Play button may overlay gameplay but must not replace it with a blank/Initialize splash. Puzzle/game cue rule: one short cue near the board.
- Background discipline: do not use wave/grid/contour/dot wallpaper as the default visual identity. Use surfaces, product visuals, cards, maps, boards, canvases, shelves, or app content as the visual mass.
- Avoid visible jargon and host-brand leakage: calibration, protocol, terminal, compiler, telemetry, lux, signal, frequency, drift, manifest, system, Roulette, NDW, No Delay Wireless, runtime, non-deterministic. Ban visible artifacts: `//`, TODO, undefined, null, raw JSON, markdown fences, and visible planning terminology.
- Treat activity_type values such as simulation as internal planning labels, not UI copy. Do not label buttons "Run Simulation" or "Start Simulation"; use concrete action verbs from the format instead, such as Grow, Remix, Shake, Tune, Release, Forecast, Reset, or Play.
- Every control must advance a goal, score/progress, created output, configured result, unlocked reveal, selected record, or saved state.
- Do a control audit in `<self_review>`: for each button/input/slider/key action, state the visible element that changes. If any control has no visible changed element, rewrite or delete it.
- If you include local fonts, use `<link rel="stylesheet" href="/static/design-kit/fonts.css">`.
- Three.js core must use: `import * as THREE from '/static/vendor/three.module.js';`. Addons must use direct local `/static/vendor/three-addons/...` imports.
	- The app renders this HTML in an iframe, so no host cleanup code is required.

	Hard reject self-review checklist for every site:
	{PREMIUM_SELF_REVIEW_CHECKLIST}
	
	{HARD_RUNTIME_RULES}

{PREMIUM_STYLE_GUIDANCE}
"""


def build_premium_plan_prompt(brief: str, seed: int, *, experience_target: Dict[str, Any], novelty: Dict[str, Any]) -> str:
    target = experience_target
    return f"""
Plan one premium random interactive mini-site.
Return JSON only matching the provided schema.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}

Goals:
- Resolve the concrete activity format first. The selected activity_contract.activity_variant is the product, not a vibe.
- Choose one strong art direction and one signature interaction/motion system. Do not average styles.
- Use the local design kit manifest below. Choose a palette_key as your base color foundation, or omit it and design your own color system. Also choose layout_key, motion_preset, display_font_key, and body_font_key.
- Create original inline SVG illustrations, CSS shapes/gradients, canvas artwork, or format-specific UI visuals when the page needs custom graphics.
- Avoid recent visual trends from the novelty summary.
- Favor recognizable, useful formats people can immediately try: arcade games, puzzle games, card/word/quiz games, product pages, ecommerce storefronts, pricing pages, booking/catalog flows, workspace apps, map explorers, record investigations, drawing/music tools, simulators, and configurators.
- Plan first-screen content and one obvious action. Apps/tools/commerce pages need sample records/items/options. Product/storefront pages need a hero product/offer, price/plan, benefits/specs, options, and a buy/reserve/add-to-cart/compare action. Games need score/result/restart plus one meta-reward: streak, combo, best score, lives, tickets, medals, levels, or unlocks.
- Plan at least one content-bearing visual artifact for the selected format. It must be an actual object/stage/output/map/board/product/preview/record set, not merely a background, button cluster, icon row, or card shell.
- Avoid generic dashboards unless activity_type is saas_replica or data_investigation and the dashboard has a real workflow: filtering records, saving selections, triaging tickets, or configuring a result.
- Ban visible sci-fi filler and host-brand words: calibration, protocol, terminal, compiler, telemetry, lux, signal, frequency, drift, manifest, system, Roulette, NDW, No Delay Wireless, runtime, and non-deterministic.
- Include a physical metaphor when it clarifies the activity: arcade cabinet, board, deck, receipt, ticket printer, paper tray, counter, dial, workbench, cards, shelves, map, or machine.
- Avoid a single centered card unless the chosen layout explicitly calls for it.
- Fill prompt_genome with a compact creative mutation for this generation only. Do not mutate runtime rules, output schema, allowed libraries, cleanup rules, or asset policy.
- Fill fingerprint with how this plan should be remembered after serving.
- Treat the experience target below as mandatory positive steering. Do not merely style around it; make it the behavior of the page.
- Treat semantic anchors as Tier 2 flavor only: they may influence texture, object names, mood, copy, and micro-interactions, but they must not rename, obscure, or override the selected activity_variant.
- Follow title_policy: semantic anchor words must be embodied or hidden. Do not keyword-stuff anchors into titles or major labels; games/tools/products should keep the recognizable format name dominant. Material anchors should usually appear as surface treatment, not text.
- Material anchors must be synthesized with browser-native code when used visibly: CSS repeating gradients, layered backgrounds, pseudo-elements, border styles, inline SVG patterns/filters, Canvas procedural strokes/noise, or Three.js material only when the selected page already needs 3D.
- Paper Shaders may be used as one optional material embodiment layer for paper/cardboard, print/halftone, fluted glass, liquid metal, light rays, smoke/gem atmospherics, cells, liquid blobs, or a hero object surface. It should support the format, not replace the app/game/tool content.
- Fill task_contract before visual decisions. It must define the user goal, domain objects, state variables, controls with must_change_state, completion_condition, error_states, and allowed_patterns. The task_contract is the content layer; semantic anchors, palette, waves, glows, particles, and atmospheric motion are optional.
- task_contract.payoff_scene is mandatory: it defines what satisfying thing happens after the primary action and why a user would keep going.
- reward_contract is mandatory: every site must produce a visible payoff within 5-15 seconds. Do not use a decorative color change as the reward.
- Fill semantic_translation by translating every semantic anchor into visual_role, interaction_role, content_role, and motion_role.
- Fill activity_type, activity_contract.activity_variant, activity_contract.core_mechanic, and activity_contract.library_profile before style decisions. The activity must be a concrete mini app/game/tool/workflow, not a decorative control panel or abstract metaphor.
- Fill genre_contract as the art-direction governor. Copy density, instruction policy, palette strategy, visual density, motion language, and chrome policy must form one coherent genre instead of independent random choices.
- The primary_loop is the core product contract: user_action, visible_response, state_change, reward_or_payoff, and continue_reason must be specific.
- primary_loop.reward_or_payoff must directly implement task_contract.payoff_scene.scene.
- Avoid slider-only plans unless activity_type is interactive_instrument or simulation, and even then sliders need a visible result/payoff.
- The onboarding_cue must be a diegetic micro-cue, label, placeholder, cursor affordance, or short CTA. No tutorial panel unless genre_contract.instruction_policy is documentation_allowed.
- Fill mobile_interaction with a specific touch/small-screen fallback. Fill reset_or_replay with a visible replay affordance.

{VISUAL_ARTIFACT_GUIDANCE}

Experience target:
{json.dumps(target, separators=(",", ":"), ensure_ascii=True)}

Novelty summary from recently served pages:
{json.dumps(novelty, separators=(",", ":"), ensure_ascii=True)}

Local design kit manifest:
{compact_design_kit_manifest()}
"""


def build_premium_page_prompt(
    brief: str,
    seed: int,
    plan: Dict[str, Any],
    retry_note: str = "",
) -> str:
    retry_block = f"\nRetry note:\n- {retry_note}\n" if retry_note else ""
    return f"""
Build one premium interactive mini-site.
	Use one-shot meta-correction. Output in this exact order:
	<thinking>Brief semantic plan, selected local libraries/assets, and one risk to avoid.</thinking>
	<draft>Initial complete HTML draft.</draft>
	<self_review>Answer the hard reject checklist below, then list concrete fixes applied before final HTML.</self_review>
```html
<!doctype html>
...
```

Only the final fenced html block will be served. Do not output JSON.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}

Approved premium plan (follow exactly):
{json.dumps(plan, indent=2)}

Experience contract:
- The activity_type and activity_contract are mandatory. Build the page as a specific mini activity, not as an abstract visual artifact.
- The selected activity_contract.activity_variant is the product. Semantic anchors are flavor and must never rename, obscure, or replace the recognizable format.
- The task_contract is mandatory. Implement its domain_objects, state_variables, controls, completion_condition, and allowed_patterns. Do not invent decorative controls outside that task model.
- Implement task_contract.payoff_scene.trigger, scene, and continue_action. This is the user's reward moment; do not reduce it to "confirmed" text.
- Implement reward_mechanic and reward_contract exactly: user action, immediate feedback, progress/state change, payoff moment within 5-15 seconds, and reason to continue. A button changing color is not a payoff.
- Static first content rule: show meaningful content immediately. Games show board/stage/player/targets/score; apps show sample records/cards/table; product/ecommerce pages show product visual, price/plan, benefits/specs, variants, and checkout/cart/receipt feedback; creative tools show a starter preview/artifact.
- Visual artifact rule: include at least one content-bearing visual object/stage/output users can name. Panels, buttons, icons, gradients, and decorative backgrounds do not count.
- Format rules: breakout_paddle plays like Breakout, minesweeper_grid like Minesweeper, tile_merge_2048 like 2048, rhythm_tap like a timing game, etc. Games/quizzes need recognizable names, keyboard/touch/pointer controls, score/result, restart, win/loss/completion, and score plus one meta-reward.
- Simple game visibility rule: do not ship a splash-only start; show the playable board/stage/cards/player immediately.
- Workflow rules: saas_replica, commerce, booking, product_or_storefront, data, builder, editor, and tool pages need sample items/options and one obvious action that produces a useful result. A product_or_storefront target must feel like a product/ecommerce website. No blank tables, empty slots, placeholder-only panels, setup-first flows, or decorative-only controls.
- Follow genre_contract.copy_density, palette_strategy, chrome_policy, instruction_policy, visual_density, and motion_language. Use one dominant action accent, one optional secondary accent, readable contrast, and no generic fake telemetry.
- Keep color decisions genre-appropriate: one background family, one surface family, one dominant action accent, optional secondary accent, clear disabled/error/success states, and no arbitrary rainbow palette unless the format needs it. Avoid generic AI palettes: purple/blue gradients, neon soup, cream/orange dashboard defaults, and glassy glowing cards unless the selected format specifically calls for them.
- Keep the main page background light, warm, bright, or neutral unless the selected format is a game board/canvas that needs contrast. Do not make dark mode, black dashboards, slate shells, or terminal-like pages the default visual language.
- Do not add a footer, copyright bar, legal strip, fake department signature, or organization sign-off. Generated pages are single-screen experiences; finish on the activity payoff and replay/next action.
- The onboarding cue must be a diegetic micro-cue, placeholder, label, cursor affordance, or short CTA. Do not create a section titled "Onboarding", "Instructions", "How to use", "Primary Loop", or "Feedback Contract" unless documentation_allowed.
- Keep the first screen legible in three seconds: clear title, obvious action target, visible score/progress/result, and no lecture. Puzzle/game cue rule: add one short cue near the board, e.g. "Use arrows", "Match two cards", or "Avoid mines".
- Avoid recurring wave/grid wallpaper. Avoid visible jargon: calibration, protocol, terminal, compiler, telemetry, lux, signal, frequency, drift, manifest, system, Roulette, NDW, No Delay Wireless, runtime, non-deterministic.
- Treat internal activity_type values such as simulation as implementation labels only. User-facing buttons should use concrete format verbs like Grow, Remix, Shake, Tune, Release, Forecast, Reset, or Play, not "Run Simulation".
- The primary_loop must be implemented, not just described. Every planned task_contract control must visibly change at least one listed must_change_state value, and completion_condition must appear as result/status/score/saved state/preview/receipt/win-loss/final summary.
- The payoff_scene must appear as an actual UI/state moment: animated delivery route, ticket/pass, cart/receipt, score burst, generated artifact, saved workflow, comparison, report, configured preview, or equivalent format-specific result.
- Implement the payoff as a persistent visible section/card/stage state, not an alert, console log, temporary toast only, or hidden variable.
- Empty/icon-only controls are not acceptable. Every button needs readable text or an aria-label plus adjacent visible label; primary actions need visible text.
- Do not ship a slider-only page unless activity_type is interactive_instrument or simulation; even then include a payoff/result/replay beyond changing meter values.
- The semantic_translation must drive interaction, content, motion, and visual treatment. Include reset/replay and mobile_interaction when declared.
- Follow title_policy. If an anchor appears in visible title/copy, embody it in at least two UI layers; otherwise keep it implicit and out of major labels. Avoid material-spec leakage such as "Material:", "Finish:", "Chassis material", or "[anchor] finish" unless the page is a real product/spec comparison and the spec affects the UI.

{VISUAL_ARTIFACT_GUIDANCE}

Local design kit manifest:
{compact_design_kit_manifest()}

Premium build requirements:
- Use at least one local design-kit asset or font selection from the approved plan, and deliver one signature motion moment such as parallax drift, layered reveal, kinetic meter motion, or a restrained Three.js scene.
- Follow activity_contract.library_profile: include `/static/js/ndw.js` for NDW profiles, `/static/vendor/alpine.min.js` for Alpine UI state profiles, `/static/vendor/matter.min.js` for Matter physics profiles, `/static/vendor/gsap.min.js` for GSAP profiles, `/static/vendor/Draggable.min.js` after GSAP when the page has one draggable DOM object/control, `/static/vendor/lucide.min.js` plus `lucide.createIcons()` for Lucide app chrome, and local Three module imports for Three profiles. Use the chosen library for the core interaction, not just a decorative flourish.
- Alpine pages must define state before Alpine loads: put `window.storeName = () => ({ ... })` before `<script defer src="/static/vendor/alpine.min.js"></script>`, then use `x-data="storeName()"`; or use inline object state directly in `x-data`.
- Optional Paper Shaders usage: include `<script src="/static/vendor/paper-shaders/ndw-paper.js"></script>` and call global `mountPaperShader(...)` for one lightweight shader surface when it clearly helps the material, product hero, game board, card deck, map, poster, receipt, or generated artifact. Prefer `flutedGlass`/`liquidMetal` for products, `halftoneCMYK`/`halftoneDots`/`grainGradient` for posters and print, `metaballs`/`voronoi`/`smokeRing` for games and toys, and `godRays`/`water`/`gemSmoke` for atmospheric hero surfaces. Do not use it for recurring wave/grid wallpaper or full-page decoration that hides the actual activity.
- Maintain one clear focal area; controls stay near what they affect. Include an activity payoff within 10 seconds: completed set, saved configuration, unlocked reveal, created artifact, score/result, selected record, generated preview, cart/receipt, or selected plan.
- Fill the page with real starter content: sample records, products, cards, game pieces, board state, editor output, or configured preview. Remove any empty slots or placeholder panels that are not functional.
- Prefer fewer working controls over many fragile controls. A polished page with 2-4 reliable actions is better than a busy page with dead buttons.
- Treat ambient backgrounds as optional. If task_contract.visual_budget says ambient_background is not primary, do not spend the main interaction on waves, ripples, particles, or atmospheric loops.
- Visible copy must be human-facing, not plan-facing. Ban visible artifacts: `//`, TODO, undefined, null, markdown fences, raw JSON, "onboarding instructions", "visitor role", "primary loop".
- If you include local fonts, use `<link rel="stylesheet" href="/static/design-kit/fonts.css">`.
- Create original inline SVG/CSS/canvas artwork when needed; do not invent local asset paths.
- Generate material textures inline with CSS/SVG/Canvas/Three when useful. Do not depend on texture libraries or static overlay assets.
	- Three.js core must use `import * as THREE from '/static/vendor/three.module.js';`; addons must use direct local `/static/vendor/three-addons/...` imports.
	- Since the app renders this HTML in an iframe, no host cleanup code is required; still avoid memory leaks inside the page.
	- The final fenced block must be a complete document with `<html>`, `<head>`, and `<body>`.
	{retry_block}

	Hard reject self-review checklist:
	{PREMIUM_SELF_REVIEW_CHECKLIST}
	
	{HARD_RUNTIME_RULES}

{PREMIUM_STYLE_GUIDANCE}
"""
