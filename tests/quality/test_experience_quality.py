from api.generation.experience_quality import score_experience
from api.generation.semantic_anchors import select_semantic_anchors


def _plan():
    return {
        "semantic_anchors": {
            "material": "concrete",
            "natural_phenomenon": "bioluminescence",
            "cultural_object": "typewriter",
            "system_metaphor": "signal relay",
            "interaction_verb": "excavate",
        },
        "semantic_translation": {
            "material": {
                "visual_role": "concrete slab",
                "interaction_role": "typing cracks the surface",
                "content_role": "buried archive",
                "motion_role": "slow fracture",
            }
        },
        "visitor_role": "signal operator",
        "visitor_goal": "decode a buried transmission",
        "first_interaction": "type into the console",
        "primary_loop": {
            "user_action": "type characters",
            "visible_response": "the concrete slab cracks and bioluminescent light appears",
            "state_change": "message fragments unlock",
            "reward_or_payoff": "the hidden transmission becomes readable",
            "continue_reason": "complete the message",
        },
        "progression_model": "0-100% decoded meter",
        "reset_or_replay": "reset button buries the message again",
        "onboarding_cue": "Start typing to excavate the signal.",
        "mobile_interaction": "tap the input and drag the slab",
    }


def test_semantic_anchors_are_seeded_and_stratified():
    anchors_a = select_semantic_anchors(7, "museum_exhibit:scan_to_discover")
    anchors_b = select_semantic_anchors(7, "museum_exhibit:scan_to_discover")
    assert anchors_a == anchors_b
    assert set(anchors_a) == {
        "material",
        "natural_phenomenon",
        "cultural_object",
        "system_metaphor",
        "interaction_verb",
    }


def test_experience_quality_accepts_stateful_loop():
    html = """
    <!doctype html><html><head><meta name="viewport" content="width=device-width">
    <style>@media(max-width:700px){main{display:block}}</style></head><body>
    <main><h1>Buried Signal Relay</h1>
      <p>Start typing to excavate the signal. Complete the message to unlock it.</p>
      <input id="console" aria-label="typewriter console">
      <button id="reset">Reset</button>
      <div id="meter">Progress 0%</div><div id="slab">concrete bioluminescent archive</div>
    </main>
    <script>
      const state = { progress: 0, unlocked: [] };
      document.getElementById('console').addEventListener('input', (event) => {
        state.progress = Math.min(100, event.target.value.length * 10);
        document.getElementById('meter').textContent = 'Progress ' + state.progress + '%';
        document.getElementById('slab').classList.add('cracked');
      });
      document.getElementById('reset').addEventListener('click', () => {
        state.progress = 0;
        document.getElementById('meter').textContent = 'Progress 0%';
      });
    </script></body></html>
    """
    score = score_experience({"kind": "full_page_html", "html": html}, _plan())
    assert score["passes"]
    assert score["flags"]["meaningful_state_change"]
    assert score["flags"]["interaction_not_decorative"]


def test_experience_quality_rejects_decorative_only_page():
    html = "<!doctype html><html><body><main><h1>Glowing Signal</h1><p>Atmospheric panels only.</p></main></body></html>"
    score = score_experience({"kind": "full_page_html", "html": html}, _plan())
    assert not score["passes"]
    assert "No primary interaction." in score["hard_failures"]
