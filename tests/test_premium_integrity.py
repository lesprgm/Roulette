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

def test_compliance_review_handles_premium_flags(monkeypatch):
    # Verify that the compliance review function exists and takes the right args
    # We don't call the real Gemini API here, just verify the logic flow
    doc = {"kind": "full_page_html", "html": "<html><body>TEST</body></html>"}
    brief = "test brief"
    category = "test category"
    
    # Mock _gemini_review_active to False to test skip path
    monkeypatch.setattr(llm_client, "_gemini_review_active", lambda: False)
    review_out, fixed_doc, ok = llm_client._maybe_run_compliance_review(doc, brief, category)
    assert review_out is None
    assert fixed_doc is None
    assert ok is True

def test_normalize_doc_preserves_lucide_markup():
    # Verify the normalization doesn't strip data-lucide (it shouldn't, but good to keep an eye on)
    html = '<div id="ndw-content"><i data-lucide="settings"></i></div>'
    doc = {"kind": "full_page_html", "html": html}
    normalized = llm_client._normalize_doc(doc)
    assert "data-lucide" in normalized["html"]
