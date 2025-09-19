from fastapi.testclient import TestClient
from api.main import app

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

