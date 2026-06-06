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


def test_preflight_warns_but_does_not_block_three_without_cleanup_in_iframe_full_page():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script type="module">
          import * as THREE from '/static/vendor/three.module.js';
          const renderer = new THREE.WebGLRenderer();
          renderer.setSize(320, 200);
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is False
    assert any("iframe teardown" in issue.get("message", "") for issue in issues)


def test_preflight_allows_three_full_page_with_cleanup():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script type="module">
          import * as THREE from '/static/vendor/three.module.js';
          const renderer = new THREE.WebGLRenderer();
          NDW.registerCleanup(() => renderer.dispose());
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is False


def test_preflight_blocks_bare_three_import_in_iframe_full_page():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script type="module">
          import * as THREE from 'three';
          const renderer = new THREE.WebGLRenderer();
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    assert any("Unsupported module import 'three'" in issue.get("message", "") for issue in issues)


def test_preflight_warns_cleanup_registered_inside_animation_loop():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script type="module">
          import * as THREE from '/static/vendor/three.module.js';
          function animate() {
            const loopId = requestAnimationFrame(animate);
            NDW.registerCleanup(() => cancelAnimationFrame(loopId));
          }
          animate();
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is False
    assert any("inside a recurring animation loop" in issue.get("message", "") for issue in issues)


def test_preflight_warns_global_listener_leak_in_iframe_full_page():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script>
          window.addEventListener('mousemove', () => {});
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is False


def test_preflight_blocks_direct_missing_element_dereference():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script>
          document.getElementById('missing').addEventListener('click', () => {});
          document.querySelector('.missing-class').classList.add('active');
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    assert any("directly dereferences missing element id 'missing'" in issue.get("message", "") for issue in issues)
    assert any("directly dereferences missing selector '.missing-class'" in issue.get("message", "") for issue in issues)


def test_preflight_allows_optional_missing_element_access_as_warning():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><body>
        <main id="ndw-content"></main>
        <script>
          document.getElementById('missing')?.addEventListener('click', () => {});
        </script>
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is False
    assert any("missing element id 'missing'" in issue.get("message", "") for issue in issues)


def test_preflight_blocks_remote_and_missing_local_assets():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><head>
        <link rel="stylesheet" href="https://example.com/theme.css">
        <link rel="stylesheet" href="/static/design-kit/missing.css">
        </head><body>
        <main id="ndw-content" style="background-image:url('/static/design-kit/overlays/nope.svg')"></main>
        <img src="relative.png" alt="">
        </body></html>""",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    messages = " ".join(issue.get("message", "") for issue in issues)
    assert "Remote link" in messages
    assert "does not exist" in messages
    assert "Relative or unsupported media asset" in messages


def test_preflight_blocks_nested_iframe():
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main id='ndw-content'><iframe src='/x'></iframe></main></body></html>",
    }
    issues = preflight_doc(doc)
    assert has_blocking_issues(issues) is True
    assert any("nested iframes" in issue.get("message", "") for issue in issues)


def test_preflight_warns_heavy_html(monkeypatch):
    import api.preflight as preflight

    monkeypatch.setattr(preflight, "_HTML_WARN_BYTES", 1000)
    monkeypatch.setattr(preflight, "_HTML_BLOCK_BYTES", 3000)
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main id='ndw-content'>" + ("x" * 1200) + "</main></body></html>",
    }

    issues = preflight_doc(doc)

    assert has_blocking_issues(issues) is False
    assert any("Generated HTML is heavy" in issue.get("message", "") for issue in issues)


def test_preflight_blocks_extreme_html_size(monkeypatch):
    import api.preflight as preflight

    monkeypatch.setattr(preflight, "_HTML_WARN_BYTES", 1000)
    monkeypatch.setattr(preflight, "_HTML_BLOCK_BYTES", 1200)
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main id='ndw-content'>" + ("x" * 1400) + "</main></body></html>",
    }

    issues = preflight_doc(doc)

    assert has_blocking_issues(issues) is True
    assert any("Generated HTML is too large" in issue.get("message", "") for issue in issues)


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
