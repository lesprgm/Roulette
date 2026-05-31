import pytest
from api import dedupe

def test_skeletonize_strips_content():
    html = """
    <div class="p-6 bg-slate-100">
        <!-- Comment -->
        <h1 id="title" style="color:red">Hello World</h1>
        <p class="mt-2 text-slate-700">This is a test paragraph.</p>
        <script>console.log('hi');</script>
        <style>.foo { color: blue; }</style>
    </div>
    """
    skeleton = dedupe._skeletonize(html)
    
    # Structural elements should remain
    assert "<div" in skeleton
    assert 'class="p-6bg-slate-100"' in skeleton  # Note: _WS_RE.sub("", html) removes all spaces inside tags too if not careful
    assert "<h1" in skeleton
    assert "<p" in skeleton
    
    # Non-structural content should be gone
    assert "Comment" not in skeleton
    assert "Hello World" not in skeleton
    assert "paragraph" not in skeleton
    assert "console.log" not in skeleton
    assert ".foo" not in skeleton

def test_signature_identical_for_layout_twins():
    doc1 = {
        "kind": "full_page_html",
        "html": '<div class="card"><h1>Title 1</h1><p>Text 1</p></div>'
    }
    doc2 = {
        "kind": "full_page_html",
        "html": '<div class="card"><h1>Different Title</h1><p>Other text</p></div>'
    }
    
    sig1 = dedupe.signature_for_doc(doc1)
    sig2 = dedupe.signature_for_doc(doc2)
    
    assert sig1 == sig2
    assert len(sig1) == 64 # SHA-256

def test_signature_different_for_distinct_layouts():
    doc1 = {
        "kind": "full_page_html",
        "html": '<div class="card"><h1>Title</h1></div>'
    }
    doc2 = {
        "kind": "full_page_html",
        "html": '<section class="hero"><h1>Title</h1></section>'
    }
    
    sig1 = dedupe.signature_for_doc(doc1)
    sig2 = dedupe.signature_for_doc(doc2)
    
    assert sig1 != sig2

def test_signature_handles_snippets():
    snippet = {
        "kind": "ndw_snippet_v1",
        "html": '<button class="btn">Click</button>',
        "css": ".btn { color: red; }",
        "js": "alert(1)"
    }
    sig = dedupe.signature_for_doc(snippet)
    assert sig is not None
    assert len(sig) == 64
