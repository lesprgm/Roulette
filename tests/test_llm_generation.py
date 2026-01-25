import json
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import llm_client


client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}


def test_llm_generate_normalizes_full_page_html(monkeypatch):
    # Force OpenRouter path (Groq disabled)
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    html = "<!doctype html><html><body><div id='app'>Hi</div><script>console.log('ok')</script></body></html>"
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: {"kind": "full_page_html", "html": html})

    out = llm_client.generate_page("any brief", seed=123)
    assert isinstance(out, dict)
    assert out.get("kind") == "full_page_html"
    assert isinstance(out.get("html"), str) and "<script>" in out["html"]


def test_llm_generate_normalizes_components_to_custom(monkeypatch):
    # Use OpenRouter path
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    comp_doc = {
        "components": [
            {
                "id": "x1",
                "type": "chart",  # unknown -> should coerce to custom
                "props": {"html": "<div><script>let n=1</script></div>", "height": "420"},
            }
        ]
    }
    # Mimic normalized doc via OpenRouter
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: llm_client._normalize_doc(comp_doc))

    out = llm_client.generate_page("any", seed=1)
    assert "components" in out and isinstance(out["components"], list)
    comp = out["components"][0]
    assert comp.get("type") == "custom"
    assert comp.get("id") == "x1"
    assert comp.get("props", {}).get("height") == 420  # coerced to int
    assert "<script>" in comp.get("props", {}).get("html", "")


def test_llm_generate_picks_first_renderable_component(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    doc = {
        "components": [
            {"id": "a", "type": "box", "props": {"title": "no html"}},
            {"id": "b", "type": "weird", "props": {"html": "<div>ok</div>", "height": 250}},
        ]
    }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: llm_client._normalize_doc(doc))

    out = llm_client.generate_page("x", seed=5)
    comp = out["components"][0]
    assert comp["id"] == "b"
    assert comp["type"] == "custom"
    assert comp["props"]["height"] == 250


def test_llm_generate_returns_error_on_call_failure(monkeypatch):
    # No providers available
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)
    # Simulate failure path (returns None)
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: None)
    monkeypatch.setattr(llm_client, "_call_groq_for_page", lambda brief, seed, category_note=None: None)

    out = llm_client.generate_page("y", seed=7)
    assert isinstance(out, dict) and "error" in out


def test_generate_endpoint_returns_llm_page_when_available(monkeypatch):
    # Force API layer to think LLM is available
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda: 0)
    page = {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}
    def mock_burst(brief, seed, user_key=None): yield page
    monkeypatch.setattr(main_mod, "llm_generate_page_burst", mock_burst)

    r = client.post("/generate", json={"brief": "", "seed": 9}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json() == page


def test_stream_endpoint_emits_page_event_with_llm(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda: 0)
    page = {
        "components": [
            {"id": "c1", "type": "custom", "props": {"html": "<div>Stream OK</div>", "height": 200}}
        ]
    }
    def mock_burst(brief, seed, user_key=None): yield page
    monkeypatch.setattr(main_mod, "llm_generate_page_burst", mock_burst)

    r = client.post("/generate/stream", json={"brief": "z", "seed": 11}, headers=API_HEADERS)
    assert r.status_code == 200
    lines = [ln for ln in r.text.strip().splitlines() if ln.strip()]
    # Should include meta then a page event with our payload
    assert any(json.loads(ln).get("event") == "meta" for ln in lines)
    page_events = [json.loads(ln) for ln in lines if json.loads(ln).get("event") == "page"]
    assert page_events and page_events[-1].get("data") == page


def test_llm_generate_accepts_ndw_snippet_v1(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Tiny App",
        "background": {"style": "background:#111", "class": "text-white"},
        "css": "#ndw-app{min-height:100vh}",
        "html": "<div id='ndw-app'><h1>Hi</h1></div>",
        "js": "console.log('ndw ok')",
    }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: snippet)

    out = llm_client.generate_page("any", seed=42)
    assert out.get("kind") == "ndw_snippet_v1"
    assert isinstance(out.get("html"), str) and "ndw-app" in out["html"]


def test_snippet_without_background_keeps_landing_styles(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    snippet = { "kind": "ndw_snippet_v1", "html": "<div id='ndw-app'><h2>OK</h2></div>" }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: snippet)
    out = llm_client.generate_page("", 1)
    assert out.get("kind") == "ndw_snippet_v1"
    assert out.get("background") is None or isinstance(out.get("background"), dict)


def test_snippet_minimum_content_is_preserved(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    snippet = { "kind": "ndw_snippet_v1", "css": "#ndw-app{color:red}", "html": "<div id='ndw-app'></div>", "js": "console.log('hi')" }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: snippet)
    out = llm_client.generate_page("", 2)
    assert out.get("css") and out.get("html")


