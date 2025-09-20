from fastapi.testclient import TestClient
from api.main import app
import json

client = TestClient(app)

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_generate_success():
    payload = {"brief": "Landing for a sports analytics tool", "seed": 123}
    r = client.post("/generate", json=payload)
    assert r.status_code == 200
    data = r.json()
    # essential fields exist
    for key in ["components", "layout", "palette", "links", "seed", "model_version"]:
        assert key in data
    # it should be hero type for our stub
    assert data["components"][0]["type"] == "hero"

def test_validate_failure_on_missing_component_id():
    bad_page = {
        "components": [
            {"type": "hero", "props": {"title": "X"}}  # missing "id"
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
        "links": ["/about"],
        "seed": 1,
        "model_version": "v0"
    }
    r = client.post("/validate", json={"page": bad_page})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["valid"] is False
    # Expect an error mentioning 'id'
    messages = [e["message"] for e in detail["errors"]]
    # More flexible check
    assert any("id" in m and "required" in m for m in messages)
    
def test_stream_returns_ndjson():
    payload = {"brief": "Landing page", "seed": 123}
    r = client.post("/generate/stream", json=payload)
    assert r.status_code == 200
    lines = [json.loads(line) for line in r.text.strip().splitlines()]
    assert all("component" in line for line in lines)
    assert lines[0]["component"]["type"] == "hero"
    
def test_cache_roundtrip():
    payload = {"brief": "Cache me", "seed": 1}
    r1 = client.post("/generate", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/generate", json=payload)
    assert r2.status_code == 200
    assert r1.json() == r2.json()  # should be identical due to cache hit

def test_rate_limit(monkeypatch):
    # temporarily tighten limits for the test:
    import api.ratelimit as rl
    old_max = rl.MAX_REQUESTS
    rl.MAX_REQUESTS = 2
    try:
        payload = {"brief": "Hot path", "seed": 1}
        assert client.post("/generate", json=payload).status_code == 200
        assert client.post("/generate", json=payload).status_code == 200
        resp = client.post("/generate", json=payload)
        assert resp.status_code == 429
    finally:
        rl.MAX_REQUESTS = old_max



