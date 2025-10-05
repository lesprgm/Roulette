import json
import os
import time
import importlib

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


def _make_custom_doc(html: str, height: int = 200):
    return {
        "components": [
            {
                "id": f"custom-{abs(hash(html))%1_000_000}",
                "type": "custom",
                "props": {"html": html, "height": height},
            }
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
    }


def test_prefetch_enqueue_dequeue_basic(isolated_prefetch):
    pf = isolated_prefetch
    assert pf.size() == 0
    d1 = _make_custom_doc("<div>A</div>")
    d2 = _make_custom_doc("<div>B</div>")
    assert pf.enqueue(d1) is True
    assert pf.enqueue(d2) is True
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

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})

    def _fake_llm(brief: str, seed: int):
        return _make_custom_doc(f"<div>seed-{seed}</div>")

    monkeypatch.setattr(main_mod, "llm_generate_page", _fake_llm)
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

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})

    def _same_doc(brief: str, seed: int):
        return _make_custom_doc("<div>same</div>")

    monkeypatch.setattr(main_mod, "llm_generate_page", _same_doc)
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

    docA = _make_custom_doc("<div>prefetched-A</div>")
    docB = _make_custom_doc("<div>prefetched-B</div>")
    assert pf.enqueue(docA) is True
    assert pf.enqueue(docB) is True

    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})
    sentinel = _make_custom_doc("<div>LLM-Fallback</div>")
    monkeypatch.setattr(main_mod, "llm_generate_page", lambda brief, seed: sentinel)
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


def test_prefetch_fill_requires_llm_without_offline(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    monkeypatch.delenv("ALLOW_OFFLINE_GENERATION", raising=False)
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": False})
    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    client = TestClient(app)

    r = client.post("/prefetch/fill", json={"brief": "", "count": 5}, headers=API_HEADERS)
    assert r.status_code == 503


def test_prefetch_fill_offline_disallowed_without_llm(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    # Even if offline generation is generally allowed for /generate, /prefetch/fill is LLM-only now
    monkeypatch.setenv("ALLOW_OFFLINE_GENERATION", "1")
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": False})
    monkeypatch.setattr(main_mod, "llm_generate_page", None)
    client = TestClient(app)

    r = client.post("/prefetch/fill", json={"brief": "", "count": 6}, headers=API_HEADERS)
    assert r.status_code == 503


def test_prefetch_status_endpoint(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod
    pf = isolated_prefetch

    # Seed queue with one doc
    assert pf.enqueue(_make_custom_doc("<div>status-1</div>")) is True
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
    assert pf.enqueue(_make_custom_doc("<div>T1</div>")) is True
    assert pf.enqueue(_make_custom_doc("<div>T2</div>")) is True

    # Mock LLM as available and generate unique docs for top-up
    monkeypatch.setattr(main_mod, "llm_status", lambda: {"provider": "gemini", "has_token": True})

    def _fake_llm(brief: str, seed: int):
        return _make_custom_doc(f"<div>topup-{seed}</div>")

    monkeypatch.setattr(main_mod, "llm_generate_page", _fake_llm)
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
