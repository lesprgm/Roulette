import os
import json
import requests
import pytest

from fastapi.testclient import TestClient


def _load_key_from_dotenv(key_name: str) -> str:
    """Load a single key from .env if present, without requiring python-dotenv."""
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" not in s:
                    continue
                k, v = s.split("=", 1)
                if k.strip() == key_name:
                    return v.strip()
    except Exception:
        pass
    return ""


def _live_flag() -> bool:
    return os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}


if _live_flag():
    # If key not exported, attempt to source from .env for live tests
    if not os.getenv("OPENROUTER_API_KEY"):
        val = _load_key_from_dotenv("OPENROUTER_API_KEY")
        if val and val != "your_openrouter_api_key_here":
            os.environ["OPENROUTER_API_KEY"] = val

# Import app after potential env setup (only happens during live run)
from api.main import app


client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}


def _live_enabled() -> bool:
    flag = os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    return flag and key and key != "your_openrouter_api_key_here"


@pytest.mark.skipif(not _live_enabled(), reason="Live LLM tests disabled or API key missing")
def test_openrouter_live_chat_completion():
    """Directly hit OpenRouter chat completions to verify connectivity and auth."""
    api_key = os.getenv("OPENROUTER_API_KEY").strip()
    model = (os.getenv("OPENROUTER_MODEL") or "google/gemma-3n-e2b-it:free").strip()

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "non-deterministic-website-tests",
        },
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Reply with a short JSON object: {\"ok\": true}",
                    }
                ],
                "temperature": 1.1,
                "max_tokens": 64,
            }
        ),
        timeout=20,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, dict) and "choices" in data and data["choices"], data
    content = data["choices"][0]["message"]["content"]
    assert isinstance(content, str) and len(content) > 0


@pytest.mark.skipif(not _live_enabled(), reason="Live LLM tests disabled or API key missing")
def test_generate_live_openrouter_integration():
    """End-to-end hit /generate which should call OpenRouter when configured."""
    payload = {"brief": "tiny interactive toy", "seed": 12345}
    r = client.post("/generate", json=payload, headers=API_HEADERS)
    assert r.status_code == 200, r.text
    page = r.json()
    # Should be one of the accepted shapes (normalized by backend) and not an error
    assert "error" not in page, page
    kind = page.get("kind")
    if kind == "full_page_html":
        assert isinstance(page.get("html"), str) and page["html"].strip()
    elif kind == "ndw_snippet_v1":
        has_html = isinstance(page.get("html"), str) and page["html"].strip()
        has_js = isinstance(page.get("js"), str) and page["js"].strip()
        assert has_html or has_js
        assert isinstance(page.get("css"), str) and page["css"].strip()
    else:
        assert "components" in page and isinstance(page["components"], list) and len(page["components"]) >= 1
