import json
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api import llm_client

client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}

def test_stream_emits_one_live_premium_page(monkeypatch):
    from api import main as main_mod
    
    # Mock llm_status and prefetch queue to be empty
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 0)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: {"kind": "full_page_html", "html": "OK"})

    r = client.post("/generate/stream", json={"brief": "test", "seed": 1}, headers=API_HEADERS)
    assert r.status_code == 200
    
    events = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "page"
    assert events[1]["data"]["html"] == "OK"
    assert len(events) == 2


def test_stream_serves_premium_queue_without_followups(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: {"kind": "full_page_html", "html": "QUEUED"} if lane == "premium" else None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 2)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("queued page should serve first")))

    r = client.post("/generate/stream", json={"brief": "queue", "seed": 7}, headers=API_HEADERS)
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "page"
    assert events[1]["data"]["html"] == "QUEUED"
    assert len(events) == 2


def test_stream_live_premium_failure_emits_error(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 0)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: {"error": "Premium generation failed"})

    r = client.post("/generate/stream", json={"brief": "review", "seed": 5}, headers=API_HEADERS)
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "error"
    assert events[1]["data"]["error"] == "Premium generation failed"
    assert len(events) == 2

def test_generate_endpoint_uses_live_premium_when_queue_empty(monkeypatch):
    from api import main as main_mod
    
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    
    page_winner = {"kind": "full_page_html", "html": "WINNER"}
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: page_winner)

    r = client.post("/generate", json={"brief": "race", "seed": 99}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["html"] == "WINNER"

def test_stream_rate_limit_headers(monkeypatch):
    from api import main as main_mod
    # Force rate limit
    monkeypatch.setattr(main_mod, "_safe_rate_check", lambda b, k: (False, 0, 1234567890))
    
    r = client.post("/generate/stream", json={"brief": "fast", "seed": 1}, headers=API_HEADERS)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert r.json()["error"] == "rate limit exceeded"
