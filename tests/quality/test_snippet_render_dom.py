from api import llm_client
from api.preflight import has_blocking_issues, preflight_doc


def test_snippet_preflight_blocks_external_script_src():
    html = """
    <div id='ndw-app'>
      <h1>Hi</h1>
      <script src='https://bad.example.com/x.js'></script>
      <script>window.__ran = (window.__ran||0)+1;</script>
    </div>
    """
    snippet = {
        "kind": "ndw_snippet_v1",
        "html": html,
        "css": "#ndw-app{min-height:50vh}",
        "js": "window.__ran = (window.__ran||0)+1;",
    }

    data = llm_client._normalize_doc(snippet)
    issues = preflight_doc(data)

    assert data.get("kind") == "ndw_snippet_v1"
    assert "window.__ran" in data.get("html", "")
    assert isinstance(data.get("css"), str)
    assert isinstance(data.get("js"), str)
    assert has_blocking_issues(issues)
    assert any("Remote script" in issue["message"] for issue in issues)
