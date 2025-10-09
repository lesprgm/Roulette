def test_index_references_compiled_ts_assets():
    """Ensure index.html points to compiled TypeScript outputs and not legacy JS paths."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert "/static/ts-build/app.js" in html
    assert "/static/ts-build/ndw.js" in html
    assert "/static/js/app.js" not in html
    assert "/static/js/ndw.js" not in html