import re
from fastapi.testclient import TestClient
from api.main import app
from api import prefetch as prefetch_mod
from api import llm_client

client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}


def test_generate_returns_snippet_and_no_external_scripts(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", True)

    html = """
    <div id='ndw-app'>
      <h1>Hi</h1>
      <script src='https://bad.example.com/x.js'></script>
      <script>window.__ran = (window.__ran||0)+1;</script>
    </div>
    """
    snippet = {
        "kind": "ndw_snippet_v1",
        "html": html,
        "css": "#ndw-app{min-height:50vh}",
        "js": "window.__ran = (window.__ran||0)+1;",
    }
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", lambda brief, seed: snippet)
    monkeypatch.setattr(prefetch_mod, "dequeue", lambda: None)
    monkeypatch.setattr(prefetch_mod, "size", lambda: 0)

    r = client.post("/generate", json={"brief": "", "seed": 123}, headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get("kind") == "ndw_snippet_v1"
    assert "<script src=" in data.get("html", "")
    assert isinstance(data.get("css"), str)
    assert isinstance(data.get("js"), str)
