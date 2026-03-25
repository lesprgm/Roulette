import json
from fastapi.testclient import TestClient

from api.main import app, GenerateRequest

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
    assert body.get("provider") in ("groq", "openrouter", "gemini", None)
    assert "using" in body
    assert "has_token" in body


def test_generate_request_defaults_to_fast():
    req = GenerateRequest()
    assert req.quality == "fast"


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
    if page.get("kind") == "full_page_html":
        assert isinstance(page.get("html"), str) and "<" in page["html"]
    else:
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
        if page_from_event.get("kind") == "full_page_html":
            assert isinstance(page_from_event.get("html"), str) and "<" in page_from_event["html"]
        else:
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
    if page.get("kind") == "full_page_html":
        assert isinstance(page.get("html"), str) and "<" in page["html"]
    else:
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
        assert "message" in j and "retry_after_seconds" in j
        assert j["retry_after_seconds"] >= 0
        assert "seconds" in j["message"].lower()
    finally:
        rl.MAX_REQUESTS = old_max


def test_generate_endpoint_premium_bypasses_prefetch(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    queued = {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium Queue</body></html>"}
    monkeypatch.setattr(main_mod, "_consume_premium_quota", lambda key: (True, 4, 9999999999))
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: queued if lane == "premium" else None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 2)
    monkeypatch.setattr(main_mod, "_serve_or_fill_premium_batch", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("premium queue should serve first")))

    r = client.post("/generate", json={"brief": "", "seed": 9, "quality": "premium"}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json() == queued


def test_stream_endpoint_premium_emits_single_page(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    page = {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium Stream</body></html>"}
    monkeypatch.setattr(main_mod, "_consume_premium_quota", lambda key: (True, 4, 9999999999))
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: page)

    r = client.post("/generate/stream", json={"brief": "", "seed": 12, "quality": "premium"}, headers=API_HEADERS)
    assert r.status_code == 200
    lines = [json.loads(ln) for ln in r.text.strip().splitlines() if ln.strip()]
    assert lines[0]["event"] == "meta"
    page_events = [line for line in lines if line.get("event") == "page"]
    assert len(page_events) == 1
    assert page_events[0]["data"] == page


def test_stream_fast_prefetch_and_followups_increment_only_served_page(monkeypatch):
    from api import main as main_mod

    increments = []
    queued = {"kind": "full_page_html", "html": "<!doctype html><html><body>Queued Fast</body></html>"}
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: queued if lane is None else None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 2)
    monkeypatch.setattr(main_mod.counter, "increment", lambda n=1: increments.append(n) or 1)

    r = client.post("/generate/stream", json={"brief": "", "seed": 12, "quality": "fast"}, headers=API_HEADERS)
    assert r.status_code == 200
    lines = [json.loads(ln) for ln in r.text.strip().splitlines() if ln.strip()]
    page_events = [line for line in lines if line.get("event") == "page"]
    assert len(page_events) == 1
    assert page_events[0]["data"] == queued
    assert increments == [1]


def test_generate_endpoint_premium_quota_exhaustion(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod, "_consume_premium_quota", lambda key: (False, 0, 9999999999))

    r = client.post("/generate", json={"brief": "", "seed": 9, "quality": "premium"}, headers=API_HEADERS)
    assert r.status_code == 429
    assert "premium" in r.json()["error"]


def test_generate_endpoint_premium_empty_queue_batches(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod, "_consume_premium_quota", lambda key: (True, 4, 9999999999))
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    page = {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium Batch First</body></html>"}
    monkeypatch.setattr(main_mod, "_serve_or_fill_premium_batch", lambda *args, **kwargs: page)

    r = client.post("/generate", json={"brief": "", "seed": 9, "quality": "premium"}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json() == page


def test_generate_endpoint_premium_refunds_quota_on_failed_batch(monkeypatch):
    from api import main as main_mod

    refunds = []
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod, "_consume_premium_quota", lambda key: (True, 4, 9999999999))
    monkeypatch.setattr(main_mod, "_refund_premium_quota", lambda key: refunds.append(key) or (True, 5, 9999999999))
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod, "_serve_or_fill_premium_batch", lambda *args, **kwargs: {"error": "Premium generation failed"})

    r = client.post("/generate", json={"brief": "", "seed": 9, "quality": "premium"}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["error"] == "Premium generation failed"
    assert len(refunds) == 1


def test_consume_premium_quota_uses_credit_before_limiter(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod.premium_credits, "consume", lambda key: True)
    monkeypatch.setattr(main_mod, "_inspect_premium_quota", lambda key: (False, 0, 9999999999))
    monkeypatch.setattr(
        main_mod,
        "_safe_rate_check",
        lambda bucket, key: (_ for _ in ()).throw(AssertionError("limiter should not increment when a credit is available")),
    )

    allowed, remaining, reset_ts = main_mod._consume_premium_quota("demo_123")
    assert allowed is True
    assert remaining == 0
    assert reset_ts == 9999999999


def test_refund_premium_quota_grants_credit_when_backend_refund_missing(monkeypatch):
    from api import main as main_mod

    granted = []
    monkeypatch.setattr(main_mod, "_rl_instance", None)
    monkeypatch.setattr(main_mod, "_rl_mod", object())
    monkeypatch.setattr(main_mod.premium_credits, "grant", lambda key, amount=1: granted.append((key, amount)) or amount)
    monkeypatch.setattr(main_mod.premium_credits, "peek", lambda key: 1)
    monkeypatch.setattr(main_mod, "_inspect_premium_quota", lambda key: (False, 0, 9999999999))

    allowed, remaining, reset_ts = main_mod._refund_premium_quota("demo_123")
    assert allowed is True
    assert remaining == 1
    assert reset_ts == 9999999999
    assert granted == [("demo_123", 1)]
