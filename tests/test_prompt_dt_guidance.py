"""Test that the prompt properly guides LLMs on dt usage and timing."""
from api.llm_client import _PAGE_SHAPE_HINT


def test_prompt_mentions_dt_parameter():
    """Ensure prompt explicitly mentions dt as a parameter to NDW.loop."""
    text = _PAGE_SHAPE_HINT
    assert "NDW.loop((dt)" in text or "NDW.loop( (dt)" in text, \
        "Prompt must show dt as parameter to NDW.loop"


def test_prompt_warns_against_manual_time_tracking():
    """Ensure prompt explicitly forbids manual time tracking."""
    text = _PAGE_SHAPE_HINT.lower()
    # Should mention NOT to use Date.now, performance.now, or manual tracking
    assert "no manual time" in text or "do not manually track" in text or \
           "never use date.now" in text, \
        "Prompt must warn against manual time tracking"


def test_prompt_clarifies_dt_units():
    """Ensure prompt clarifies that dt is in milliseconds."""
    text = _PAGE_SHAPE_HINT.lower()
    assert "millisecond" in text, "Prompt must clarify dt is in milliseconds"
    assert "dt/1000" in text or "(dt / 1000)" in text, \
        "Prompt must show conversion from ms to seconds"


def test_prompt_shows_physics_with_dt():
    """Ensure prompt shows correct physics integration with dt."""
    text = _PAGE_SHAPE_HINT
    assert "dt/1000" in text or "dt / 1000" in text, \
        "Prompt must show dt/1000 conversion for physics"
    assert ("velocity" in text.lower() or "position" in text.lower()), \
        "Prompt must show physics examples"


def test_prompt_shows_initialization_order():
    """Ensure prompt emphasizes initializing state before loop."""
    text = _PAGE_SHAPE_HINT.lower()
    assert "before ndw.loop" in text or "initialize" in text, \
        "Prompt must emphasize initialization before loop"


def test_prompt_has_canvas_usage_example():
    """Ensure prompt shows correct canvas creation pattern."""
    text = _PAGE_SHAPE_HINT
    assert "NDW.makeCanvas" in text, \
        "Prompt must show correct canvas assignment pattern"
    assert ".ctx" in text, "Prompt must show accessing .ctx property"

# ... (omitted tests) ...

def test_prompt_mentions_rng_usage():
    """Ensure prompt demonstrates correct RNG usage."""
    text = _PAGE_SHAPE_HINT
    assert "NDW.utils.rng" in text, "Prompt must mention NDW.utils.rng"


def test_prompt_notes_event_registration_order():
    """Ensure prompt directs registering handlers before NDW.loop."""
    lower = _PAGE_SHAPE_HINT.lower()
    assert "register" in lower or "initialize" in lower, \
        "Prompt must say to register handlers before NDW.loop"


def test_prompt_includes_canonical_template():
    """Ensure prompt includes canonical code template block."""
    text = _PAGE_SHAPE_HINT
    assert "CANONICAL CANVAS TEMPLATE" in text, \
        "Prompt must include canonical canvas template heading"
    assert "NDW.loop((dt) =>" in text, \
        "Canonical template must demonstrate NDW.loop"


def test_prompt_warns_against_chaining_ndw_calls():
    """Ensure prompt forbids chaining NDW.* onto other expressions."""
    lower = _PAGE_SHAPE_HINT.lower()
    assert "never chain" in lower and "ndw" in lower, \
        "Prompt must warn against chaining NDW calls"


def test_prompt_encourages_variety():
    """Ensure prompt nudges the model to rotate categories."""
    lower = _PAGE_SHAPE_HINT.lower()
    # Updated to match new category notes structure
    assert "category assignment" in lower, \
        "Prompt must mention category assignment"


def test_prompt_requires_user_instructions():
    """Ensure prompt demands instructions/context outside the canvas."""
    lower = _PAGE_SHAPE_HINT.lower()
    assert "instructions" in lower, \
        "Prompt must mention providing instructions"


def test_prompt_pushes_rich_layouts_for_websites():
    """Ensure prompt asks for multi-section HTML for websites."""
    lower = _PAGE_SHAPE_HINT.lower()
    assert "rich aesthetic" in lower or "premium" in lower, \
        "Prompt must mention rich or premium aesthetics"
    assert "format" in lower or "structure" in lower, \
        "Prompt must discuss format/structure"

