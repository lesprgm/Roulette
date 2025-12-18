import os
import base64
import pytest
import requests
from unittest.mock import MagicMock
from api import llm_client

def test_get_design_matrix_b64_loads_file(monkeypatch):
    """Verify it loads the real file from the static directory."""
    b64 = llm_client._get_design_matrix_b64()
    assert b64 is not None
    # Decode and check signature
    raw = base64.b64decode(b64)
    assert raw.startswith(b"\xff\xd8")  # JPEG header

def test_call_gemini_for_page_includes_image(monkeypatch):
    """Verify that the multimodal payload includes the image part."""
    # Mock requests.post
    mock_post = MagicMock()
    # Mock a basic successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": '{"kind": "full_page_html", "html": "<div>ok</div>"}'}]
            }
        }]
    }
    mock_post.return_value = mock_response
    monkeypatch.setattr(requests, "post", mock_post)
    
    # Ensure Gemini API keys are set
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm_client, "GEMINI_GENERATION_ENDPOINT", "http://fake.api")
    
    llm_client._call_gemini_for_page("test brief", seed=1)
    
    # Check the call args
    args, kwargs = mock_post.call_args
    body = kwargs["json"]
    parts = body["contents"][0]["parts"]
    
    # Should have a text part AND an image part
    assert any("text" in p for p in parts)
    assert any("inlineData" in p for p in parts)
    
    # Verify image data looks right
    image_part = [p for p in parts if "inlineData" in p][0]
    assert image_part["inlineData"]["mimeType"] == "image/jpeg"
    assert len(image_part["inlineData"]["data"]) > 100

def test_vision_grounding_system_prompt_references_matrix(monkeypatch):
    """Verify the system prompt contains the vision grounding instructions."""
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"candidates": []}
    monkeypatch.setattr(requests, "post", mock_post)
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "fake-key")
    
    llm_client._call_gemini_for_page("test", 1)
    
    body = mock_post.call_args[1]["json"]
    text_part = body["contents"][0]["parts"][0]["text"]
    assert "VISION GROUNDING: DESIGN MATRIX ATTACHED" in text_part
    assert "Professional, Playful, Brutalist, Cozy" in text_part
