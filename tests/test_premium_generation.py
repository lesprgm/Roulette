from api import llm_client


def test_fast_prompt_uses_assignment_axes():
    note = llm_client._CATEGORY_ROTATION_NOTES[0][1]
    prompt = llm_client._build_fast_page_prompt("brief", 7, note)
    assert "layout_archetype" in prompt
    assert "motion_archetype" in prompt
    assert "overlay_key" in prompt
    assert "background_token" in prompt
    assert "FAST DESIGN-KIT MANIFEST" in prompt


def test_premium_plan_prompt_references_local_design_kit():
    prompt = llm_client._build_premium_plan_prompt("brief", 7)
    assert "/static/design-kit/overlays/" in prompt
    assert "display_orbit" in prompt
    assert "palette_key" in prompt


def test_generate_page_premium_retries_build_without_rerunning_plan(monkeypatch):
    plan_calls = []
    build_notes = []
    scores = [
        {"score": 62, "threshold": 70, "passes": False, "reasons": ["low"], "flags": {}},
        {"score": 84, "threshold": 70, "passes": True, "reasons": ["good"], "flags": {}},
    ]

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
    docs = iter(
        [
            {"kind": "full_page_html", "html": "<!doctype html><html><body><main class='mx-auto max-w-lg'>Low</main></body></html>"},
            {"kind": "full_page_html", "html": "<!doctype html><html><body><main id='ndw-content' style='background:linear-gradient(#fff,#ddd)'><script>requestAnimationFrame(()=>{});</script><section>High</section></main></body></html>"},
        ]
    )
    monkeypatch.setattr(
        llm_client,
        "_call_gemini_premium_build",
        lambda brief, seed, plan, retry_note="": build_notes.append(retry_note) or next(docs),
    )
    monkeypatch.setattr(llm_client, "_preflight_doc", lambda doc: [])
    monkeypatch.setattr(llm_client, "_preflight_has_blocking_issues", lambda issues: False)
    monkeypatch.setattr(llm_client, "score_page_doc", lambda doc: scores.pop(0))

    out = llm_client.generate_page_premium("brief", 7, user_key="student")
    assert out.get("kind") == "full_page_html"
    assert len(plan_calls) == 1
    assert len(build_notes) == 2
    assert build_notes[0] == ""
    assert build_notes[1] != ""


def test_generate_page_premium_returns_best_doc_when_threshold_not_met(monkeypatch):
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
    assert out.get("kind") == "full_page_html"
    assert out.get("ndw_debug", {}).get("premium_plan")
