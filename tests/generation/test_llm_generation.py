from api import llm_client


def test_generate_page_delegates_to_premium(monkeypatch):
    doc = {"kind": "full_page_html", "html": "<!doctype html><html><body><main id='ndw-content'>Premium</main></body></html>"}
    calls = []

    def fake_premium(brief, seed, user_key=None):
        calls.append((brief, seed, user_key))
        return doc

    monkeypatch.setattr(llm_client, "generate_page_premium", fake_premium)

    assert llm_client.generate_page("random", 123, user_key="user-1") is doc
    assert calls == [("random", 123, "user-1")]


def test_generate_page_returns_premium_error_without_fallback(monkeypatch):
    monkeypatch.setattr(llm_client, "generate_page_premium", lambda *args, **kwargs: {"error": "Premium planner failed"})

    assert llm_client.generate_page("random", 123) == {"error": "Premium planner failed"}


def test_status_reports_gemini_only(monkeypatch):
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(llm_client, "GEMINI_GENERATION_MODEL", "gemini-test")
    monkeypatch.setattr(llm_client, "GEMINI_FALLBACK_MODEL", "gemini-fallback")

    status = llm_client.status()

    assert status["provider"] == "gemini"
    assert status["using"] == "gemini-premium"
    assert status["primary"] == "gemini-test"
    assert status["fallback"] == "gemini-fallback"
    assert not any(key.endswith("fallbacks") for key in status)


def test_extract_final_html_blocks_prefers_fenced_html():
    text = """
    <thinking>plan</thinking>
    ```html
    <!doctype html><html><body><main id="ndw-content">Final</main></body></html>
    ```
    """

    assert llm_client.extract_final_html_blocks(text) == [
        '<!doctype html><html><body><main id="ndw-content">Final</main></body></html>'
    ]


def test_extract_final_html_blocks_falls_back_to_raw_html():
    text = "notes before <!doctype html><html><body><main id='ndw-content'>Raw</main></body></html>"

    assert llm_client.extract_final_html_blocks(text) == [
        "<!doctype html><html><body><main id='ndw-content'>Raw</main></body></html>"
    ]


def test_normalize_strips_external_assets():
    html = (
        "<!doctype html><html><head>"
        '<script src="https://cdn.tailwindcss.com"></script>'
        '<link rel="stylesheet" href="https://example.com/style.css">'
        "</head><body><main id='ndw-content'>Hello</main></body></html>"
    )
    doc = llm_client._normalize_doc({"kind": "full_page_html", "html": html})

    assert "https://cdn.tailwindcss.com" not in doc["html"]
    assert "https://example.com/style.css" not in doc["html"]
    assert doc["ndw_debug"]["external_assets_removed"]


def test_normalize_removes_visible_code_artifacts_without_touching_scripts():
    html = (
        "<!doctype html><html><body>"
        "<main id='ndw-content'><p>ESTABLISHED 1974 // COASTAL ARCHIVES</p><h1>// Start Booking</h1></main>"
        "<script>// Keep this script comment\nconst label = 'A // B';</script>"
        "</body></html>"
    )
    doc = llm_client._normalize_doc({"kind": "full_page_html", "html": html})

    assert "ESTABLISHED 1974 - COASTAL ARCHIVES" in doc["html"]
    assert "<h1>Start Booking</h1>" in doc["html"]
    assert "// Keep this script comment" in doc["html"]
    assert "const label = 'A // B';" in doc["html"]
    assert doc["ndw_debug"]["external_assets_removed"]


def test_first_js_syntax_error_exposes_preflight_helper():
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main id='ndw-content'></main><script>function (</script></body></html>",
    }

    assert llm_client._first_js_syntax_error(doc)


def test_structured_call_can_disable_non_transport_400_retry(monkeypatch):
    calls = []

    class Response:
        status_code = 400
        text = '{"error":"invalid schema"}'

    monkeypatch.setattr(llm_client, "GEMINI_THINKING_LEVEL", "medium")
    monkeypatch.setattr(
        llm_client.requests,
        "post",
        lambda *args, **kwargs: calls.append((args, kwargs)) or Response(),
    )

    out = llm_client._call_gemini_structured(
        [{"text": "plan"}],
        {"type": "object", "properties": {}},
        endpoint="https://example.invalid/generate",
        retry_without_thinking=False,
    )

    assert out is None
    assert len(calls) == 1
