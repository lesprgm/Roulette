import json
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

API_HEADERS = {"x-api-key": "demo_123"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_llm_status_shape():
    r = client.get("/llm/status")
    assert r.status_code == 200
    body = r.json()
    # Provider may be 'groq' or 'openrouter' depending on env
    assert body.get("provider") in ("groq", "openrouter", None)
    assert "using" in body
    assert "has_token" in body


def test_validate_success():
    good_page = {
        "components": [
            {"id": "hero-1", "type": "hero", "props": {"title": "Welcome", "subtitle": "Hello"}}
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
        "links": ["/about"],
        "seed": 1,
        "model_version": "v0",
    }
    r = client.post("/validate", json={"page": good_page})
    assert r.status_code == 200
    detail = r.json()["detail"]
    assert detail["valid"] is True


def test_validate_failure_on_missing_component_id():
    bad_page = {
        "components": [
            {"type": "hero", "props": {"title": "X"}}  
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
        "links": ["/about"],
        "seed": 1,
        "model_version": "v0",
    }
    r = client.post("/validate", json={"page": bad_page})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["valid"] is False
    messages = [e["message"] for e in detail["errors"]]
    assert any("id" in m.lower() or "required" in m.lower() for m in messages)


def test_generate_ok(monkeypatch):
    from api import main as main_mod
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "stub", "has_token": False})
    payload = {"brief": "Landing page", "seed": 123}
    r = client.post("/generate", json=payload, headers=API_HEADERS)
    assert r.status_code == 200
    page = r.json()
    assert "components" in page and isinstance(page["components"], list)
    assert "layout" in page and "palette" in page


def test_stream_returns_ndjson(monkeypatch):
    from api import main as main_mod
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "stub", "has_token": False})
    payload = {"brief": "Landing page", "seed": 123}
    r = client.post("/generate/stream", json=payload, headers=API_HEADERS)
    assert r.status_code == 200

    raw_lines = [ln for ln in r.text.strip().splitlines() if ln.strip()]
    assert len(raw_lines) >= 1

    parsed_lines = []
    all_component_lines = True
    page_from_event = None

    for ln in raw_lines:
        try:
            obj = json.loads(ln)
            parsed_lines.append(obj)
            if not (isinstance(obj, dict) and "component" in obj):
                all_component_lines = False
            if isinstance(obj, dict) and obj.get("event") == "page" and isinstance(obj.get("data"), dict):
                page_from_event = obj["data"]
        except json.JSONDecodeError:
            all_component_lines = False

    if all_component_lines:
        assert all(isinstance(o, dict) and "component" in o for o in parsed_lines)
        return

    if page_from_event is not None:
        assert "components" in page_from_event and isinstance(page_from_event["components"], list) and len(page_from_event["components"]) >= 1
        return

    stitched = "".join(raw_lines)
    try:
        page = json.loads(stitched)
    except json.JSONDecodeError:
        joined = r.text
        first = joined.find("{")
        last = joined.rfind("}")
        assert first != -1 and last != -1 and last > first, "Stream did not contain a JSON object or component lines"
        page = json.loads(joined[first:last + 1])

    assert isinstance(page, dict)
    assert "components" in page and isinstance(page["components"], list) and len(page["components"]) >= 1


def test_rate_limit(monkeypatch):
    import api.ratelimit as rl

    rl._reset()
    old_max = rl.MAX_REQUESTS
    rl.MAX_REQUESTS = 2
    try:
        payload = {"brief": "Hot path", "seed": 1}
        headers = API_HEADERS
        assert client.post("/generate", json=payload, headers=headers).status_code == 200
        assert client.post("/generate", json=payload, headers=headers).status_code == 200
        resp = client.post("/generate", json=payload, headers=headers)
        assert resp.status_code == 429
        j = resp.json()
        assert ("retry_after" in j) or ("reset" in j)
    finally:
        rl.MAX_REQUESTS = old_max
