import pytest
from api import llm_client

def test_prompt_mandates_lucide_icons():
    # Check if the mandatory prompt hint includes Lucide instructions
    assert "PREMIUM ICONOGRAPHY" in llm_client._PAGE_SHAPE_HINT
    assert "data-lucide" in llm_client._PAGE_SHAPE_HINT
    assert "icon-name" in llm_client._PAGE_SHAPE_HINT

def test_prompt_requires_initial_visual_state():
    assert "INITIAL VISUAL STATE" in llm_client._PAGE_SHAPE_HINT
    assert "ambient motion" in llm_client._PAGE_SHAPE_HINT or "particles" in llm_client._PAGE_SHAPE_HINT

def test_prompt_mandates_gsap_intros():
    assert "PREMIUM INTROS" in llm_client._PAGE_SHAPE_HINT
    assert "GSAP" in llm_client._PAGE_SHAPE_HINT

def test_premium_prompt_requires_experience_contract():
    prompt = llm_client._build_premium_plan_prompt("test brief", 12)
    assert "Experience target:" in prompt
    assert "semantic_translation" in prompt
    assert "primary_loop" in prompt
    assert "onboarding_cue" in prompt
    assert "mobile_interaction" in prompt

def test_prompt_exposes_alpine_and_matter_as_local_profile_libraries():
    hint = llm_client._PAGE_SHAPE_HINT
    prompt = llm_client._build_premium_page_prompt(
        "test brief",
        12,
        {
            "activity_type": "commerce_or_booking_flow",
            "activity_contract": {
                "activity_variant": "travel_booking",
                "library_profile": "alpine_ui_state",
            },
            "task_contract": {
                "state_variables": ["selected_trip"],
                "controls": [{"must_change_state": ["selected_trip"]}],
            },
        },
    )
    assert "/static/vendor/alpine.min.js" in hint
    assert "/static/vendor/matter.min.js" in hint
    assert "Alpine.js" in hint
    assert "Matter.js" in hint
    assert "Alpine UI state profiles" in prompt
    assert "Matter physics profiles" in prompt

def test_premium_style_guidance_contains_anti_ai_slop_rules():
    text = llm_client._build_premium_page_prompt("test brief", 12, {})
    assert "generic AI-generated aesthetics" in text
    assert "purple/blue gradients" in text
    assert "asymmetry, overlap, z-depth" in text
    assert "one high-impact motion moment" in text

def test_normalize_doc_preserves_lucide_markup():
    # Verify the normalization doesn't strip data-lucide (it shouldn't, but good to keep an eye on)
    html = '<div id="ndw-content"><i data-lucide="settings"></i></div>'
    doc = {"kind": "full_page_html", "html": html}
    normalized = llm_client._normalize_doc(doc)
    assert "data-lucide" in normalized["html"]
