import json
import pytest
from api import llm_client

def test_extract_completed_objects_from_array():
    # Test 1: Full array at once
    text = '[{"id": 1}, {"id": 2}, {"id": 3}]'
    objs = llm_client._extract_completed_objects_from_array(text)
    assert len(objs) == 3
    assert objs[0]["id"] == 1
    assert objs[2]["id"] == 3

    # Test 2: Partial array (first object complete)
    text = '[{"id": 1}, {"id": 2}, {"id":'
    objs = llm_client._extract_completed_objects_from_array(text)
    assert len(objs) == 2
    assert objs[1]["id"] == 2

    # Test 3: Array with nested objects
    text = '[{"a": {"b": 1}}, {"c": 2}]'
    objs = llm_client._extract_completed_objects_from_array(text)
    assert len(objs) == 2
    assert objs[0]["a"]["b"] == 1

    # Test 4: String with escaped braces
    text = '[{"msg": "hello } world"}, {"id": 1}]'
    objs = llm_client._extract_completed_objects_from_array(text)
    assert len(objs) == 2
    assert objs[0]["msg"] == "hello } world"

def test_generate_page_burst_mocked(monkeypatch):
    import requests
    
    class MockResponse:
        def __init__(self):
            self.status_code = 200
        def iter_lines(self):
            # Simulate Gemini stream chunks
            # Gemini stream is a list of response objects
            def make_chunk(text):
                return json.dumps({
                    "candidates": [{
                        "content": {
                            "parts": [{"text": text}]
                        }
                    }]
                }).encode()

            return [
                make_chunk('[{"kind": "full_page_html", "html": "v1"'),
                make_chunk('}, {"kind": "full_page_html", "html": "v2"'),
                make_chunk('}, {"kind": "full_page_html", "html": "v3"}]')
            ]

    def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(requests, "post", mock_post)
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "fake")
    monkeypatch.setattr(llm_client, "_get_design_matrix_b64", lambda: None)

    results = list(llm_client.generate_page_burst("test", 123))
    
    # Based on our simple mock, we should see the objects as they complete
    # The stream-parser will see:
    # After chunk 1: [{"kind": "t1" -> no objects
    # After chunk 2: [{"kind": "t1"}, {"kind": "t2" -> 1 object (t1)
    # After chunk 3: [{"kind": "t1"}, {"kind": "t2"}, {"kind": "t3"}] -> 3 objects total
    
    assert len(results) == 3
    assert results[0]["kind"] == "full_page_html"
    assert results[0]["html"] == "v1"
    assert results[1]["html"] == "v2"
    assert results[2]["html"] == "v3"
