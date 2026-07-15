from __future__ import annotations

import json
from typing import Any, Dict, List

from api.generation.prompts import HARD_RUNTIME_RULES, PREMIUM_RUNTIME_GUIDANCE, PREMIUM_STYLE_GUIDANCE

PREMIUM_SELF_REVIEW_CHECKLIST = """
Repair audit before final HTML:
1. Sandbox: remove remote resources, forbidden network APIs, localStorage/sessionStorage, document.write, eval, and invented local asset paths.
2. Initialization: every function referenced by HTML or a library exists before that library initializes. For Alpine `x-data="name()"`, define `window.name` before loading Alpine; use public Alpine state only, never `__x` internals or Alpine directives inside SVG.
3. References: every queried DOM id exists and every SVG numeric/path attribute has a valid non-empty value before first paint.
4. Control audit: for each visible button, input, select, and key/pointer action, trace element -> handler/expression -> changed state -> named visible DOM/SVG/Canvas result. Repair or remove any broken chain.
5. First paint: the primary subject, real starter content, and usable controls are visible immediately; Canvas/SVG scenes draw a complete initial frame without waiting for interaction.
6. Payoff: the primary loop can reach its declared completion/payoff, keeps the result visible, and offers the declared reset, replay, save, checkout, or continue action.
7. Games: verify rules, score/progress, collision or answer logic, failure/completion, restart, and keyboard/touch controls. Apps/tools/commerce: verify create/select/filter/configure/save and visible result or confirmation flows.
8. Visual and layout: use the assigned palette anchors and primary renderer, preserve every layout-model node/relation, geometry_contract, and viewport_contract. Inspect the final CSS: `#ndw-content` fills the viewport, the composed regions use at least 88vw x 78dvh, and no small centered card or persistent stage-plus-sidebar shell contains the experience. Empty Canvas, wallpaper, particles, and oversized color fields do not count as meaningful viewport content.
9. Copy: stay under copy_budget.max_visible_words, keep headings and instructions within their limits, and remove paragraphs that merely explain obvious controls.
10. Runtime: use only required local libraries, valid load order, bounded animation/canvas work, and no script error that prevents later handlers from registering.
11. Discipline: retain the recognizable format and remove blank panels, placeholders, dead controls, footer chrome, fake telemetry, planning language, `//`, TODO, undefined, and null.
In <self_review>, list only failures you found and corrected. Apply every correction to the one final HTML document; do not emit a draft HTML document.
""".strip()


VISUAL_ARTIFACT_GUIDANCE = """
Visual subject rules:
- The target's visual_spec.visual_subject is visible on first paint and changes with state, selection, progress, or payoff.
- `inline_svg` means original SVG illustration, map, board, product, or record visualization; icons alone do not count.
- `canvas_scene` means an initial rendered board, drawing, map, product view, or simulation scene; never an empty canvas.
- `paper_surface` means one named material surface using local Paper Shaders and `mountPaperShader(...)` with CSS fallback, never full-page wallpaper.
- `gsap_motion` means one state-linked reveal, transition, route, transformation, or payoff.
- `alpine_state` means task state such as cart, filter, drawer, selection, or configuration visibly drives the subject and result.
""".strip()


LAYOUT_MODEL_GUIDANCE = """
Layout model DSL:
- desktop_geometry: `full_bleed` fills the viewport; `vertical_journey` stacks premise/stage/action/result across broad horizontal zones; `offset_canvas` offsets the focal region with one edge overlap; `mosaic_focus` uses one dominant asymmetric cell plus smaller cells; `poster_field` layers distinct zones in one poster-like field.
- control edge: `floating_tray`, `bottom_dock`, `top_ribbon`, `inline_cluster`, or `collapsible_sheet` describes the controls' relationship to the primary node.
- result edge: `replace_controls`, `bottom_sheet`, `stage_overlay`, `inline_after`, or `focused_modal` describes the payoff transition.
- geometry_contract contains measurable viewport occupation and wrapper constraints. Treat those as acceptance criteria, not suggestions.
- viewport_contract applies to every geometry: `#ndw-content` is 100vw with at least 100dvh, composed regions occupy at least 88vw x 78dvh on desktop, blank background stays below 40%, and the whole experience is never enclosed in one card.
- Use semantic source order and CSS Grid/Flex/positioning. Follow mobile_transformation and never invent a persistent right rail unless the graph explicitly requires one.
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
<plan>Four short bullets: subject, controls/state, render stack, payoff.</plan>
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
- The visual_spec is mandatory. Treat its palette values as anchor colors and derive a coherent tonal system with tints, shades, translucent states, and localized contrast where useful. Build its visual subject using the primary renderer, then apply the listed supporting renderers only where useful.
- Implement visual_spec.layout_model literally: create its named regions, preserve its spatial edges, follow desktop/mobile geometry, and do not substitute the familiar header + left stage + persistent right control rail.
- Implement layout_model.geometry_contract and viewport_contract literally. A single centered rounded rectangle containing the whole experience, a narrow root `max-width`, or more than 40% unused viewport is a failed layout and must be rebuilt before output. Cards may exist only as child regions inside the larger composition.
- Enforce visual_spec.copy_budget. Count user-visible words approximately; headings and the single micro-instruction have their own limits. Internal state and contracts must become behavior, not explanatory UI copy.
- Every control must change a visible subject, score, selection, cart, preview, route, receipt, saved result, or payoff. Remove controls that cannot.
- Games show the board/stage/player/targets and score immediately. Apps, commerce, and products show real starter content and one useful action immediately.
- Keep the main page light unless a game/canvas playfield needs contrast. Do not substitute generic white-card/dashboard layouts for the assigned composition.
- Use `surface_ink` for text on the supplied surface color. Do not dilute every palette into a pale background plus near-white cards; use decisive color blocking and readable chromatic contrast.
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
    return f"""
Build {len(targets)} distinct premium interactive web experiences in one streaming response.

For each site, output exactly this compact protocol. The plan and self review are short text only; output one final HTML document, never a draft HTML document.

{protocols}

Do not output JSON or prose outside site markers.
Brief: {brief or 'Surprise me with bold, replayable mini-experiences.'}
Seed: {seed}

Per-site backend targets:
{json.dumps([_prompt_target(target) for target in targets], separators=(',', ':'), ensure_ascii=True)}

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
<plan>Four short bullets: subject, controls/state, render stack, payoff.</plan>
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
