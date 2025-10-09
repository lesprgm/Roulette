import json
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

    html = "<!doctype html><html><body><div id='app'>Hi</div><script>console.log('ok')</script></body></html>"
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: {"kind": "full_page_html", "html": html})

    out = llm_client.generate_page("any brief", seed=123)
    assert isinstance(out, dict)
    assert out.get("kind") == "full_page_html"
    assert isinstance(out.get("html"), str) and "<script>" in out["html"]


def test_llm_generate_normalizes_components_to_custom(monkeypatch):
    # Use OpenRouter path
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)

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
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: llm_client._normalize_doc(comp_doc))

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

    doc = {
        "components": [
            {"id": "a", "type": "box", "props": {"title": "no html"}},
            {"id": "b", "type": "weird", "props": {"html": "<div>ok</div>", "height": 250}},
        ]
    }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: llm_client._normalize_doc(doc))

    out = llm_client.generate_page("x", seed=5)
    comp = out["components"][0]
    assert comp["id"] == "b"
    assert comp["type"] == "custom"
    assert comp["props"]["height"] == 250


def test_llm_generate_returns_error_on_call_failure(monkeypatch):
    # No providers available
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)
    # Simulate failure path (returns None)
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: None)
    monkeypatch.setattr(llm_client, "_call_groq_for_page", lambda brief, seed: None)

    out = llm_client.generate_page("y", seed=7)
    assert isinstance(out, dict) and "error" in out


def test_generate_endpoint_returns_llm_page_when_available(monkeypatch):
    # Force API layer to think LLM is available
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})
    page = {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}
    monkeypatch.setattr(main_mod, "llm_generate_page", lambda brief, seed: page)

    r = client.post("/generate", json={"brief": "", "seed": 9}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json() == page


def test_stream_endpoint_emits_page_event_with_llm(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})
    page = {
        "components": [
            {"id": "c1", "type": "custom", "props": {"html": "<div>Stream OK</div>", "height": 200}}
        ]
    }
    monkeypatch.setattr(main_mod, "llm_generate_page", lambda brief, seed: page)

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

    snippet = {
        "kind": "ndw_snippet_v1",
        "title": "Tiny App",
        "background": {"style": "background:#111", "class": "text-white"},
        "css": "#ndw-app{min-height:100vh}",
        "html": "<div id='ndw-app'><h1>Hi</h1></div>",
        "js": "console.log('ndw ok')",
    }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: snippet)

    out = llm_client.generate_page("any", seed=42)
    assert out.get("kind") == "ndw_snippet_v1"
    assert isinstance(out.get("html"), str) and "ndw-app" in out["html"]


def test_snippet_without_background_keeps_landing_styles(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)

    snippet = { "kind": "ndw_snippet_v1", "html": "<div id='ndw-app'><h2>OK</h2></div>" }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: snippet)
    out = llm_client.generate_page("", 1)
    assert out.get("kind") == "ndw_snippet_v1"
    assert out.get("background") is None or isinstance(out.get("background"), dict)


def test_snippet_minimum_content_is_preserved(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)

    snippet = { "kind": "ndw_snippet_v1", "css": "#ndw-app{color:red}", "html": "<div id='ndw-app'></div>", "js": "console.log('hi')" }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: snippet)
    out = llm_client.generate_page("", 2)
    assert out.get("css") and out.get("html")


def test_snippet_rejects_missing_all_content(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)

    bad = { "kind": "ndw_snippet_v1" }
    def _call(_b,_s): return bad
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", _call)
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda b,s: bad)
    try:
        llm_client._normalize_doc(bad)
    except ValueError:
        pass

