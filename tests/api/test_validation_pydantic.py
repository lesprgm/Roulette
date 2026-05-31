from fastapi.testclient import TestClient
from api.main import app


client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}


def test_validate_accepts_ndw_snippet_v1():
    doc = {
        "kind": "ndw_snippet_v1",
        "title": "Test",
        "background": {"style": "background: #000;", "class": "text-white"},
        "css": "#ndw-app{min-height:50vh}",
        "html": "<div id='ndw-app'><h1>Hi</h1></div>",
        "js": "console.log('ok')",
    }
    r = client.post("/validate", json={"page": doc}, headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get("detail", {}).get("valid") is True


def test_validate_accepts_full_page_html():
    doc = {"kind": "full_page_html", "html": "<!doctype html><html><body>Hi</body></html>"}
    r = client.post("/validate", json={"page": doc}, headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get("detail", {}).get("valid") is True
