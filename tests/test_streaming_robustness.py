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
    
    # We expect: meta, page (OK) — followups are enqueued, not streamed
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "page"
    assert events[1]["data"]["html"] == "OK"
    assert len(events) == 2


def test_stream_burst_enqueues_followups(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda: 0)

    enqueued = []

    def fake_enqueue(doc):
        enqueued.append(doc)
        return None

    monkeypatch.setattr(main_mod.prefetch, "enqueue", fake_enqueue)
    monkeypatch.setattr(main_mod, "run_compliance_batch", lambda docs: [{"index": 0, "ok": True}, {"index": 1, "ok": True}])

    def mock_burst(brief, seed, user_key=None):
        yield {"kind": "full_page_html", "html": "FIRST"}
        yield {"kind": "full_page_html", "html": "SECOND"}
        yield {"error": "Simulated LLM Error"}

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", mock_burst)

    r = client.post("/generate/stream", json={"brief": "queue", "seed": 7}, headers=API_HEADERS)
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "page"
    assert events[1]["data"]["html"] == "FIRST"
    assert len(events) == 2
    assert len(enqueued) == 1
    assert enqueued[0]["html"] == "SECOND"


def test_stream_burst_reviews_followups(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda: None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda: 0)

    enqueued = []

    def fake_enqueue(doc):
        enqueued.append(doc)
        return None

    monkeypatch.setattr(main_mod.prefetch, "enqueue", fake_enqueue)

    def mock_review(docs):
        return [
            {"index": 0, "ok": True, "doc": {"kind": "full_page_html", "html": "SECOND_FIXED"}},
            {"index": 1, "ok": False, "issues": [{"message": "blocked"}]},
        ]

    monkeypatch.setattr(main_mod, "run_compliance_batch", mock_review)

    def mock_burst(brief, seed, user_key=None):
        yield {"kind": "full_page_html", "html": "FIRST"}
        yield {"kind": "full_page_html", "html": "SECOND"}
        yield {"kind": "full_page_html", "html": "THIRD"}

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", mock_burst)

    r = client.post("/generate/stream", json={"brief": "review", "seed": 5}, headers=API_HEADERS)
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    assert events[0]["event"] == "meta"
    assert events[1]["event"] == "page"
    assert events[1]["data"]["html"] == "FIRST"
    assert len(events) == 2
    assert len(enqueued) == 1
    assert enqueued[0]["html"] == "SECOND_FIXED"
    assert enqueued[0]["review"]["ok"] is True

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
