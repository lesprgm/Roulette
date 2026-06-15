from api import llm_client
from api.generation.experience_grammar import (
    FORMAT_VARIANT_SPECS,
    PRODUCT_FORMATS,
    _activity_contract_for_variant,
    activity_family_for_variant,
    seeded_diverse_format_first_targets,
)
from api.generation.semantic_anchors import ANCHOR_BUCKETS


def test_premium_experience_target_includes_activity_and_genre_contracts():
    target = llm_client._premium_experience_target(7)
    assert target["format_first"] is True
    assert target["format_contract"]["activity_variant"] == target["activity_contract"]["activity_variant"]
    assert target["activity_type"]
    assert target["activity_contract"]["activity_type"] == target["activity_type"]
    assert target["activity_contract"]["activity_variant"]
    assert target["activity_contract"]["core_mechanic"]
    assert target["activity_contract"]["library_profile"]
    assert target["task_contract"]["format"]
    assert target["task_contract"]["domain_objects"]
    assert target["task_contract"]["state_variables"]
    assert target["task_contract"]["controls"]
    assert target["task_contract"]["completion_condition"]
    assert target["genre_contract"]["page_genre"]
    assert target["genre_contract"]["copy_density"]
    assert target["genre_contract"]["entry_rule"]
    assert target["genre_contract"]["retention_rule"]
    assert target["genre_contract"]["jargon_policy"]
    assert target["activity_contract"]["retention_contract"]
    assert target["task_contract"]["retention_contract"]
    assert target["visitor_role"]
    assert target["visitor_goal"]
    assert target["first_interaction"]
    assert target["onboarding_cue"]
    assert target["primary_loop"]["user_action"]
    assert target["primary_loop"]["visible_response"]
    assert target["primary_loop"]["state_change"]
    assert target["primary_loop"]["reward_or_payoff"]
    assert target["primary_loop"]["continue_reason"]
    assert target["semantic_translation"]


def test_premium_experience_target_derives_cell_from_concrete_format():
    for seed in range(1, 80):
        target = llm_client._premium_experience_target(seed)
        variant = target["activity_contract"]["activity_variant"]
        spec = FORMAT_VARIANT_SPECS[variant]
        assert target["experience_archetype"] == spec["experience_archetype"]
        assert target["primary_loop_type"] == spec["primary_loop_type"]
        assert target["activity_contract"]["core_mechanic"] == spec["core_mechanic"]


def test_semantic_anchor_pool_removes_abstract_repeat_offenders():
    system_metaphors = set(ANCHOR_BUCKETS["system_metaphor"])
    assert "skill ladder" not in system_metaphors
    assert "migration counter" not in system_metaphors
    assert "signal relay" not in system_metaphors
    assert "memory palace" not in system_metaphors
    assert "dream logistics" not in system_metaphors
    assert "market of rumors" not in system_metaphors


def test_premium_experience_target_can_choose_broad_game_variants():
    seen = {
        llm_client._premium_experience_target(seed)["activity_contract"]["activity_variant"]
        for seed in range(1, 180)
    }
    assert {"breakout_paddle", "minesweeper_grid", "tile_merge_2048", "rhythm_tap", "snake_grid"} & seen
    assert len(seen) >= 25


def test_premium_experience_target_biases_toward_retention_formats():
    targets = [llm_client._premium_experience_target(seed) for seed in range(1, 121)]
    game_count = sum(1 for target in targets if target["activity_contract"]["activity_variant"] in {
        "platformer_collectathon",
        "snake_grid",
        "tic_tac_toe",
        "trivia_quiz",
        "memory_match",
        "word_guess",
        "breakout_paddle",
        "minesweeper_grid",
        "tile_merge_2048",
        "endless_runner",
        "rhythm_tap",
        "whack_a_target",
        "sliding_tile_puzzle",
        "tower_defense_lite",
        "pinball_table",
        "asteroids_shooter",
        "maze_escape",
        "reaction_timer",
        "fishing_timing",
        "basketball_arcade",
        "card_sort_strategy",
        "typing_race",
    })
    heavy_workflow_count = sum(1 for target in targets if target["activity_contract"]["activity_variant"] in {
        "kanban_workspace",
        "crm_pipeline",
        "invoice_builder",
        "analytics_explorer",
        "inventory_manager",
        "resume_screener",
        "support_triage",
    })
    assert game_count > heavy_workflow_count


