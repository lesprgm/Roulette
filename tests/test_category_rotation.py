import importlib

import pytest


@pytest.fixture(autouse=True)
def reload_llm_client():
    """Reload api.llm_client for each test to reset module globals."""
    import api.llm_client as llm_client
    importlib.reload(llm_client)
    return llm_client


def test_category_note_cycles_per_user(reload_llm_client):
    llm_client = reload_llm_client
    notes = []
    for _ in range(7):  # cycle more than once
        notes.append(llm_client._next_category_note("user-a"))
    assert len(notes) == 7
    # First five notes should be unique and match order
    assert notes[:5] == [n for _, n in llm_client._CATEGORY_ROTATION_NOTES]
    # Sixth note should repeat first, seventh repeat second
    assert notes[5] == notes[0]
    assert notes[6] == notes[1]
    # A different user should start from the first category again
    other_notes = [llm_client._next_category_note("user-b") for _ in range(2)]
    assert other_notes == [n for _, n in llm_client._CATEGORY_ROTATION_NOTES[:2]]
    # Global fallback still works
    assert llm_client._next_category_note() in [n for _, n in llm_client._CATEGORY_ROTATION_NOTES]


def test_generate_page_injects_category_note(monkeypatch, reload_llm_client):
    llm_client = reload_llm_client

    captured = []

    def fake_openrouter(brief, seed, category_note):
        captured.append(category_note)
        return {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}

    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake")
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", fake_openrouter)

    for _ in range(3):
        out = llm_client.generate_page("", seed=123, user_key="user-c")
        assert out.get("kind") == "full_page_html"

    assert captured == [n for _, n in llm_client._CATEGORY_ROTATION_NOTES[:3]]


def test_generate_page_maintains_separate_cycles(monkeypatch, reload_llm_client):
    llm_client = reload_llm_client
    captured = []

    def fake_openrouter(brief, seed, category_note):
        captured.append(category_note)
        return {"kind": "full_page_html", "html": "<!doctype html><html><body>OK</body></html>"}

    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "fake")
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client, "_call_openrouter_for_page", fake_openrouter)

    llm_client.generate_page("", seed=1, user_key="alpha")
    llm_client.generate_page("", seed=2, user_key="alpha")
    llm_client.generate_page("", seed=3, user_key="beta")

    expected_notes = [
        llm_client._CATEGORY_ROTATION_NOTES[0][1],
        llm_client._CATEGORY_ROTATION_NOTES[1][1],
        llm_client._CATEGORY_ROTATION_NOTES[0][1],
    ]
    assert captured == expected_notes
