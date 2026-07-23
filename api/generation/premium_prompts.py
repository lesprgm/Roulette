from __future__ import annotations

import json
from typing import Any, Dict, List

from api.generation.prompts import HARD_RUNTIME_RULES, PREMIUM_RUNTIME_GUIDANCE, PREMIUM_STYLE_GUIDANCE

PREMIUM_SELF_REVIEW_CHECKLIST = """
Repair audit before final HTML:
1. Sandbox: remove remote resources, forbidden network APIs, localStorage/sessionStorage, document.write, eval, and invented local asset paths.
2. Initialization: every function referenced by HTML or a library exists before that library initializes. For Alpine `x-data="name()"`, define `window.name` before loading Alpine; use public Alpine state only, never `__x` internals or Alpine directives inside SVG.
3. References: every queried DOM id exists and every SVG numeric/path attribute has a valid non-empty value before first paint.
4. Control audit: remove every inline `on*` event attribute. For each visible button, input, select, and key/pointer action, trace element -> handler/expression -> changed state -> named visible DOM/SVG/Canvas result; the handler must use addEventListener or Alpine. Repair or remove any broken chain.
5. First paint: the primary subject, real starter content, and usable controls are visible immediately; Canvas/SVG scenes draw a complete initial frame without waiting for interaction.
6. Payoff: the primary loop can reach its declared completion/payoff, keeps the result visible, and offers the declared reset, replay, save, checkout, or continue action.
7. Games: verify rules, score/progress, collision or answer logic, failure/completion, restart, and keyboard/touch controls. Apps/tools/commerce: verify create/select/filter/configure/save and visible result or confirmation flows.
8. Visual and layout: implement visual_direction.subject_artwork, palette_behavior, component_language, and the selected surface_treatment, then preserve the layout model's regions, relationships, control placement, result transition, and mobile transformation. For `structured` composition_mode, root CSS must match the viewport contract. For `authored`, use the contract as a silhouette reference and freely layer, overlap, stagger, or reshape the regions when that gives the subject more presence. If surface_treatment.mode is `paper_shader`, verify exactly one named subject mounts the local shader, has a CSS fallback, and is not full-page wallpaper. Resolve the first viewport as a complete composition: never leave a tiny widget or shallow top strip surrounded by a blank field. Empty space may establish hierarchy, but the working subject, its state, and its payoff must collectively command the viewport. With text mentally blurred, the subject must remain recognizable through content-bearing artwork, objects, previews, diagrams, or scenes. Empty Canvas, icons, wallpaper, particles, oversized color fields, and repeated bordered panels do not count as meaningful content.
9. Copy: stay under copy_budget.max_visible_words, keep headings and instructions within their limits, and remove paragraphs that merely explain obvious controls.
10. Runtime: use only required local libraries, valid load order, bounded animation/canvas work, and no script error that prevents later handlers from registering.
11. Discipline: retain the recognizable format and remove blank panels, placeholders, dead controls, footer chrome, fake telemetry, planning language, `//`, TODO, undefined, and null.
In <self_review>, list only failures you found and corrected. Apply every correction to the one final HTML document; do not emit a draft HTML document.
""".strip()


