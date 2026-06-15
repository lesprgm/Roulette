import json
import time
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
    assert body.get("provider") in ("gemini", None)
    assert "using" in body
    assert "has_token" in body


def test_generate_request_is_premium_only():
    req = GenerateRequest()
    assert not hasattr(req, "quality")


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
    page = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main id='ndw-content'>Stream Test</main></body></html>",
    }
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: page)
    payload = {"brief": "Landing page", "seed": 123}
    r = client.post("/generate/stream", json=payload, headers=API_HEADERS)
    assert r.status_code == 200

    raw_lines = [ln for ln in r.text.strip().splitlines() if ln.strip()]
    events = [json.loads(line) for line in raw_lines]
    assert events[0]["event"] == "meta"
    assert [event for event in events if event.get("event") == "page"] == [{"event": "page", "data": page}]


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


def test_generate_endpoint_serves_premium_queue_first(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    queued = {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium Queue</body></html>"}
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: queued if lane == "premium" else None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 2)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("premium queue should serve first")))

    r = client.post("/generate", json={"brief": "", "seed": 9}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json() == queued


def test_stream_endpoint_premium_emits_single_page(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    page = {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium Stream</body></html>"}
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: page)

    r = client.post("/generate/stream", json={"brief": "", "seed": 12}, headers=API_HEADERS)
    assert r.status_code == 200
    lines = [json.loads(ln) for ln in r.text.strip().splitlines() if ln.strip()]
    assert lines[0]["event"] == "meta"
    page_events = [line for line in lines if line.get("event") == "page"]
    assert len(page_events) == 1
    assert page_events[0]["data"] == page


def test_stream_premium_queue_increment_only_served_page(monkeypatch):
    from api import main as main_mod

    increments = []
    queued = {"kind": "full_page_html", "html": "<!doctype html><html><body>Queued Premium</body></html>"}
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: queued if lane == "premium" else None)
    monkeypatch.setattr(main_mod.prefetch, "size", lambda lane=None: 2)
    monkeypatch.setattr(main_mod.counter, "increment", lambda n=1: increments.append(n) or 1)

    r = client.post("/generate/stream", json={"brief": "", "seed": 12}, headers=API_HEADERS)
    assert r.status_code == 200
    lines = [json.loads(ln) for ln in r.text.strip().splitlines() if ln.strip()]
    page_events = [line for line in lines if line.get("event") == "page"]
    assert len(page_events) == 1
    assert page_events[0]["data"] == queued
    assert increments == [1]


def test_generate_endpoint_returns_503_when_premium_unavailable(monkeypatch):
    from api import main as main_mod

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("ALLOW_OFFLINE_GENERATION", raising=False)
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: False)

    r = client.post("/generate", json={"brief": "", "seed": 9}, headers=API_HEADERS)
    assert r.status_code == 503
    assert r.json()["error"] == "Missing LLM credentials"


def test_generate_endpoint_premium_empty_queue_generates_live(monkeypatch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    page = {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium Live First</body></html>"}
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: page)

    r = client.post("/generate", json={"brief": "", "seed": 9}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json() == page


def test_generate_endpoint_premium_failure_does_not_increment_counter(monkeypatch):
    from api import main as main_mod

    increments = []
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod.prefetch, "dequeue", lambda lane=None: None)
    monkeypatch.setattr(main_mod, "_stream_premium_first_page", lambda *args, **kwargs: {"error": "Premium generation failed"})
    monkeypatch.setattr(main_mod.counter, "increment", lambda n=1: increments.append(n) or 1)

    r = client.post("/generate", json={"brief": "", "seed": 9}, headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["error"] == "Premium generation failed"
    assert increments == []


def test_generate_single_premium_doc_fail_opens_on_review_timeout(monkeypatch):
    from api import main as main_mod

    page = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main data-region class="min-h-screen bg-[radial-gradient(circle_at_top,#1e293b,#020617)] text-white">
          <section data-region class="p-10">
            <h1>Premium Timeout</h1>
            <button id="play">Play</button>
            <script>document.getElementById('play')?.addEventListener('click',()=>{});</script>
          </section>
        </main>
        </body></html>""",
    }
    monkeypatch.setattr(main_mod, "llm_generate_page_premium", lambda brief, seed, user_key=None: dict(page))

    started = time.monotonic()
    out = main_mod._generate_single_premium_doc("", seed=3, user_key="student", context="premium.stream.first")
    elapsed = time.monotonic() - started
    assert isinstance(out, dict)
    assert out["html"] == page["html"]
    assert "review" not in out
    assert elapsed < 0.75


def test_generate_single_premium_doc_does_not_drop_weak_advisory_doc(monkeypatch):
    from api import main as main_mod

    weak_page = {"kind": "full_page_html", "html": "<!doctype html><html><body><main><button>Try</button></main></body></html>"}
    monkeypatch.setattr(main_mod, "llm_generate_page_premium", lambda brief, seed, user_key=None: dict(weak_page))

    out = main_mod._generate_single_premium_doc("", seed=4, user_key="student", context="premium.stream.first")
    assert isinstance(out, dict)
    assert out["html"] == weak_page["html"]
