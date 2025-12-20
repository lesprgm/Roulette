import json
import os
import time
import importlib
import threading
import uuid

import pytest
from fastapi.testclient import TestClient


API_HEADERS = {"x-api-key": "demo_123"}


@pytest.fixture()
def isolated_prefetch(monkeypatch, tmp_path):
    pf_dir = tmp_path / "pfq"
    seen_file = tmp_path / "seen.json"
    monkeypatch.setenv("PREFETCH_DIR", str(pf_dir))
    monkeypatch.setenv("DEDUPE_RECENT_FILE", str(seen_file))
    monkeypatch.setenv("PREFETCH_TOPUP_ENABLED", "0")

    from api import dedupe as dd
    from api import prefetch as pf
    importlib.reload(dd)
    importlib.reload(pf)

    from api import main as main_mod
    monkeypatch.setattr(main_mod, "prefetch", pf)
    # Speed up tests: remove any artificial prefetch delay during dequeue
    main_mod.PREFETCH_DELAY_MS = 0

    return pf


def _make_custom_doc(html: str, height: int = 200, skeleton_seed: str = ""):
    # Use a unique class to ensure structural uniqueness in tests where dedupe is enabled
    unique_html = f'<div class="test-{skeleton_seed}">{html}</div>' if skeleton_seed else html
    return {
        "components": [
            {
                "id": f"custom-{abs(hash(html))%1_000_000}",
                "type": "custom",
                "props": {"html": unique_html, "height": height},
            }
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
    }


def test_prefetch_enqueue_dequeue_basic(isolated_prefetch):
    pf = isolated_prefetch
    assert pf.size() == 0
    d1 = _make_custom_doc("<div>A</div>", skeleton_seed="1")
    d2 = _make_custom_doc("<div>B</div>", skeleton_seed="2")
    assert pf.enqueue(d1)
    assert pf.enqueue(d2)
    assert pf.size() == 2
    out1 = pf.dequeue()
    out2 = pf.dequeue()
    out3 = pf.dequeue()
    assert isinstance(out1, dict) and isinstance(out2, dict)
    assert out3 is None
    assert pf.size() == 0


def test_prefetch_fill_enqueues_unique(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})

    def _fake_burst(brief: str, seed: int, user_key=None):
        yield _make_custom_doc(f"<div>seed-{seed}</div>", skeleton_seed=str(seed))

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", _fake_burst)
    client = TestClient(app)

    r = client.post("/prefetch/fill", json={"brief": "", "count": 7}, headers=API_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("requested") == 7
    assert body.get("added") == 7
    assert body.get("queue_size") == 7


def test_prefetch_fill_skips_duplicates(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})

    def _same_burst(brief: str, seed: int, user_key=None):
        yield _make_custom_doc("<div>same</div>")

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", _same_burst)
    client = TestClient(app)

    r = client.post("/prefetch/fill", json={"brief": "", "count": 6}, headers=API_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body.get("requested") >= 5 and body.get("requested") <= 10
    assert body.get("added") == 1
    assert body.get("queue_size") == 1


def test_generate_uses_prefetch_first(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod
    pf = isolated_prefetch

    docA = _make_custom_doc("<div>prefetched-A</div>", skeleton_seed="A")
    docB = _make_custom_doc("<div>prefetched-B</div>", skeleton_seed="B")
    assert pf.enqueue(docA)
    assert pf.enqueue(docB)

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})
    sentinel = _make_custom_doc("<div>LLM-Fallback</div>", skeleton_seed="sentinel")
    def _burst_fallback(brief, seed, user_key=None): yield sentinel
    monkeypatch.setattr(main_mod, "llm_generate_page_burst", _burst_fallback)
    client = TestClient(app)

    r1 = client.post("/generate", json={"brief": "", "seed": 1}, headers=API_HEADERS)
    assert r1.status_code == 200
    assert r1.json() == docA
    assert pf.size() == 1

    r2 = client.post("/generate", json={"brief": "", "seed": 2}, headers=API_HEADERS)
    assert r2.status_code == 200
    assert r2.json() == docB
    assert pf.size() == 0

    r3 = client.post("/generate", json={"brief": "", "seed": 3}, headers=API_HEADERS)
    assert r3.status_code == 200
    assert r3.json() == sentinel


def test_top_up_prefetch_retries_after_errors(monkeypatch, isolated_prefetch):
    from api import main as main_mod

    pf = isolated_prefetch
    monkeypatch.setattr(main_mod, "prefetch", pf)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})

    responses = (
        [{"error": "tempo"}, {"error": "429"}] +
        [_make_custom_doc(f"<div>seed-{n}</div>") for n in range(5)]
    )

    call_iter = iter(responses)

    def _burst(brief: str, seed: int, user_key=None):
        def _llm(brief: str, seed: int, user_key=None):
            try:
                return next(call_iter)
            except StopIteration:
                return _make_custom_doc(f"<div>seed-final-{seed}</div>", skeleton_seed=f"final-{seed}")
        yield _llm(brief, seed, user_key)

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", _burst)
    monkeypatch.setattr(main_mod.time, "sleep", lambda *_: None)

    main_mod._top_up_prefetch("", min_fill=3)

    assert pf.size() >= 3


