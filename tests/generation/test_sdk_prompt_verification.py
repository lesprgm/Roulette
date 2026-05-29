"""Verification of the NDW SDK Cheat Sheet in the LLM prompts."""
import pytest
from api.llm_client import _PAGE_SHAPE_HINT


def test_prompt_includes_sdk_cheat_sheet():
    text = _PAGE_SHAPE_HINT
    assert "NDW SDK CHEAT SHEET" in text
    
    # Verify core methods are documented
    methods = [
        "NDW.loop",
        "NDW.isPressed",
        "NDW.isDown",
        "NDW.audio.playTone",
        "NDW.juice.shake",
        "NDW.particles.spawn",
        "NDW.makeCanvas",
        "NDW.utils.dist",
        "NDW.utils.store.get",
        "NDW.utils.store.set"
    ]
    for m in methods:
        assert m in text, f"Prompt should document {m}"


def test_prompt_includes_semantic_aliases():
    text = _PAGE_SHAPE_HINT
    aliases = [
        "NDW.jump()",
        "NDW.shot()",
        "NDW.action()"
    ]
    for a in aliases:
        assert a in text, f"Prompt should document semantic alias {a}"


def test_prompt_includes_handy_loop_parameter():
    text = _PAGE_SHAPE_HINT
    # Should show (dt) parameter
    assert "NDW.loop((dt) =>" in text or "NDW.loop(dt =>" in text


def test_prompt_includes_canvas_parent_guidance():
    text = _PAGE_SHAPE_HINT
    # Should mention document.getElementById('ndw-content')
    assert "ndw-content" in text


def test_prompt_includes_do_not_rules():
    text = _PAGE_SHAPE_HINT
    assert "DO NOT:" in text
    assert "Do not reference external fonts, CDNs, or fetch remote data" in text
    assert "iframes" in text.lower()
    assert "external asset" in text.lower() or "external fonts" in text.lower()


def test_prompt_includes_premium_design_guidelines():
    text = _PAGE_SHAPE_HINT
    # Check for keywords that push the LLM towards higher quality
    keywords = ["design quality", "modern", "harmonious", "contrast", "premium"]
    for k in keywords:
        assert k in text.lower(), f"Prompt should encourage {k}"


def test_prompt_mentions_self_qa():
    text = _PAGE_SHAPE_HINT
    assert "SELF QA" in text
    assert "Pretend to click every button" in text
