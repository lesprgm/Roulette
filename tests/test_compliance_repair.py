from __future__ import annotations

from typing import Any, Dict, List

import api.llm_client as llm_client


class _FakeResp:
    status_code = 200
    text = "{}"

    def json(self) -> Dict[str, Any]:
        return {}


def test_gemini_batch_review_repairs_unparsable_response(monkeypatch):
    docs = [{"kind": "full_page_html", "html": "<html></html>"}]

    monkeypatch.setattr(llm_client.requests, "post", lambda *args, **kwargs: _FakeResp())
    monkeypatch.setattr(
        llm_client,
        "_extract_gemini_text",
        lambda payload: '{"results":[{"index":0,"ok":true,"issues":[],"notes":"ok"}XXX',  # malformed
    )
    monkeypatch.setattr(llm_client, "_repair_json_loose", lambda text: text)

    called: Dict[str, Any] = {}

    def _repair(raw_text: str, schema: Dict[str, Any], *, name: str, label: str, max_tokens: int):
        called["raw"] = raw_text
        return {
            "results": [
                {"index": 0, "ok": True, "issues": [], "notes": "ok", "doc": None}
            ]
        }

    monkeypatch.setattr(llm_client, "_openrouter_repair_to_schema", _repair)

    out = llm_client._call_gemini_review_batch(docs)
    assert isinstance(out, list)
    assert out[0]["ok"] is True
    assert "raw" in called


def test_gemini_single_review_repairs_unparsable_response(monkeypatch):
    doc = {"kind": "full_page_html", "html": "<html></html>"}

    monkeypatch.setattr(llm_client.requests, "post", lambda *args, **kwargs: _FakeResp())
    monkeypatch.setattr(llm_client, "_gemini_review_active", lambda: True)
    monkeypatch.setattr(
        llm_client,
        "_extract_gemini_text",
        lambda payload: '{"ok":true,"issues":[],"notes":"ok"XXX',  # malformed
    )
    monkeypatch.setattr(llm_client, "_repair_json_loose", lambda text: text)

    called: Dict[str, Any] = {}

    def _repair(raw_text: str, schema: Dict[str, Any], *, name: str, label: str, max_tokens: int):
        called["raw"] = raw_text
        return {"ok": True, "issues": [], "notes": "ok", "doc": None}

    monkeypatch.setattr(llm_client, "_openrouter_repair_to_schema", _repair)

    out = llm_client._call_gemini_review(doc, "", "")
    assert isinstance(out, dict)
    assert out.get("ok") is True
    assert "raw" in called