def test_diverse_burst_targets_do_not_repeat_format_families():
    targets = seeded_diverse_format_first_targets(614300, 8)
    families = [activity_family_for_variant(target["activity_contract"]["activity_variant"]) for target in targets]
    variants = [target["activity_contract"]["activity_variant"] for target in targets]
    assert len(variants) == len(set(variants))
    assert len(families) == len(set(families))


def test_diverse_burst_targets_include_product_storefronts_across_seeds():
    seen = {
        target["activity_contract"]["activity_variant"]
        for seed in range(1, 40)
        for target in seeded_diverse_format_first_targets(seed, 5)
    }
    assert set(PRODUCT_FORMATS) & seen


def test_product_storefront_task_contract_uses_product_retention_contract():
    target = next(
        llm_client._premium_experience_target(seed)
        for seed in range(1, 300)
        if llm_client._premium_experience_target(seed)["activity_type"] == "product_or_storefront"
    )
    assert target["task_contract"]["retention_contract"]["entry"].startswith("Show product hero")
    assert "cart" in " ".join(target["task_contract"]["domain_objects"])


def test_library_profiles_are_deterministic_for_new_runtime_primitives():
    for variant in ["breakout_paddle", "whack_a_target", "pinball_table", "fishing_timing", "basketball_arcade"]:
        assert _activity_contract_for_variant(7, variant)["library_profile"] == "matter_physics_game"

    for variant in ["invoice_builder", "travel_booking", "product_detail_page", "marketplace_listing_page"]:
        assert _activity_contract_for_variant(7, variant)["library_profile"] == "alpine_ui_state"


def test_visual_playground_uses_game_variants_not_app_fallbacks():
    seen = {
        llm_client.seeded_activity_contract(seed, "visual_playground", "press_sequence_to_unlock")["activity_variant"]
        for seed in range(1, 80)
    }
    assert {"breakout_paddle", "minesweeper_grid", "tile_merge_2048", "rhythm_tap", "snake_grid"} & seen
    assert "kanban_workspace" not in seen
    assert "weather_mixer" not in seen


def test_extract_gemini_text_preserves_structured_fallback_with_blank_text():
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": ""},
                        {"functionCall": {"name": "emit", "arguments": "{\"ok\":true}"}},
                    ]
                }
            }
        ]
    }
    assert llm_client._extract_gemini_text(payload) == "{\"ok\":true}"


def test_premium_plan_prompt_uses_novelty_and_prompt_genome():
    prompt = llm_client._build_premium_plan_prompt("brief", 7)
    assert "Novelty summary from recently served pages" in prompt
    assert "prompt_genome" in prompt
    assert "fingerprint" in prompt
    assert "creative_libraries" in prompt
    assert "genre_contract" in prompt
    assert "activity_contract" in prompt
    assert "activity_type" in prompt
    assert "activity_contract.activity_variant" in prompt
    assert "activity_contract.library_profile" in prompt
    assert "task_contract" in prompt
    assert "domain objects" in prompt
    assert "completion_condition" in prompt
    assert "Resolve the concrete activity format first" in prompt
    assert "semantic anchors as Tier 2 flavor" in prompt
    assert "must not rename, obscure, or override" in prompt
    assert "arcade games" in prompt
    assert "workspace apps" in prompt
    assert "Copy density" in prompt
    assert "instruction policy" in prompt
    assert "one obvious action" in prompt
    assert "sample records/items/options" in prompt
    assert "meta-reward" in prompt
    assert "calibration, protocol, terminal" in prompt
    assert "product pages" in prompt
    assert "ecommerce storefronts" in prompt
    assert "hero product/offer" in prompt


def test_premium_plan_prompt_references_local_design_kit():
    prompt = llm_client._build_premium_plan_prompt("brief", 7)
    assert "/static/design-kit/overlays/" in prompt
    assert "display_orbit" in prompt
    assert "palette_key" in prompt


