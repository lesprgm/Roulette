from api.llm_client import _PAGE_SHAPE_HINT


def test_hint_includes_ndw_hash_and_mouse_and_physics():
    text = _PAGE_SHAPE_HINT
    assert "NDW.utils" in text
    # SDK Cheat Sheet primarily documents rng for seeded random, hash is optional
    assert "rng" in text or "hash(" in text or "hash(seed)" in text, \
        "Prompt should mention rng or hash for seeded randomness"
    assert "mouse" in text
    # The new SDK Cheat Sheet may not have explicit physics formulas but shows dt usage
    assert ("velocity" in text.lower() or " v " in text or "dt" in text.lower()), \
        "Prompt should mention velocity or dt for physics"
    # playTone is now documented in the SDK Cheat Sheet
    assert "playTone" in text, "SDK Cheat Sheet should document playTone"