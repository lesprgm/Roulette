import json as jsonlib
import types
import pytest

from api import llm_client


def _normalized_page():
    return {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}


def test_prefers_openrouter_over_groq(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "also-present")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)

    called = {"groq": False, "openrouter": False}

    def openrouter_ok(brief, seed, category_note=None):
        called["openrouter"] = True
        return _normalized_page()

    def groq_never(brief, seed, category_note=None):
        called["groq"] = True
        raise AssertionError("Groq should not be called when OpenRouter succeeds")

    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", openrouter_ok)
    monkeypatch.setattr(llm_client, "_call_groq_for_page", groq_never)

    out = llm_client.generate_page("any", seed=42)
    assert out.get("kind") == "full_page_html"
    assert called["openrouter"] is True
    assert called["groq"] is False


def test_fallbacks_to_groq_when_openrouter_fails(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "also-present")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)

    called = {"groq": False, "openrouter": False}

    def openrouter_fail(brief, seed, category_note=None):
        called["openrouter"] = True
        return None

    def groq_ok(brief, seed, category_note=None):
        called["groq"] = True
        return _normalized_page()

    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", openrouter_fail)
    monkeypatch.setattr(llm_client, "_call_groq_for_page", groq_ok)

    out = llm_client.generate_page("any", seed=123)
    assert out.get("kind") == "full_page_html"
    assert called["openrouter"] is True
    assert called["groq"] is True


def test__call_groq_for_page_hits_groq_endpoint(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)

    captured = {"urls": [], "bodies": []}

    class FakeResp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
            self.text = jsonlib.dumps(payload)

        def json(self):
            return self._payload

    def fake_post(url, headers=None, timeout=None, **kwargs):
        json_body = kwargs.get("json")
        captured["urls"].append(url)
        captured["bodies"].append(json_body)
        content = (json_body or {}).get("messages", [{}])[0].get("content", "{}").strip()
        assistant = json_body and {"choices": [{"message": {"content": jsonlib.dumps(_normalized_page())}}]} or {}
        return FakeResp(200, assistant)

    monkeypatch.setattr(llm_client, "requests", types.SimpleNamespace(post=fake_post))

    out = llm_client._call_groq_for_page("brief", seed=7, category_note="test")
    assert out and out.get("kind") == "full_page_html"
    assert captured["urls"], "No HTTP calls captured"
    assert captured["urls"][0] == llm_client.GROQ_ENDPOINT
    assert captured["bodies"][0].get("response_format") == {"type": "json_object"}
