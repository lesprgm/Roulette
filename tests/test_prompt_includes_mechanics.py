from api.llm_client import _PAGE_SHAPE_HINT


def test_hint_includes_ndw_hash_and_mouse_and_physics():
    text = _PAGE_SHAPE_HINT
    assert "NDW.utils" in text
    assert "hash(" in text or "hash(seed)" in text
    assert "mouse" in text
    # Check for physics terms (may be abbreviated as v, a, p)
    assert ("velocity" in text.lower() or " v " in text or "vel" in text.lower()), \
        "Prompt should mention velocity or use v for velocity"
    assert ("acceleration" in text.lower() or " a " in text or "accel" in text.lower()), \
        "Prompt should mention acceleration or use a for acceleration"
    assert "playTone" not in text