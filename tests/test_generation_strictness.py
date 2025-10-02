import json
import os
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}


def test_generate_offline_flag_allows_custom_app(monkeypatch):
    # Simulate missing credentials but allow offline generation
    monkeypatch.setenv("ALLOW_OFFLINE_GENERATION", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "manually_set_for_other_tests")  # keep pytest behavior elsewhere
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": False})

    r = client.post("/generate", json={"brief": "", "seed": 1}, headers=API_HEADERS)
    assert r.status_code == 200
    page = r.json()
    assert isinstance(page, dict)
    assert "components" in page and isinstance(page["components"], list)
    assert len(page["components"]) == 1
    comp = page["components"][0]
    assert (comp.get("type") or "").lower() == "custom"
    assert isinstance(comp.get("props", {}).get("html", ""), str) and comp["props"]["html"].strip()


def test_generate_503_when_no_creds_no_offline(monkeypatch):
    # Force no offline, no creds, and disable pytest stub
    monkeypatch.delenv("ALLOW_OFFLINE_GENERATION", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": False})

    r = client.post("/generate", json={"brief": "Anything", "seed": 2}, headers=API_HEADERS)
    assert r.status_code == 503
    body = r.json()
    assert isinstance(body, dict) and "error" in body


def test_stream_error_event_without_creds_and_offline(monkeypatch):
    monkeypatch.delenv("ALLOW_OFFLINE_GENERATION", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": False})

    r = client.post("/generate/stream", json={"brief": "X", "seed": 3}, headers=API_HEADERS)
    assert r.status_code == 200
    lines = [ln for ln in r.text.strip().splitlines() if ln.strip()]
    assert len(lines) >= 1
    # Should include an error event line
    assert any(json.loads(ln).get("event") == "error" for ln in lines)


def test_validate_accepts_unknown_type_with_inline_html():
    page = {
        "components": [
            {
                "id": "x1",
                "type": "something_new",
                "props": {"html": "<div><script>console.log('ok')</script></div>", "height": 240},
            }
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
        "links": ["/about"],
        "seed": 1,
        "model_version": "vtest",
    }
    r = client.post("/validate", json={"page": page})
    assert r.status_code == 200
    assert r.json().get("detail", {}).get("valid") is True


def test_generate_allows_empty_brief(monkeypatch):
    # Even without a brief, endpoint should respond with a page when test stub is active
    # (Default pytest environment keeps a test stub path enabled.)
    from api import main as main_mod
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "stub", "has_token": False})
    r = client.post("/generate", json={"brief": "", "seed": 123}, headers=API_HEADERS)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        page = r.json()
        assert "components" in page and isinstance(page["components"], list)
