"""Test NDW runtime validation and error handling."""
import re


def test_ndw_runtime_has_loop_validation():
    """Ensure NDW.loop validates its callback parameter."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    # Should check if fn is a function
    assert re.search(r"typeof.*fn.*!==.*['\"]function['\"]", content) or \
           re.search(r"typeof.*fn.*===.*['\"]function['\"]", content), \
        "NDW.loop should validate callback is a function"


def test_ndw_runtime_warns_about_dt_parameter():
    """Ensure NDW.loop warns when callback doesn't accept dt parameter."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    # Should check fn.length (number of parameters)
    assert "fn.length" in content, \
        "NDW.loop should check callback parameter count"
    assert "warn" in content.lower() and "dt" in content, \
        "NDW.loop should warn about missing dt parameter"


def test_ndw_runtime_has_error_overlay_integration():
    """Ensure NDW._frame catches errors and shows overlay."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    # Should have try/catch in _frame
    assert re.search(r"_frame.*\{.*try.*catch", content, re.DOTALL), \
        "NDW._frame should have try/catch"
    
    # Should call error overlay if available
    assert "__NDW_showSnippetErrorOverlay" in content, \
        "NDW._frame should integrate with error overlay"


def test_ndw_makecanvas_has_compatibility_aliases():
    """Ensure NDW.makeCanvas provides backward-compat aliases."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    # Should alias .element
    assert ".element = c" in content or "element: c" in content, \
        "NDW.makeCanvas should alias .element"
    
    # Should alias .canvas
    assert ".canvas = c" in content or "canvas: c" in content, \
        "NDW.makeCanvas should alias .canvas for backward compatibility"


def test_ndw_makecanvas_sets_ctx_and_dpr():
    """Ensure NDW.makeCanvas sets .ctx and .dpr properties."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    assert "c.ctx = ctx" in content or "ctx:" in content, \
        "NDW.makeCanvas should set .ctx property"
    assert "c.dpr = dpr" in content or "dpr:" in content, \
        "NDW.makeCanvas should set .dpr property"


def test_ndw_frame_passes_dt_to_callback():
    """Ensure NDW._frame calculates and passes dt to callback."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    # Should calculate dt from now - last
    assert re.search(r"dt\s*=.*now.*-.*last", content, re.IGNORECASE) or \
           re.search(r"const\s+dt.*=.*\(.*now.*-", content), \
        "NDW._frame should calculate dt"
    
    # Should pass dt to tick callback
    assert re.search(r"_tick.*\(.*dt.*\)", content), \
        "NDW._frame should pass dt to callback"


def test_ndw_has_keyboard_tracking():
    """Ensure NDW tracks keyboard state for isDown."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    assert "_keys" in content, "NDW should maintain _keys set"
    assert "keydown" in content.lower(), "NDW should listen to keydown"
    assert "keyup" in content.lower(), "NDW should listen to keyup"
    # isDown is defined inline, check for the method pattern
    assert re.search(r"isDown\s*\(.*key", content, re.IGNORECASE), \
        "NDW should provide isDown(key) method"


def test_ndw_has_pointer_tracking():
    """Ensure NDW tracks pointer/mouse state."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    assert "pointer" in content.lower(), "NDW should track pointer"
    assert "pointerdown" in content or "mousedown" in content, \
        "NDW should listen to pointer events"
    # Should mirror pointer state into 'mouse' key
    assert "'mouse'" in content or '"mouse"' in content, \
        "NDW should mirror pointer state to 'mouse' key"


def test_ndw_has_resize_handling():
    """Ensure NDW provides resize handling."""
    with open('static/ts-src/ndw.ts', 'r') as f:
        content = f.read()
    
    assert "onResize" in content, "NDW should provide onResize"
    assert "_resizeHandlers" in content or "resize" in content.lower(), \
        "NDW should maintain resize handlers"