VISUAL_ARTIFACT_GUIDANCE = """
Visual subject rules:
- The target's visual_spec.visual_subject is visible on first paint and changes with state, selection, progress, or payoff.
- Implement visual_spec.visual_direction.subject_artwork. A semantic-DOM page still needs task-native imagery, previews, diagrams, charts, maps, object illustrations, or other information-bearing visuals when its format calls for them.
- Use as many content-bearing visual elements as the composition needs. Do not reduce a product, destination, game world, or creative artifact to an icon, colored circle, or text label.
- Fill the selected viewport silhouette with task-native content. A narrow top cluster followed by an unused blank viewport is unfinished, not minimalist.
- `semantic_dom` means the product is built from semantic HTML, CSS layout, real records or products, and task state. Use Alpine only where its declarative state improves the workflow; do not replace the interface with a decorative Canvas.
- `inline_svg` means original SVG illustration, map, board, product, or record visualization; icons alone do not count. Its complete initial artwork must be static SVG markup. Update named SVG groups with plain JavaScript; never put `<template>`, Alpine directives, or Alpine-bound attributes inside SVG.
- `canvas_scene` means an initial rendered board, drawing, map, product view, or simulation scene; never an empty canvas.
- `matter_scene` means Matter.js owns visible physics, collisions, scoring, and reset while semantic DOM supplies only the necessary HUD and controls.
- `three_scene` means Three.js owns a genuinely spatial subject or interaction; do not use it for ordinary app, product, or commerce chrome.
- `paper_surface` means one named material surface using local Paper Shaders and `mountPaperShader(...)` with CSS fallback, never full-page wallpaper.
- `gsap_motion` means one state-linked reveal, transition, route, transformation, or payoff.
- `alpine_state` means task state such as cart, filter, drawer, selection, or configuration visibly drives the subject and result.
""".strip()


LAYOUT_MODEL_GUIDANCE = """
Layout model:
- `topology` is specific to the selected kind of product, game, tool, or workflow. It is not a decorative theme.
- `composition_mode` decides how strictly to apply the silhouette. For `structured`, apply root_display, root_columns, root_rows, edge_anchors, and scroll_axis at the page root. For `authored`, treat those fields as spatial guidance rather than required CSS and compose the required regions around the subject.
- Use dominant_region, control_region, and result_region to place real content. Never use any layout named in forbidden_shells, even if it would be easier for the selected format.
- Preserve the hierarchy and relationships in `regions`, `source_order`, `desktop_flow`, `control_placement`, and `result_transition`, while choosing sensible exact CSS dimensions from the content.
- Different topologies must produce different dominant axes, region proportions, control locations, and result behavior. An `authored` composition may use overlap, asymmetry, layering, floating regions, or deliberate broken-grid placement instead of visible column dividers. A palette swap or renamed panel does not count as a different layout.
- Side regions, overlays, docks, vertical journeys, maps, galleries, timelines, editorial spreads, and workspaces are allowed when the selected topology calls for them.
- Use semantic source order and transform it according to `mobile_transformation`; do not preserve a desktop split when it makes the mobile interaction worse.
""".strip()


def _prompt_target(target: Dict[str, Any]) -> Dict[str, Any]:
    format_spec = target.get("format_spec") if isinstance(target.get("format_spec"), dict) else {}
    task = target.get("task_model") if isinstance(target.get("task_model"), dict) else {}
    genre = target.get("genre_contract") if isinstance(target.get("genre_contract"), dict) else {}
    compact = {
        "site_index": target.get("site_index"),
        "seed": target.get("seed"),
        "format": {
            "id": format_spec.get("format_id"),
            "category": target.get("format_category"),
            "library_profile": format_spec.get("library_profile"),
        },
        "task_model": {
            key: task.get(key)
            for key in (
                "format",
                "user_goal",
                "domain_objects",
                "state_variables",
                "controls",
                "completion_condition",
                "payoff_scene",
                "error_states",
            )
        },
        "reward_contract": target.get("reward_contract") or task.get("reward_contract"),
        "primary_loop": target.get("primary_loop"),
        "reset_or_replay": target.get("reset_or_replay"),
        "mobile_interaction": target.get("mobile_interaction"),
        "genre": {
            key: genre.get(key)
            for key in ("page_genre", "visual_density", "motion_language", "instruction_policy", "chrome_policy")
        },
        "visual_spec": target.get("visual_spec"),
        "title_policy": target.get("title_policy"),
    }
    for key in ("art_direction", "signature_moment", "copy_treatment", "mobile_adaptation", "risk_to_avoid"):
        if target.get(key):
            compact[key] = target[key]
    return compact


