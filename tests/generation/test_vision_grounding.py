import base64

from api import llm_client


def _minimal_plan():
    return {
        "layout_archetype": "stage_focus",
        "motion_archetype": "parallax_drift",
        "visual_density": "layered",
        "interaction_model": "pointer_reactive",
        "rendering_mode": "dom",
        "tone": "luminous",
        "palette_key": "solar_pop",
        "layout_key": "stage_focus",
        "motion_preset": "parallax_drift",
        "overlay_key": "noise_grid",
        "display_font_key": "display_orbit",
        "body_font_key": "body_clean",
        "three_scene_key": "glass_orbit",
        "art_direction": "A vivid interactive stage.",
    }


def test_get_design_matrix_b64_loads_file():
    b64 = llm_client._get_design_matrix_b64()
    assert b64 is not None
    assert base64.b64decode(b64).startswith(b"\xff\xd8")


def test_premium_build_includes_design_matrix(monkeypatch):
    captured = {}

    def fake_text(parts, **kwargs):
        captured["parts"] = parts
        return "```html\n<!doctype html><html><body><main id='ndw-content'>ok</main></body></html>\n```"

    monkeypatch.setattr(llm_client, "_get_design_matrix_b64", lambda: "abc123")
    monkeypatch.setattr(llm_client, "_call_gemini_text", fake_text)

    llm_client._call_gemini_premium_build("brief", 1, _minimal_plan())

    assert any("text" in part for part in captured["parts"])
    assert {"inlineData": {"mimeType": "image/jpeg", "data": "abc123"}} in captured["parts"]


def test_premium_build_prompt_references_design_matrix():
    prompt = llm_client._build_premium_page_prompt("brief", 1, _minimal_plan())

    assert "VISION GROUNDING: DESIGN MATRIX ATTACHED" in prompt
    assert "Professional, Playful, Brutalist, Cozy" in prompt