def test_premium_build_prompt_uses_self_review_and_raw_html():
    prompt = llm_client._build_premium_page_prompt(
        "brief",
        7,
        {"layout_archetype": "stage_focus", "palette_key": "solar_pop"},
    )
    assert "/static/design-kit/fonts.css" in prompt
    assert "/static/design-kit/overlays/" in prompt
    assert "<self_review>" in prompt
    assert "```html" in prompt
    assert "Do not output JSON" in prompt
    assert "import * as THREE from '/static/vendor/three.module.js';" in prompt
    assert "Forbidden APIs used? no" in prompt
    assert "fetch, XMLHttpRequest, WebSocket, Worker" in prompt
    assert "/static/vendor/gsap.min.js" in prompt
    assert "do not invent plugin paths such as ScrollTrigger or Draggable" in prompt
    assert "/static/vendor/three-addons/controls/OrbitControls.js" in prompt
    assert "Final HTML must be at least" in prompt
    assert "Follow genre_contract.copy_density" in prompt
    assert "activity_type and activity_contract are mandatory" in prompt
    assert "activity_variant" in prompt
    assert "activity_contract.activity_variant is the product" in prompt
    assert "must never rename, obscure, or replace" in prompt
    assert "task_contract is mandatory" in prompt
    assert "must visibly change at least one listed must_change_state" in prompt
    assert "library_profile" in prompt
    assert "breakout_paddle" in prompt
    assert "slider-only page" in prompt
    assert "Ban visible artifacts" in prompt
    assert "Do not create a section titled" in prompt
    assert "No blank tables, empty slots" in prompt
    assert "high-contrast first frame" in prompt
    assert "Avoid recurring wave/grid wallpaper" in prompt
    assert "do not ship a splash-only start" in prompt
    assert "Static first content rule" in prompt
    assert "Puzzle/game cue rule" in prompt
    assert "score plus one meta-reward" in prompt
    assert "starter preview/artifact" in prompt
    assert "Avoid visible jargon" in prompt
    assert "Roulette, NDW, No Delay Wireless" in prompt
    assert "product_or_storefront" in prompt
    assert "product/ecommerce website" in prompt
    assert "checkout/cart/receipt feedback" in prompt
    assert "/static/vendor/alpine.min.js" in prompt
    assert "/static/vendor/matter.min.js" in prompt
    assert "No inline onclick/oninput/onchange handlers" in prompt


def test_premium_burst_prompt_uses_site_markers_and_targets():
    prompt = llm_client._build_premium_burst_prompt(
        "brief",
        7,
        [
            {
                "site_index": 1,
                "experience_archetype": "museum_exhibit",
                "primary_loop_type": "scan_to_compare",
                "semantic_anchors": {"material": "glass"},
            },
            {
                "site_index": 2,
                "experience_archetype": "interactive_instrument",
                "primary_loop_type": "tune_to_harmonize",
                "semantic_anchors": {"material": "paper"},
            },
        ],
    )
    assert "===NDW_SITE_1_START===" in prompt
    assert "===NDW_SITE_1_END===" in prompt
    assert "<self_review>" in prompt
    assert "Do not output JSON" in prompt
    assert "Each site must feel unrelated" in prompt
    assert "Forbidden APIs used? no" in prompt
    assert "Remote resources used? no" in prompt
    assert "/static/vendor/gsap.min.js" in prompt
    assert "/static/vendor/ScrollTrigger.min.js" not in prompt
    assert "do not invent plugin paths such as ScrollTrigger or Draggable" in prompt
    assert "generic centered-card shell" in prompt
    assert "Respect each site's genre_contract" in prompt
    assert "Build the activity_contract" in prompt
    assert "saas_replica" in prompt
    assert "activity_contract.activity_variant" in prompt
    assert "Breakout" in prompt
    assert "Avoid slider-only sites" in prompt
    assert "Ban visible artifacts" in prompt
    assert "within three seconds" in prompt
    assert "preload realistic sample data" in prompt
    assert "meta-reward" in prompt
    assert "product hero" in prompt
    assert "Canvas/game first paint rule" in prompt
    assert "wave/grid/contour/dot wallpaper" in prompt
    assert "Non-empty first screen rule" in prompt
    assert "Simple game visibility rule" in prompt
    assert "Static first content rule" in prompt
    assert "Puzzle/game cue rule" in prompt
    assert "Roulette, NDW, No Delay Wireless" in prompt