def _output_protocol(index: int) -> str:
    return f"""===NDW_SITE_{index}_START===
<plan>Four short bullets: subject artwork; palette/type/surface identity; controls/state; payoff/motion.</plan>
<self_review>Concrete corrections applied to the final HTML.</self_review>
```html
<!doctype html>
...
```
===NDW_SITE_{index}_END==="""


def _build_rules() -> str:
    return f"""
Build rules:
- The backend `format` and `task_model` entries are mandatory. Implement their format, domain objects, visible state, controls, completion condition, and payoff scene.
- The visual_spec is mandatory. Treat its palette as a coherent strategy, not a requirement to display every supplied color. White space, neutral surfaces, and single-hue tonal depth are intentional when selected. Implement subject_artwork and the selected surface_treatment, then build the task with the primary renderer and use supporting renderers for meaningful artwork, state feedback, or motion. A `none` surface treatment means do not invent one.
- Use as many content-bearing visual elements as the composition needs. Original inline SVG, CSS illustration, Canvas, charts, diagrams, and task-native library output are allowed; Lucide icons, wallpaper, and color fields do not count by themselves.
- Implement `visual_spec.component_language` as the site's positive component system. Apply its geometry, borders, elevation, spacing, typography, and controls consistently without letting it replace the assigned topology, palette, or artwork.
- Implement visual_spec.layout_model according to composition_mode. Structured layouts honor the root viewport contract; authored layouts preserve the required content relationships but may depart from its literal tracks to make a stronger task-native composition. Do not reuse a familiar shell from another site.
- Let the selected topology determine whether the page is layered, split, sequential, editorial, map-led, gallery-led, board-like, or workspace-like. Use the viewport deliberately, but do not inflate empty regions merely to satisfy a fixed coverage percentage.
- Enforce visual_spec.copy_budget. Count user-visible words approximately; headings and the single micro-instruction have their own limits. Internal state and contracts must become behavior, not explanatory UI copy.
- Every control must change a visible subject, score, selection, cart, preview, route, receipt, saved result, or payoff. Remove controls that cannot.
- Games show the board/stage/player/targets and score immediately. Apps, commerce, and products show real starter content and one useful action immediately.
- Keep the main page light unless a game/canvas playfield needs contrast. Do not substitute generic white-card/dashboard layouts for the assigned composition.
- Use `surface_ink` for text on a colored surface. Use the least color needed to support the subject, hierarchy, and state; novelty must come from the experience and composition, not forced chromatic variety.
- Use `/static/design-kit/fonts.css` for local fonts. Do not use emoji as primary artwork or invent asset paths.
- Include reset/replay and touch fallback where the task declares them.

{VISUAL_ARTIFACT_GUIDANCE}

{LAYOUT_MODEL_GUIDANCE}

{HARD_RUNTIME_RULES}

{PREMIUM_RUNTIME_GUIDANCE}

{PREMIUM_STYLE_GUIDANCE}
""".strip()


