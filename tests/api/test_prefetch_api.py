
import importlib
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

@pytest.fixture()
def isolated_queue(monkeypatch, tmp_path):
    pf_dir = tmp_path / "pfq"
    premium_pf_dir = tmp_path / "premium-pfq"
    seen_file = tmp_path / "seen.json"
    monkeypatch.setenv("PREFETCH_DIR", str(pf_dir))
    monkeypatch.setenv("PREMIUM_PREFETCH_DIR", str(premium_pf_dir))
    monkeypatch.setenv("DEDUPE_RECENT_FILE", str(seen_file))

    from api import prefetch as pf
    importlib.reload(pf)

    from api import main as main_mod
    monkeypatch.setattr(main_mod, "prefetch", pf)
    return pf


def _make_doc(title: str = "Test Page"):
    return {
        "title": title,
        "category": "unit-test",
        "vibe": "testing",
        "kind": "full_page_html",
        "html": (
            f"<!doctype html><html><head><title>{title}</title></head>"
            f"<body><main id='ndw-content' data-region><h1>{title}</h1>"
            "<button id='play'>Play</button><script>document.getElementById('play')?.addEventListener('click',()=>{});</script>"
            "</main></body></html>"
        ),
    }

def test_prefetch_previews_empty_or_populated(isolated_queue):
    """Test that previews endpoint returns a list (may be empty or populated)."""
    pf = isolated_queue
    assert pf.enqueue(_make_doc("Preview Test"), lane="premium")
    response = client.get("/api/prefetch/previews")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        assert "id" in item
        assert "title" in item
        assert "category" in item
        assert "vibe" in item
        assert "created_at" in item

def test_prefetch_entry_custom_flow(isolated_queue):
    """Manually enqueue a record and verify we can retrieve it."""
    pf = isolated_queue
    doc = _make_doc("Entry Test")
    assert pf.enqueue(doc, lane="premium")

    resp = client.get("/api/prefetch/previews")
    assert resp.status_code == 200
    previews = resp.json()
    
    found = None
    for p in previews:
        if p.get("title") == "Entry Test":
            found = p
            break
    assert found, "Inserted queue item not found in previews"

    resp_detail = client.get(f"/api/prefetch/{found['id']}")
    assert resp_detail.status_code == 200
    full_doc = resp_detail.json()
    assert full_doc["title"] == "Entry Test"
    assert full_doc["category"] == "unit-test"


def test_prefetch_entry_increments_counter_on_serve(monkeypatch, isolated_queue):
    pf = isolated_queue
    assert pf.enqueue(_make_doc("Counter Test"), lane="premium")

    from api import main as main_mod

    counts = []
    monkeypatch.setattr(main_mod.counter, "increment", lambda n=1: counts.append(n) or 1)

    previews = client.get("/api/prefetch/previews").json()
    item = next(p for p in previews if p.get("title") == "Counter Test")
    resp_detail = client.get(f"/api/prefetch/{item['id']}")
    assert resp_detail.status_code == 200
    assert counts == [1]


def test_premium_previews_endpoint_returns_premium_lane(isolated_queue):
    pf = isolated_queue
    assert pf.enqueue(_make_doc("Fast Preview"), lane="fast")
    assert pf.enqueue(_make_doc("Premium Preview"), lane="premium")

    response = client.get("/api/premium/previews")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item.get("title") == "Premium Preview" for item in data)
    assert all(item.get("title") != "Fast Preview" for item in data)


def test_prefetch_entry_not_found(isolated_queue):
    response = client.get("/api/prefetch/file:does-not-exist.json")
    assert response.status_code == 404
