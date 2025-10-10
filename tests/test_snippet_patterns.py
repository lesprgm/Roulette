import json
import re


def test_snippet_with_manual_time_tracking_fails_validation():
    """Snippets with manual time tracking should be detectable."""
    bad_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Bad Timer",
        "js": """
        let lastTime = Date.now();
        NDW.loop(() => {
            const now = Date.now();
            const dt = now - lastTime;
            lastTime = now;
        });
        """
    }
    
    js = bad_snippet["js"]
    has_date_now = "Date.now()" in js
    has_performance_now = "performance.now()" in js
    has_manual_dt = re.search(r"lastTime.*=.*Date|lastTime.*=.*performance", js)
    
    assert has_date_now or has_performance_now or has_manual_dt, \
        "Should detect manual time tracking patterns"


def test_snippet_with_correct_dt_usage():
    """Snippets using dt parameter correctly should pass."""
    good_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Good Animation",
        "js": """
        let x = 0;
        const speed = 100;
        NDW.loop((dt) => {
            x += speed * (dt / 1000);
        });
        """
    }
    
    js = good_snippet["js"]
    has_dt_param = re.search(r"NDW\.loop\s*\(\s*\(?.*dt.*\)?.*=>", js) or \
                   re.search(r"NDW\.loop\s*\(\s*function\s*\(\s*dt", js)
    has_dt_conversion = "dt / 1000" in js or "dt/1000" in js
    
    assert has_dt_param, "Should use dt parameter"
    assert has_dt_conversion, "Should convert dt from ms to seconds"


def test_snippet_with_nested_canvas_access():
    """Should detect incorrect canvas.canvas.width pattern."""
    bad_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Bad Canvas",
        "js": """
        const canvasInfo = NDW.makeCanvas({fullScreen:true});
        const canvas = canvasInfo.canvas;
        const ctx = canvasInfo.ctx;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        """
    }
    
    js = bad_snippet["js"]
    # Should detect canvasInfo.canvas pattern (wrong)
    has_nested_access = re.search(r"\.canvas\s*=\s*\w+\.canvas", js) or \
                       "canvasInfo.canvas" in js
    
    assert has_nested_access, "Should detect nested canvas access pattern"


def test_snippet_with_correct_canvas_usage():
    """Correct canvas pattern should be detectable."""
    good_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Good Canvas",
        "js": """
        const canvas = NDW.makeCanvas({fullScreen:true});
        const ctx = canvas.ctx;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        """
    }
    
    js = good_snippet["js"]
    # Should assign makeCanvas result directly
    has_direct_assign = re.search(r"const\s+canvas\s*=\s*NDW\.makeCanvas", js)
    has_ctx_access = "canvas.ctx" in js
    has_direct_dims = "canvas.width" in js and "canvas.canvas.width" not in js
    
    assert has_direct_assign, "Should assign makeCanvas result directly"
    assert has_ctx_access, "Should access .ctx property"
    assert has_direct_dims, "Should access dimensions directly"


def test_snippet_initializes_before_loop():
    """State should be initialized before NDW.loop call."""
    good_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Good Init Order",
        "js": """
        const canvas = NDW.makeCanvas({fullScreen:true});
        const ctx = canvas.ctx;
        let x = 0, y = 0;
        let velocity = {x: 1, y: 1};
        
        NDW.loop((dt) => {
            x += velocity.x * (dt/1000);
            y += velocity.y * (dt/1000);
        });
        """
    }
    
    js = good_snippet["js"]
    loop_match = re.search(r"NDW\.loop", js)
    if loop_match:
        before_loop = js[:loop_match.start()]
        # Should have variable declarations before loop
        has_vars_before = re.search(r"let\s+\w+\s*=|const\s+\w+\s*=|var\s+\w+\s*=", before_loop)
        assert has_vars_before, "Should initialize variables before loop"


def test_snippet_has_clearrect_in_canvas_loop():
    """Canvas animations should clear each frame."""
    good_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Good Canvas Loop",
        "js": """
        const canvas = NDW.makeCanvas({fullScreen:true});
        const ctx = canvas.ctx;
        
        NDW.loop((dt) => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillRect(10, 10, 50, 50);
        });
        """
    }
    
    js = good_snippet["js"]
    has_clear = "clearRect" in js
    has_canvas_dims = re.search(r"clearRect\s*\(\s*0\s*,\s*0\s*,.*canvas\.width.*canvas\.height", js)
    
    assert has_clear, "Canvas loops should call clearRect"
    assert has_canvas_dims, "clearRect should use canvas.width/height"


def test_snippet_uses_arrow_keys_correctly():
    """Keyboard controls should check e.key properly."""
    good_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Good Controls",
        "js": """
        NDW.onKey((e) => {
            if (e.key === 'ArrowUp') jump();
            if (e.key === 'ArrowDown') crouch();
        });
        """
    }
    
    js = good_snippet["js"]
    has_event_param = re.search(r"NDW\.onKey\s*\(\s*\(?.*e.*\)?.*=>", js) or \
                     re.search(r"NDW\.onKey\s*\(\s*function\s*\(\s*e", js)
    has_key_check = "e.key" in js
    has_arrow_keys = "Arrow" in js
    
    assert has_event_param, "onKey should accept event parameter"
    assert has_key_check, "Should check e.key property"
    assert has_arrow_keys, "Should reference arrow keys"


def test_snippet_uses_continuous_input_correctly():
    """Continuous input should use isDown inside loop."""
    good_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Good Continuous Input",
        "js": """
        let x = 0;
        NDW.loop((dt) => {
            if (NDW.isDown('ArrowLeft')) x -= 100 * (dt/1000);
            if (NDW.isDown('ArrowRight')) x += 100 * (dt/1000);
        });
        """
    }
    
    js = good_snippet["js"]
    has_isdown = "NDW.isDown" in js
    loop_match = re.search(r"NDW\.loop\s*\([^)]*\)\s*=>?\s*\{", js)
    if loop_match:
        after_loop = js[loop_match.end():]
        # Find matching closing brace (simplified check)
        has_isdown_in_loop = "NDW.isDown" in after_loop[:after_loop.find("})")]
        assert has_isdown_in_loop, "isDown should be inside loop callback"


def test_snippet_does_not_chain_ndw_calls():
    """Snippets should not access `.NDW` off other expressions."""
    bad_snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Chained NDW",
        "js": """
        const particles = Array(10).fill(0).NDW.onPointer(() => {});
        """
    }

    js = bad_snippet["js"]
    chained = ".NDW" in js
    assert chained, "Detection should spot .NDW chaining pattern"