def build_premium_burst_prompt(brief: str, seed: int, targets: List[Dict[str, Any]]) -> str:
    protocols = "\n\n".join(_output_protocol(index) for index in range(1, len(targets) + 1))
    layout_manifest = [
        {
            "site": target.get("site_index") or index,
            "format": (target.get("format_spec") or {}).get("format_id"),
            "topology": ((target.get("visual_spec") or {}).get("layout_model") or {}).get("topology"),
            "silhouette_family": ((target.get("visual_spec") or {}).get("layout_model") or {}).get("silhouette_family"),
            "composition_mode": ((target.get("visual_spec") or {}).get("layout_model") or {}).get("composition_mode"),
            "viewport_behavior": (((target.get("visual_spec") or {}).get("layout_model") or {}).get("viewport_contract") or {}).get("behavior"),
            "root_display": (((target.get("visual_spec") or {}).get("layout_model") or {}).get("viewport_contract") or {}).get("root_display"),
            "root_columns": (((target.get("visual_spec") or {}).get("layout_model") or {}).get("viewport_contract") or {}).get("root_columns"),
            "root_rows": (((target.get("visual_spec") or {}).get("layout_model") or {}).get("viewport_contract") or {}).get("root_rows"),
            "desktop_flow": ((target.get("visual_spec") or {}).get("layout_model") or {}).get("desktop_flow"),
            "control_placement": ((target.get("visual_spec") or {}).get("layout_model") or {}).get("control_placement"),
            "result_transition": ((target.get("visual_spec") or {}).get("layout_model") or {}).get("result_transition"),
            "component_language": ((target.get("visual_spec") or {}).get("component_language") or {}).get("id"),
        }
        for index, target in enumerate(targets, start=1)
    ]
    return f"""
Build {len(targets)} distinct premium interactive web experiences in one streaming response.

For each site, output exactly this compact protocol. The plan and self review are short text only; output one final HTML document, never a draft HTML document.

{protocols}

Do not output JSON or prose outside site markers.
Brief: {brief or 'Surprise me with bold, replayable mini-experiences.'}
Seed: {seed}

Per-site backend targets:
{json.dumps([_prompt_target(target) for target in targets], separators=(',', ':'), ensure_ascii=True)}

Burst layout manifest:
{json.dumps(layout_manifest, separators=(',', ':'), ensure_ascii=True)}
Before coding, compare this manifest across the whole batch. Apply exact root tracks only to `structured` sites. For `authored` sites, use the topology as a compositional brief and make the subject-led outlines visibly different; do not copy one site's DOM/CSS shell into another and merely change its content or colors.
The assigned component languages are intentionally different. Implement each positive system instead of carrying one site's borders, radii, shadows, typography, spacing, or controls into another.

{_build_rules()}

Internally assemble the implementation first, run the repair audit below against it, and apply those corrections directly to the single final document. Never emit the internal draft:
{PREMIUM_SELF_REVIEW_CHECKLIST}
""".strip()


def build_premium_plan_prompt(brief: str, seed: int, *, experience_target: Dict[str, Any], novelty: Dict[str, Any]) -> str:
    return f"""
Plan only the creative interpretation for one premium interactive mini-site.
Return JSON matching the compact schema. Do not restate or alter backend-owned format, task, reward, state, replay, mobile, genre, or visual-specification fields.

Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}
Backend target:
{json.dumps(_prompt_target(experience_target), separators=(',', ':'), ensure_ascii=True)}
Recent novelty summary:
{json.dumps(novelty, separators=(',', ':'), ensure_ascii=True)}

Choose a coherent art direction, one signature state-linked moment, concise copy treatment, a mobile adaptation, and one risk to avoid. The selected format and visual specification are mandatory; do not replace them with an abstract metaphor.
""".strip()


def build_premium_page_prompt(
    brief: str,
    seed: int,
    plan: Dict[str, Any],
    retry_note: str = "",
) -> str:
    retry_block = f"\nRepair note from local validation: {retry_note}\n" if retry_note else ""
    return f"""
Build one premium interactive mini-site.
Output only this compact protocol:
<plan>Four short bullets: subject artwork; palette/type/surface identity; controls/state; payoff/motion.</plan>
<self_review>Concrete corrections applied to the final HTML.</self_review>
```html
<!doctype html>
...
```

The plan and self-review are text only. Emit one final HTML document, never a complete draft followed by another complete document.
Do not output JSON.
Brief: {brief or 'Surprise me with a bold concept.'}
Seed: {seed}
Approved plan:
{json.dumps(_prompt_target(plan), separators=(',', ':'), ensure_ascii=True)}
{retry_block}

{_build_rules()}

Internally assemble the implementation first, run the repair audit below against it, and apply its fixes directly to the single final document. Never emit the internal draft:
{PREMIUM_SELF_REVIEW_CHECKLIST}
""".strip()
