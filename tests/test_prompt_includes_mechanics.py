from api.llm_client import _PAGE_SHAPE_HINT


def test_hint_includes_ndw_hash_and_mouse_and_physics():
    text = _PAGE_SHAPE_HINT
    assert "NDW.utils" in text
    assert "hash(" in text or "hash(seed)" in text
    assert "mouse" in text 
    assert "velocity" in text and "acceleration" in text
    assert "playTone" in text