def test_premium_plan_locks_backend_contract_after_model_output(monkeypatch):
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "_get_design_matrix_b64", lambda: None)
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_structured",
        lambda *args, **kwargs: {
            "experience_archetype": "fictional_control_room",
            "primary_loop_type": "press_sequence_to_unlock",
            "semantic_anchors": {"material": "wrong"},
            "activity_type": "fake_os_app",
            "activity_contract": {"activity_variant": "operating_panel"},
            "task_contract": {"format": "operating_panel"},
            "genre_contract": {"page_genre": "fictional_control_room"},
            "layout_archetype": "stage_focus",
            "motion_archetype": "parallax_drift",
            "visual_density": "layered",
            "interaction_model": "pointer_reactive",
            "rendering_mode": "dom",
            "tone": "luminous",
            "signature_interaction": "test",
            "hero_treatment": "test",
            "palette_key": "solar_pop",
            "layout_key": "stage_focus",
            "motion_preset": "parallax_drift",
            "overlay_key": "noise_grid",
            "display_font_key": "display_orbit",
            "body_font_key": "body_clean",
            "three_scene_key": "glass_orbit",
            "art_direction": "test",
        },
    )
    expected = llm_client._premium_experience_target(7)

    plan = llm_client._call_gemini_premium_plan("brief", 7)

    assert plan["experience_archetype"] == expected["experience_archetype"]
    assert plan["primary_loop_type"] == expected["primary_loop_type"]
    assert plan["semantic_anchors"] == expected["semantic_anchors"]
    assert plan["activity_type"] == expected["activity_type"]
    assert plan["activity_contract"] == expected["activity_contract"]
    assert plan["task_contract"] == expected["task_contract"]
    assert plan["genre_contract"] == expected["genre_contract"]


def test_extract_completed_premium_burst_sites():
    text = """
    ===NDW_SITE_1_START===
    <thinking>Plan</thinking>
    ```html
    <!doctype html><html><body><main>One</main></body></html>
    ```
    ===NDW_SITE_1_END===
    ===NDW_SITE_2_START===
    <self_review>ok</self_review>
    ````html
    <!doctype html><html><body><main>Two</main></body></html>
    ````
    ===NDW_SITE_2_END===
    """
    sites = llm_client.extract_completed_premium_burst_sites(text)
    assert len(sites) == 2
    assert sites[0][0] == 1
    assert "One" in sites[0][1]
    assert sites[1][0] == 2
    assert "Two" in sites[1][1]


def test_premium_burst_rejects_tiny_shells_as_hard_guard(monkeypatch):
    monkeypatch.setattr(llm_client, "PREMIUM_BURST_MIN_HTML_BYTES", 3000)
    tiny_doc = {"kind": "full_page_html", "html": "<!doctype html><html><body><main>Tiny</main></body></html>"}

    assert "html too small" in llm_client._premium_burst_rejection(
        tiny_doc,
        {"score": 1, "threshold": 70, "passes": False},
    )


def test_premium_burst_does_not_reject_low_advisory_scores(monkeypatch):
    monkeypatch.setattr(llm_client, "PREMIUM_BURST_MIN_HTML_BYTES", 3000)
    good_sized_doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main>" + ("Layered experience " * 220) + "</main></body></html>",
    }

    assert llm_client._premium_burst_rejection(
        good_sized_doc,
        {"score": 66, "threshold": 70, "passes": False},
    ) is None
    assert llm_client._premium_burst_rejection(
        good_sized_doc,
        {"score": 84, "threshold": 70, "passes": True},
    ) is None


def test_premium_burst_attaches_repair_signals_without_rejecting(monkeypatch):
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main id='ndw-content'><h1>Snake Grid</h1><canvas></canvas><button>Restart</button></main></body></html>",
    }
    scored = llm_client._attach_quality_score(doc, "premium_burst")
    target = llm_client._premium_experience_target(42)
    monkeypatch.setattr(llm_client, "score_page_doc", lambda doc: {"score": 90, "threshold": 70, "passes": True})
    monkeypatch.setattr(llm_client, "score_design_discipline", lambda doc, plan: {"score": 30, "threshold": 75, "passes": False, "tags": ["copy_over_budget"]})
    monkeypatch.setattr(llm_client, "score_activity_depth", lambda doc, plan: {"score": 40, "threshold": 75, "passes": False, "tags": ["activity_variant_mismatch"]})

    scored = llm_client._attach_quality_score(doc, "premium_burst")
    scored = llm_client._attach_premium_evaluations(scored, target)
    assert scored["ndw_debug"]["experience_quality"].get("skipped") is not True
    assert "activity_variant_mismatch" in scored["ndw_debug"]["repair_signals"]
    assert "copy_over_budget" in scored["ndw_debug"]["repair_signals"]


