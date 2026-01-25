def test_index_references_compiled_ts_assets():
    """Ensure index.html points to compiled TypeScript outputs and not legacy JS paths."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert "/js/app.js" in html
    assert "/js/ndw.js" in html
    assert "/static/ts-build/app.js" not in html
    assert "/static/ts-build/ndw.js" not in html


def test_index_includes_tunnel_scaffold():
    """Ensure landing template includes the tunnel container and Three.js import map."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="tunnel-container"' in html
    assert "landing-mode" in html
    assert "min-height: 10000vh" not in html
    assert 'type="importmap"' in html
    assert "three@0.160.0" in html
    assert "es-module-shims" in html
