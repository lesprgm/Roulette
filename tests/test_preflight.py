from fastapi.testclient import TestClient

from api.main import app
from api.preflight import has_blocking_issues, preflight_doc


client = TestClient(app)


def test_preflight_blocks_duplicate_ids():
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><div id='dup'></div><section id='dup'></section></body></html>",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    assert any("Duplicate id 'dup'" in issue.get("message", "") for issue in issues)


def test_preflight_blocks_module_imports_in_snippets():
    doc = {
        "kind": "ndw_snippet_v1",
        "html": "<div id='ndw-app'></div>",
        "js": "import * as THREE from 'three';",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    assert any("Module import" in issue.get("message", "") for issue in issues)


def test_preflight_requires_cleanup_for_three_full_page():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script type="module">
          import * as THREE from 'three';
          const renderer = new THREE.WebGLRenderer();
          renderer.setSize(320, 200);
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    assert any("register teardown" in issue.get("message", "") for issue in issues)


def test_preflight_allows_three_full_page_with_cleanup():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script type="module">
          import * as THREE from 'three';
          const renderer = new THREE.WebGLRenderer();
          NDW.registerCleanup(() => renderer.dispose());
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is False


def test_validate_endpoint_includes_preflight_failures():
    page = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><div id='dup'></div><div id='dup'></div></body></html>",
    }
    resp = client.post("/validate", json={"page": page})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["valid"] is False
    assert any("Duplicate id 'dup'" in item.get("message", "") for item in detail.get("errors", []))