def test_generate_page_premium_uses_one_build_call(monkeypatch):
    plan_calls = []
    build_notes = []

    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "_testing_stub_enabled", lambda: False)
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_premium_plan",
        lambda brief, seed, user_key=None: plan_calls.append((brief, seed, user_key)) or {
            "layout_archetype": "stage_focus",
            "motion_archetype": "parallax_drift",
            "visual_density": "layered",
            "interaction_model": "pointer_reactive",
            "rendering_mode": "dom",
            "tone": "luminous",
            "signature_interaction": "Tilt a layered stage with the pointer.",
            "hero_treatment": "Oversized luminous headline with a kinetic dial.",
            "palette_key": "solar_pop",
            "layout_key": "stage_focus",
            "motion_preset": "parallax_drift",
            "overlay_key": "noise_grid",
            "display_font_key": "display_orbit",
            "body_font_key": "body_clean",
            "three_scene_key": "glass_orbit",
            "art_direction": "Luminous editorial control room with layered parallax glass.",
        },
    )
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_premium_build",
        lambda brief, seed, plan, retry_note="": build_notes.append(retry_note) or {"kind": "full_page_html", "html": "<!doctype html><html><body><main id='ndw-content'>One shot</main></body></html>"},
    )
    monkeypatch.setattr(llm_client, "_preflight_doc", lambda doc: [])
    monkeypatch.setattr(llm_client, "_preflight_has_blocking_issues", lambda issues: False)
    monkeypatch.setattr(llm_client, "score_page_doc", lambda doc: {"score": 84, "threshold": 70, "passes": True, "reasons": ["good"], "flags": {}})
    monkeypatch.setattr(llm_client, "score_experience", lambda doc, plan: {"score": 90, "threshold": 75, "passes": True})
    monkeypatch.setattr(llm_client, "score_design_discipline", lambda doc, plan: {"score": 90, "threshold": 75, "passes": True, "tags": []})
    monkeypatch.setattr(llm_client, "score_activity_depth", lambda doc, plan: {"score": 90, "threshold": 75, "passes": True, "tags": []})

    out = llm_client.generate_page_premium("brief", 7, user_key="student")
    assert out.get("kind") == "full_page_html"
    assert len(plan_calls) == 1
    assert len(build_notes) == 1
    assert build_notes[0] == ""


def test_generate_page_premium_returns_error_when_preflight_blocks(monkeypatch):
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "_testing_stub_enabled", lambda: False)
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_premium_plan",
        lambda brief, seed, user_key=None: {
            "layout_archetype": "split_lens",
            "motion_archetype": "scroll_shutter",
            "visual_density": "dense",
            "interaction_model": "scroll_story",
            "rendering_mode": "hybrid",
            "tone": "cinematic",
            "signature_interaction": "Slide a control rail to alter scene depth.",
            "hero_treatment": "Poster-like split scene with a dramatic horizon.",
            "palette_key": "midnight_luxe",
            "layout_key": "split_lens",
            "motion_preset": "scroll_shutter",
            "overlay_key": "diagonal_hatch",
            "display_font_key": "display_editorial",
            "body_font_key": "body_soft",
            "three_scene_key": "terrain_glow",
            "art_direction": "Cinematic split-screen observatory with a glowing horizon.",
        },
    )
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_premium_build",
        lambda brief, seed, plan, retry_note="": {"kind": "full_page_html", "html": "<!doctype html><html><body><main id='ndw-content'>Best effort</main></body></html>"},
    )
    monkeypatch.setattr(llm_client, "_preflight_doc", lambda doc: [{"severity": "block", "message": "bad selector"}])
    monkeypatch.setattr(llm_client, "_preflight_has_blocking_issues", lambda issues: True)
    monkeypatch.setattr(
        llm_client,
        "score_page_doc",
        lambda doc: {"score": 55, "threshold": 70, "passes": False, "reasons": ["best available"], "flags": {}},
    )

    out = llm_client.generate_page_premium("brief", 4)
    assert out.get("error") == "Premium build failed local preflight"
    assert out.get("issues")
