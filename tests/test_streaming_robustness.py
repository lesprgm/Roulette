import json
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api import llm_client

client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}

def test_stream_handles_malformed_json_chunks(monkeypatch):
    from api import main as main_mod
    
    # Mock llm_status and prefetch queue to be empty
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda: 0)

    # Mock llm_generate_page_burst to yield a mix of valid and invalid chunks
    def mock_burst_with_errors(brief, seed, user_key=None):
        yield {"kind": "full_page_html", "html": "OK"}
        yield {"error": "Simulated LLM Error"}
    
    monkeypatch.setattr(main_mod, "llm_generate_page_burst", mock_burst_with_errors)

    r = client.post("/generate/stream", json={"brief": "test", "seed": 1}, headers=API_HEADERS)
    assert r.status_code == 200
    
    events = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    
    # We expect: meta, page (OK), page (error)
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "page"
    assert events[1]["data"]["html"] == "OK"
    assert events[2]["event"] == "page"
    assert "error" in events[2]["data"]

def test_generate_endpoint_uses_first_to_finish_burst(monkeypatch):
    from api import main as main_mod
    
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda: None)
    
    page_winner = {"kind": "full_page_html", "html": "WINNER"}
    
    def mock_burst(brief, seed, user_key=None):
        yield page_winner
        yield {"kind": "full_page_html", "html": "LOSER"}

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", mock_burst)

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