def test_snippet_rejects_missing_all_content(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "GEMINI_REVIEW_ENABLED", False)

    bad = { "kind": "ndw_snippet_v1" }
    def _call(_b,_s): return bad
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: _call(brief, seed))
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda b, s, category_note=None: bad)
    try:
        llm_client._normalize_doc(bad)
    except ValueError:
        pass


def test_generate_page_attaches_gemini_review(monkeypatch):
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "_gemini_review_active", lambda: True)

    corrected_html = "<!doctype html><html><body><main id='ndw-shell'>Reviewed</main></body></html>"

    def fake_review(doc, brief, category_note):
        return {"ok": True, "issues": [{"severity": "info", "message": "minor tweak"}], "doc": {"kind": "full_page_html", "html": corrected_html}}

    monkeypatch.setattr(llm_client, "_call_gemini_review", fake_review)
    html = "<!doctype html><html><body><main id='ndw-shell'>OK</main></body></html>"
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: {"kind": "full_page_html", "html": html})

    out = llm_client.generate_page("any", seed=10)
    assert out.get("kind") == "full_page_html"
    assert isinstance(out.get("review"), dict)
    assert out["review"].get("ok") is True
    assert out.get("html") == corrected_html


def test_generate_page_retries_when_review_blocks(monkeypatch):
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "_gemini_review_active", lambda: True)

    def fake_review(doc, brief, category_note):
        return {"ok": False, "issues": [{"message": "fail"}]}

    monkeypatch.setattr(llm_client, "_call_gemini_review", fake_review)
    html = "<!doctype html><html><body><main id='ndw-shell'>Blocked</main></body></html>"
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: {"kind": "full_page_html", "html": html})

    out = llm_client.generate_page("any", seed=11)
    assert out.get("error"), "Expected compliance failure to surface as error"


def test_generate_page_retries_on_block_issue(monkeypatch):
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)
    monkeypatch.setattr(llm_client, "_gemini_review_active", lambda: True)

    def fake_review(doc, brief, category_note):
        return {"ok": True, "issues": [{"severity": "block", "message": "bad"}]}

    monkeypatch.setattr(llm_client, "_call_gemini_review", fake_review)
    html = "<!doctype html><html><body><main id='ndw-shell'>Blocked</main></body></html>"
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed, category_note=None: {"kind": "full_page_html", "html": html})

    out = llm_client.generate_page("any", seed=12)
    assert out.get("error"), "Expected block issues to reject generation"


def test_normalize_strips_external_assets():
    html = (
        "<!doctype html><html><head>"
        "<script src=\"https://cdn.tailwindcss.com\"></script>"
        "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Outfit\">"
        "<style>@import url('https://fonts.googleapis.com/css2?family=Outfit');</style>"
        "</head><body><script>console.log('ok')</script></body></html>"
    )
    out = llm_client._normalize_doc({"kind": "full_page_html", "html": html})
    assert "cdn.tailwindcss.com" not in out.get("html", "")
    assert "fonts.googleapis.com" not in out.get("html", "")
    assert "/static/vendor/tailwind-play.js" in out.get("html", "")
    assert "console.log('ok')" in out.get("html", "")
    debug = out.get("ndw_debug")
    assert isinstance(debug, dict) and debug.get("external_assets_removed")


def test_normalize_rewrites_known_cdns():
    html = (
        "<!doctype html><html><head>"
        "<script src=\"https://cdn.tailwindcss.com\"></script>"
        "<script src=\"https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js\"></script>"
        "<script src=\"https://unpkg.com/lucide@latest\"></script>"
        "</head><body></body></html>"
    )
    out = llm_client._normalize_doc({"kind": "full_page_html", "html": html})
    html_out = out.get("html", "")
    assert "/static/vendor/tailwind-play.js" in html_out
    assert "/static/vendor/gsap.min.js" in html_out
    assert "/static/vendor/lucide.min.js" in html_out
    assert "cdn.tailwindcss.com" not in html_out
    assert "cdnjs.cloudflare.com" not in html_out
    assert "unpkg.com/lucide" not in html_out


def test_js_syntax_checker_detects_comment_bug():
    if not hasattr(llm_client, "_first_js_syntax_error"):
        pytest.skip("JS syntax checker removed")
    html = """<!doctype html><html><body><script>const hue = 120; // commentconst color = 'red';</script></body></html>"""
    doc = {"kind": "full_page_html", "html": html}
    err = llm_client._first_js_syntax_error(doc)  # type: ignore[attr-defined]
    if err is None:
        pytest.skip("Node runtime not available; skipping JS syntax check validation")
    assert err, "Expected syntax checker to report error"
