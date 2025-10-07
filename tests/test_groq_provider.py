import json as jsonlib
import types
import pytest

from api import llm_client


def _normalized_page():
    return {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}


def test_prefers_groq_over_openrouter(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "also-present")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)

    called = {"groq": False, "openrouter": False}

    def groq_ok(brief, seed):
        called["groq"] = True
        return _normalized_page()

    def or_never(brief, seed):
        called["openrouter"] = True
        raise AssertionError("OpenRouter should not be called when Groq succeeds")

    monkeypatch.setattr(llm_client, "_call_groq_for_page", groq_ok)
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", or_never)

    out = llm_client.generate_page("any", seed=42)
    assert out.get("kind") == "full_page_html"
    assert called["groq"] is True
    assert called["openrouter"] is False


def test_fallbacks_to_openrouter_when_groq_fails(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "also-present")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "FORCE_OPENROUTER_ONLY", False)

    called = {"groq": False, "openrouter": False}

    def groq_fail(brief, seed):
        called["groq"] = True
        return None

    def or_ok(brief, seed):
        called["openrouter"] = True
        return _normalized_page()

    monkeypatch.setattr(llm_client, "_call_groq_for_page", groq_fail)
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", or_ok)

    out = llm_client.generate_page("any", seed=123)
    assert out.get("kind") == "full_page_html"
    assert called["groq"] is True
    assert called["openrouter"] is True


def test__call_groq_for_page_hits_groq_endpoint(monkeypatch):
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "fake-key")
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

    out = llm_client._call_groq_for_page("brief", seed=7)
    assert out and out.get("kind") == "full_page_html"
    assert captured["urls"], "No HTTP calls captured"
    assert captured["urls"][0] == llm_client.GROQ_ENDPOINT
    assert captured["bodies"][0].get("response_format") == {"type": "json_object"}
