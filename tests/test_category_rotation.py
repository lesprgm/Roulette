import importlib

import pytest


@pytest.fixture(autouse=True)
def reload_llm_client():
    """Reload api.llm_client for each test to reset module globals."""
    import api.llm_client as llm_client
    importlib.reload(llm_client)
    return llm_client


def test_category_note_cycles_through_all_five(reload_llm_client):
    llm_client = reload_llm_client
    notes = []
    for _ in range(7):  # cycle more than once
        notes.append(llm_client._next_category_note())
    assert len(notes) == 7
    # First five notes should be unique and match order
    assert notes[:5] == [n for _, n in llm_client._CATEGORY_ROTATION_NOTES]
    # Sixth note should repeat first, seventh repeat second
    assert notes[5] == notes[0]
    assert notes[6] == notes[1]


def test_generate_page_injects_category_note(monkeypatch, reload_llm_client):
    llm_client = reload_llm_client

    captured = []

    def fake_openrouter(brief, seed, category_note):
        captured.append(category_note)
        return {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}

    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake")
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", fake_openrouter)

    for _ in range(3):
        out = llm_client.generate_page("", seed=123)
        assert out.get("kind") == "full_page_html"

    assert captured == [n for _, n in llm_client._CATEGORY_ROTATION_NOTES[:3]]
