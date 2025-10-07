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
    if not os.getenv("GROQ_API_KEY"):
        val = _load_key_from_dotenv("GROQ_API_KEY")
        if val and not val.lower().startswith("your_"):
            os.environ["GROQ_API_KEY"] = val
    os.environ.setdefault("FORCE_OPENROUTER_ONLY", "0")

from api.main import app


client = TestClient(app)
API_HEADERS = {"x-api-key": "demo_123"}


def _live_enabled() -> bool:
    flag = os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in {"1", "true", "yes", "on"}
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    return flag and bool(key)


@pytest.mark.skipif(not _live_enabled(), reason="Live LLM tests disabled or Groq API key missing")
def test_groq_live_chat_completion():
    """Directly hit Groq chat completions to verify connectivity and auth."""
    api_key = os.getenv("GROQ_API_KEY").strip()
    model = (os.getenv("GROQ_MODEL") or "meta-llama/llama-4-scout-17b-16e-instruct").strip()

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
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


@pytest.mark.skipif(not _live_enabled(), reason="Live LLM tests disabled or Groq API key missing")
def test_generate_live_groq_integration():
    """End-to-end hit /generate which should call Groq when configured and not forcing OpenRouter."""
    os.environ["FORCE_OPENROUTER_ONLY"] = "0"

    payload = {"brief": "tiny interactive toy", "seed": 54321}
    r = client.post("/generate", json=payload, headers=API_HEADERS)
    assert r.status_code == 200, r.text
    page = r.json()
    assert "error" not in page, page
    if page.get("kind") == "full_page_html":
        assert isinstance(page.get("html"), str) and page["html"].strip()
    else:
        assert "components" in page and isinstance(page["components"], list) and len(page["components"]) >= 1