def test_top_up_prefetch_parallel_workers(monkeypatch, isolated_prefetch):
    from api import main as main_mod

    pf = isolated_prefetch
    monkeypatch.setattr(main_mod, "prefetch", pf)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})

    main_mod.PREFETCH_DELAY_MS = 0
    main_mod.PREFETCH_LOW_WATER = 0
    main_mod.PREFETCH_FILL_TO = 4
    main_mod.PREFETCH_REVIEW_BATCH = 2
    main_mod.PREFETCH_MAX_WORKERS = 3

    review_batches = []

    def _capture_review(paths):
        if paths:
            review_batches.append(list(paths))

    monkeypatch.setattr(main_mod, "_schedule_prefetch_review", _capture_review)

    active = {"count": 0, "max": 0}
    lock = threading.Lock()

    def _burst(brief: str, seed: int, user_key=None):
        def _llm(brief: str, seed: int, user_key=None):
            with lock:
                active["count"] += 1
                if active["count"] > active["max"]:
                    active["max"] = active["count"]
            time.sleep(0.01)
            html = f"<div>parallel-{seed}-{uuid.uuid4().hex}</div>"
            doc = _make_custom_doc(html, skeleton_seed=f"parallel-{seed}")
            with lock:
                active["count"] -= 1
            return doc
        yield _llm(brief, seed, user_key)

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", _burst)

    main_mod._top_up_prefetch("", min_fill=4)

    assert pf.size() == 4
    assert active["max"] > 1  # Parallelism observed
    reviewed = sum(len(batch) for batch in review_batches)
    assert reviewed == 4


def test_prefetch_fill_requires_llm_without_offline(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    monkeypatch.delenv("ALLOW_OFFLINE_GENERATION", raising=False)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": None, "has_token": False})
    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    client = TestClient(app)

    r = client.post("/prefetch/fill", json={"brief": "", "count": 5}, headers=API_HEADERS)
    assert r.status_code == 503


def test_prefetch_fill_offline_disallowed_without_llm(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    # Even if offline generation is generally allowed for /generate, /prefetch/fill is LLM-only now
    monkeypatch.setenv("ALLOW_OFFLINE_GENERATION", "1")
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": None, "has_token": False})
    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    client = TestClient(app)

    r = client.post("/prefetch/fill", json={"brief": "", "count": 6}, headers=API_HEADERS)
    assert r.status_code == 503


def test_prefetch_status_endpoint(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod
    pf = isolated_prefetch

    # Seed queue with one doc
    assert pf.enqueue(_make_custom_doc("<div>status-1</div>"))
    client = TestClient(app)
    r = client.get("/prefetch/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("size") == 1
    expected_dir = os.getenv("PREFETCH_DIR")
    assert isinstance(body.get("dir"), str) and body["dir"] == expected_dir


def test_generate_triggers_background_topup_when_low(monkeypatch, isolated_prefetch):
    """When we serve from prefetch and queue size becomes <= low-water, a background top-up should run."""
    from api.main import app
    from api import main as main_mod
    pf = isolated_prefetch

    # Keep tests fast: remove delay and set small targets
    main_mod.PREFETCH_DELAY_MS = 0
    main_mod.PREFETCH_LOW_WATER = 1
    main_mod.PREFETCH_FILL_TO = 3

    # Two items in queue so that after one generate, size=1 triggers top-up to 3
    assert pf.enqueue(_make_custom_doc("<div>T1</div>", skeleton_seed="T1"))
    assert pf.enqueue(_make_custom_doc("<div>T2</div>", skeleton_seed="T2"))

    # Mock LLM as available and generate unique docs for top-up
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "openrouter", "has_token": True})

    def _fake_burst(brief: str, seed: int, user_key=None):
        yield _make_custom_doc(f"<div>topup-{seed}</div>", skeleton_seed=f"topup-{seed}")

    monkeypatch.setattr(main_mod, "llm_generate_page_burst", _fake_burst)
    client = TestClient(app)

    # Allow background top-up in this test (bypass pytest guard)
    monkeypatch.setenv("PREFETCH_TOPUP_ENABLED", "1")
    monkeypatch.setattr(main_mod, "_prefetch_topup_enabled", lambda: True)

    # Consume one item to trigger top-up
    r = client.post("/generate", json={"brief": "", "seed": 111}, headers=API_HEADERS)
    assert r.status_code == 200

    # Background task runs after response; poll briefly until size reaches target or timeout
    deadline = time.time() + 2.0  # up to 2 seconds
    target = main_mod.PREFETCH_FILL_TO
    while time.time() < deadline:
        if pf.size() >= target:
            break
        time.sleep(0.05)
    assert pf.size() >= target
