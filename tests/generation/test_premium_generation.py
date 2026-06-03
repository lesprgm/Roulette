from api import llm_client


def test_premium_plan_prompt_uses_novelty_and_prompt_genome():
    prompt = llm_client._build_premium_plan_prompt("brief", 7)
    assert "Novelty summary from recently served pages" in prompt
    assert "prompt_genome" in prompt
    assert "fingerprint" in prompt
    assert "creative_libraries" in prompt


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
    assert "do not invent plugin paths such as Draggable" in prompt
    assert "/static/vendor/three-addons/controls/OrbitControls.js" in prompt
    assert "Final HTML must be at least" in prompt


def test_premium_burst_prompt_uses_site_markers_and_targets():
    prompt = llm_client._build_premium_burst_prompt(
        "brief",
        7,
        [
            {
                "site_index": 1,
                "experience_archetype": "museum_exhibit",
                "primary_loop_type": "scan_to_discover",
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
    assert "/static/vendor/ScrollTrigger.min.js" in prompt
    assert "do not invent plugin paths such as Draggable" in prompt
    assert "generic centered-card shell" in prompt


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


def test_premium_burst_rejects_tiny_or_low_quality(monkeypatch):
    monkeypatch.setattr(llm_client, "PREMIUM_BURST_MIN_HTML_BYTES", 3000)
    tiny_doc = {"kind": "full_page_html", "html": "<!doctype html><html><body><main>Tiny</main></body></html>"}
    good_sized_doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main>" + ("Layered experience " * 220) + "</main></body></html>",
    }

    assert "html too small" in llm_client._premium_burst_rejection(
        tiny_doc,
        {"score": 100, "threshold": 70, "passes": True},
    )
    assert "quality score below threshold" in llm_client._premium_burst_rejection(
        good_sized_doc,
        {"score": 66, "threshold": 70, "passes": False},
    )
    assert llm_client._premium_burst_rejection(
        good_sized_doc,
        {"score": 84, "threshold": 70, "passes": True},
    ) is None


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
            "overlay_key": "mesh_wave",
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
