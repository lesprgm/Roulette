from api.generation.activity_quality import score_activity_depth
from api.generation.experience_quality import score_experience
from api.generation.design_quality import score_design_discipline
from api.generation.semantic_anchors import select_semantic_anchors


def _plan():
    return {
        "semantic_anchors": {
            "material": "concrete",
            "natural_phenomenon": "bioluminescence",
            "cultural_object": "typewriter",
            "system_metaphor": "signal relay",
            "interaction_verb": "answer",
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
        "activity_type": "puzzle_box",
        "activity_contract": {
            "activity_type": "puzzle_box",
            "activity_variant": "record_investigation",
            "core_mechanic": "type_commands_or_messages",
            "library_profile": "dom_css_state_machine",
            "activity_goal": "answer prompts and assemble the transmission",
            "required_actions": ["type", "submit", "answer prompt"],
            "required_state": "track progress and unlocked message fragments",
            "payoff": "show the completed signal",
            "boredom_risks": ["slider_only_controls", "buttons_only_toggle_visual_effects"],
            "success_signal": "the visitor sees decoded fragments become a completed signal",
        },
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
        "onboarding_cue": "Start typing to answer the signal.",
        "mobile_interaction": "tap the input and drag the slab",
        "genre_contract": {
            "page_genre": "toy_simulator",
            "copy_density": "low",
            "visual_density": "focused",
            "palette_strategy": "monochrome_accent",
            "motion_language": "playful_elastic",
            "instruction_policy": "one_microcue",
            "chrome_policy": "minimal_functional",
            "focal_rule": "One dominant interactive stage.",
            "copy_budget": "Use labels and one short cue.",
            "palette_roles": {
                "background": "quiet field",
                "surface": "supporting surface",
                "primary_accent": "action accent",
                "text": "readable text",
            },
        },
    }


def test_semantic_anchors_are_seeded_and_stratified():
    anchors_a = select_semantic_anchors(7, "museum_exhibit:scan_to_compare")
    anchors_b = select_semantic_anchors(7, "museum_exhibit:scan_to_compare")
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
      <p>Start typing to answer the signal. Complete the message to unlock it.</p>
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


def test_design_discipline_flags_literal_tutorial_and_visible_artifacts():
    html = """
    <!doctype html><html><body><main>
      <section class="panel"><h2>// Onboarding Instructions</h2>
      <p>Visitor Role: signal operator. Primary Loop: use every dashboard panel.
      Feedback Contract: every slider updates telemetry. TODO undefined null.</p></section>
      <section class="panel badge telemetry">System Status Calibrated</section>
      <section class="panel badge metric">Protocol Registry</section>
      <input type="range"><input type="range"><button>Reset</button><button>Classify</button>
    </main></body></html>
    """
    score = score_design_discipline({"kind": "full_page_html", "html": html}, _plan())
    assert not score["passes"]
    assert "literal_onboarding_section" in score["tags"]
    assert "planning_terms_visible" in score["tags"]
    assert "visible_code_artifact" in score["tags"]
    assert "decorative_dashboard_chrome" in score["tags"]


def test_design_discipline_accepts_restrained_affordance_copy():
    html = """
    <!doctype html><html><body><main>
      <h1>Buried Signal Relay</h1>
      <label for="console">Type an answer</label>
      <input id="console" aria-label="typewriter console">
      <button id="reset">Reset</button>
      <canvas aria-label="cracking concrete signal stage"></canvas>
    </main></body></html>
    """
    score = score_design_discipline({"kind": "full_page_html", "html": html}, _plan())
    assert score["passes"]
    assert score["tags"] == []


def test_activity_quality_flags_slider_only_non_simulation():
    html = """
    <!doctype html><html><body><main>
      <h1>Signal Lab</h1>
      <label>Frequency <input type="range"></label>
      <label>Glow <input type="range"></label>
      <label>Density <input type="range"></label>
      <div id="meter">resonance calibrated</div>
      <script>
        const state = { progress: 0 };
        document.querySelectorAll('input').forEach(input => {
          input.addEventListener('input', () => {
            state.progress += 1;
            document.getElementById('meter').textContent = 'resonance ' + state.progress;
          });
        });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, _plan())
    assert not score["passes"]
    assert "slider_only_activity" in score["tags"]
    assert score["metrics"]["range_control_count"] == 3


def test_activity_quality_accepts_app_like_workflow():
    plan = {
        **_plan(),
        "activity_type": "saas_replica",
        "activity_contract": {
            "activity_type": "saas_replica",
            "activity_variant": "kanban_workspace",
            "core_mechanic": "filter_search_and_select_records",
            "library_profile": "lucide_app_chrome",
            "activity_goal": "filter records and save a selected project",
            "required_actions": ["search", "filter", "select"],
            "required_state": "track selected records and saved shortlist",
            "payoff": "saved project shortlist",
            "boredom_risks": ["slider_only_controls", "fake_metrics_without_task"],
            "success_signal": "selected records become a saved shortlist",
        },
        "task_contract": {
            "format": "kanban_workspace",
            "user_goal": "Filter records and save a project shortlist.",
            "domain_objects": ["records", "kanban", "tasks", "project cards"],
            "state_variables": ["selected", "records", "saved"],
            "controls": [
                {"label": "Search records", "type": "input", "must_change_state": ["records"]},
                {"label": "Filter active", "type": "button", "must_change_state": ["selected"]},
                {"label": "Save shortlist", "type": "button", "must_change_state": ["saved"]},
            ],
            "completion_condition": "saved shortlist result",
            "error_states": ["empty records"],
            "allowed_patterns": ["search", "filter", "select", "save"],
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Project Kanban Workspace</h1>
      <input id="search" placeholder="Search records">
      <button id="filter">Filter active</button>
      <button id="save">Save shortlist</button>
      <section id="records">Customer records, kanban columns, tasks, and project cards</section>
      <output id="result">0 selected</output>
      <script>
        const state = { selected: [], records: ['A', 'B'], saved: false };
        document.getElementById('filter').addEventListener('click', () => {
          state.selected = state.records;
          document.getElementById('result').textContent = state.selected.length + ' selected';
        });
        document.getElementById('save').addEventListener('click', () => {
          state.saved = true;
          document.getElementById('result').textContent = 'Saved shortlist result';
        });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert score["passes"]
    assert score["tags"] == []


def test_activity_quality_accepts_recognizable_snake_game_loop():
    plan = {
        **_plan(),
        "activity_type": "snake_game",
        "activity_contract": {
            "activity_type": "snake_game",
            "activity_variant": "snake_grid",
            "core_mechanic": "snake_collect_and_grow",
            "library_profile": "ndw_canvas_game_loop",
            "activity_goal": "steer the snake to collect food and grow",
            "required_actions": ["steer", "collect", "avoid collision"],
            "required_state": "track snake body, food, score, and collision state",
            "payoff": "score increases when food is collected",
            "boredom_risks": ["slider_only_controls", "buttons_only_toggle_visual_effects"],
            "success_signal": "the snake grows and score changes",
        },
        "task_contract": {
            "format": "snake_game",
            "user_goal": "Steer the snake, collect food, grow, and avoid collision.",
            "domain_objects": ["snake", "food", "grid", "score"],
            "state_variables": ["snake", "food", "score", "alive"],
            "controls": [
                {"label": "Arrow keys", "type": "keyboard", "must_change_state": ["snake", "score"]},
                {"label": "Restart", "type": "button", "must_change_state": ["score", "alive"]},
            ],
            "completion_condition": "score changes when food is collected",
            "error_states": ["collision"],
            "allowed_patterns": ["canvas game loop", "keyboard controls", "restart"],
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Snake Grid</h1>
      <p>Use arrow keys to steer the snake, collect food, grow, and avoid collision.</p>
      <canvas id="board" aria-label="snake game grid"></canvas>
      <output id="score">Score 0</output>
      <button id="restart">Restart</button>
      <script>
        const state = { snake: [{x: 4, y: 4}], food: {x: 8, y: 8}, score: 0, alive: true };
        document.addEventListener('keydown', () => {
          state.score += 1;
          document.getElementById('score').textContent = 'Score ' + state.score;
        });
        document.getElementById('restart').addEventListener('click', () => {
          state.score = 0;
          document.getElementById('score').textContent = 'Score 0';
        });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert score["passes"]
    assert score["tags"] == []


def test_activity_quality_accepts_non_default_game_variant():
    plan = {
        **_plan(),
        "activity_type": "microgame",
        "activity_contract": {
            "activity_type": "microgame",
            "activity_variant": "breakout_paddle",
            "core_mechanic": "breakout_paddle_bounce",
            "library_profile": "ndw_canvas_game_loop",
            "activity_goal": "move the paddle to bounce the ball and break bricks",
            "required_actions": ["move paddle", "bounce ball", "break bricks"],
            "required_state": "track ball, paddle, bricks, lives, and score",
            "payoff": "score increases as bricks break",
            "boredom_risks": ["slider_only_controls"],
            "success_signal": "bricks disappear and score changes",
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Breakout Paddle</h1>
      <canvas id="board" aria-label="breakout paddle brick game"></canvas>
      <output id="score">Score 0</output><output id="lives">Lives 3</output>
      <button id="restart">Restart</button>
      <script>
        const state = { ball: {x: 40, y: 40}, paddle: 80, bricks: [1,2,3], score: 0, lives: 3 };
        document.addEventListener('keydown', () => {
          state.score += 10;
          state.bricks.pop();
          document.getElementById('score').textContent = 'Score ' + state.score;
        });
        document.getElementById('restart').addEventListener('click', () => {
          state.score = 0;
          document.getElementById('score').textContent = 'Score 0';
        });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert score["passes"]
    assert "activity_variant_mismatch" not in score["tags"]


def test_activity_quality_flags_poetic_renaming_of_known_format():
    plan = {
        **_plan(),
        "activity_type": "snake_game",
        "activity_contract": {
            "activity_type": "snake_game",
            "activity_variant": "snake_grid",
            "core_mechanic": "snake_collect_and_grow",
            "library_profile": "ndw_canvas_game_loop",
            "activity_goal": "steer the snake to collect food and grow",
            "required_actions": ["steer", "collect", "avoid collision"],
            "required_state": "track snake body, food, score, and collision state",
            "payoff": "score increases when food is collected",
            "boredom_risks": ["slider_only_controls"],
            "success_signal": "the snake grows and score changes",
        },
        "semantic_anchors": {
            "material": "concrete",
            "natural_phenomenon": "fog bank",
            "cultural_object": "radio dial",
            "system_metaphor": "translation engine",
            "interaction_verb": "steer",
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Echo Migration Protocol</h1>
      <p>Follow the hidden archive signal through the concrete fog bank and radio dial.</p>
      <button id="go">Decode</button><output id="result">Transmission locked</output>
      <script>
        const state = { score: 0, unlocked: false };
        document.getElementById('go').addEventListener('click', () => {
          state.unlocked = true;
          document.getElementById('result').textContent = 'Hidden signal archive revealed';
        });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert not score["passes"]
    assert "activity_variant_mismatch" in score["tags"]
    assert "poetic_renaming_of_known_format" in score["tags"]
    assert "semantic_anchor_overrides_activity" in score["tags"]


def test_activity_quality_flags_hidden_reveal_loop_when_format_needs_concrete_activity():
    plan = {
        **_plan(),
        "activity_type": "microgame",
        "activity_contract": {
            "activity_type": "microgame",
            "activity_variant": "breakout_paddle",
            "core_mechanic": "breakout_paddle_bounce",
            "library_profile": "ndw_canvas_game_loop",
            "activity_goal": "move the paddle to bounce the ball and break bricks",
            "required_actions": ["move paddle", "bounce ball", "break bricks"],
            "required_state": "track ball, paddle, bricks, lives, and score",
            "payoff": "score increases as bricks break",
            "boredom_risks": ["slider_only_controls"],
            "success_signal": "bricks disappear and score changes",
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Breakout Paddle</h1>
      <p>Reveal the hidden archive, decode each hidden fragment, unlock the signal, and reveal the transmission.</p>
      <canvas aria-label="breakout paddle brick game"></canvas>
      <output>Score 0</output><button>Restart</button>
      <script>
        const state = { ball: {}, paddle: 0, bricks: [1], score: 0 };
        document.querySelector('button').addEventListener('click', () => { state.score = 0; });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert "abstract_hidden_reveal_loop" in score["tags"]


def test_activity_quality_flags_missing_task_model_controls():
    plan = {
        **_plan(),
        "activity_type": "saas_replica",
        "activity_contract": {
            "activity_type": "saas_replica",
            "activity_variant": "invoice_builder",
            "core_mechanic": "configure_product_or_system",
            "library_profile": "lucide_app_chrome",
            "activity_goal": "create a valid invoice",
            "required_actions": ["add line item", "edit total", "export"],
            "required_state": "track items subtotal total export readiness",
            "payoff": "export-ready invoice preview",
            "boredom_risks": ["slider_only_controls"],
            "success_signal": "invoice total and export state update",
        },
        "task_contract": {
            "format": "invoice_builder",
            "user_goal": "Create an invoice preview",
            "domain_objects": ["client", "line_item", "total"],
            "state_variables": ["items", "subtotal", "total", "exportReady"],
            "controls": [
                {"label": "Add line item", "type": "button", "must_change_state": ["items", "subtotal", "total"]},
                {"label": "Export", "type": "button", "must_change_state": ["exportReady"]},
            ],
            "completion_condition": "invoice preview is valid and export is enabled",
            "error_states": ["missing client"],
            "allowed_patterns": ["form", "editable_table", "summary_card"],
            "visual_budget": {"ambient_background": "none", "motion_only_for": ["recalculation"]},
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Invoice Builder</h1>
      <p>Client line item total result preview.</p>
      <section>Static invoice mockup only.</section>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert not score["passes"]
    assert "planned_controls_not_rendered" in score["tags"]
    assert score["metrics"]["task_contract_present"] is True
    assert score["metrics"]["task_control_count"] == 2


def test_activity_quality_accepts_product_storefront_contract():
    plan = {
        **_plan(),
        "activity_type": "product_or_storefront",
        "activity_contract": {
            "activity_type": "product_or_storefront",
            "activity_variant": "sneaker_drop_page",
            "core_mechanic": "configure_product_or_system",
            "library_profile": "gsap_state_transition",
            "activity_goal": "choose a sneaker size and reserve a drop",
            "required_actions": ["choose size", "add to cart", "checkout"],
            "required_state": "track selected variant, cart, total, and checkout readiness",
            "payoff": "cart drawer and reservation summary",
            "boredom_risks": ["no_goal_or_payoff"],
            "success_signal": "selected sneaker appears in cart with price and size",
        },
        "task_contract": {
            "format": "sneaker_drop_page",
            "user_goal": "Choose a sneaker size and reserve the limited drop.",
            "domain_objects": ["product", "price", "variant", "cart", "checkout"],
            "state_variables": ["selectedVariant", "quantity", "cartItems", "total", "checkoutReady"],
            "controls": [
                {"label": "Choose size", "type": "button", "must_change_state": ["selectedVariant"]},
                {"label": "Add to cart", "type": "button", "must_change_state": ["cartItems", "total"]},
            ],
            "completion_condition": "selected product option appears in checkout summary",
            "error_states": ["missing size"],
            "allowed_patterns": ["product_hero", "price_or_plan", "variant_selector", "cart_or_checkout_summary"],
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Sneaker Drop Page</h1>
      <section aria-label="product hero">Limited sneaker product, price $120, benefits, specs, stock timer</section>
      <button id="size">Choose size 10</button><button id="cart">Add to cart</button>
      <output id="summary">Cart total $0</output>
      <script>
        const state = { selectedVariant: '', quantity: 1, cartItems: [], total: 0, checkoutReady: false };
        document.getElementById('size').addEventListener('click', () => {
          state.selectedVariant = 'Size 10';
          document.getElementById('summary').textContent = 'Selected size 10';
        });
        document.getElementById('cart').addEventListener('click', () => {
          state.cartItems.push('sneaker');
          state.total = 120;
          state.checkoutReady = true;
          document.getElementById('summary').textContent = 'Checkout summary: sneaker size 10 total $120';
        });
      </script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert score["passes"]
    assert "product_contract_missing" not in score["tags"]


def test_activity_quality_flags_blank_product_storefront():
    plan = {
        **_plan(),
        "activity_type": "product_or_storefront",
        "activity_contract": {
            "activity_type": "product_or_storefront",
            "activity_variant": "product_detail_page",
        },
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Product Detail</h1>
      <p>Empty placeholder. Start from scratch.</p>
      <button>Configure</button>
      <script>const state = { selectedVariant: '', cartItems: [] }; document.querySelector('button').addEventListener('click', () => state.selectedVariant = 'x');</script>
    </main></body></html>
    """
    score = score_activity_depth({"kind": "full_page_html", "html": html}, plan)
    assert not score["passes"]
    assert "blank_stage_first_paint" in score["tags"]
    assert "product_payoff_missing" in score["tags"]


def test_design_discipline_flags_generic_ai_copy_and_weak_action():
    html = """
    <!doctype html><html><body><main>
      <h1>Signal Data Schematic System</h1>
      <p>Initiate protocol calibration terminal drift manifest.</p>
      <button>Pulse</button>
    </main></body></html>
    """
    score = score_design_discipline({"kind": "full_page_html", "html": html}, _plan())
    assert not score["passes"]
    assert "generic_ai_title_or_copy" in score["tags"]
    assert "weak_primary_action" in score["tags"]


def test_experience_quality_accepts_arrow_key_game_cue():
    plan = {
        **_plan(),
        "first_interaction": "Use arrow keys to steer the snake.",
        "onboarding_cue": "Use arrow keys to steer.",
    }
    html = """
    <!doctype html><html><body><main>
      <h1>Snake</h1>
      <p>Use arrow keys to steer. Avoid walls and collect food.</p>
      <canvas aria-label="snake board"></canvas>
      <button>Restart</button>
      <script>
        const state = { score: 0, selected: false };
        window.addEventListener('keydown', () => {
          state.score += 1;
          document.querySelector('button').innerText = 'Restart score ' + state.score;
        });
        requestAnimationFrame(() => {});
      </script>
    </main></body></html>
    """
    score = score_experience({"kind": "full_page_html", "html": html}, plan)
    assert score["flags"]["first_interaction_visible"]
    assert not score["hard_failures"]


def test_design_discipline_flags_host_brand_leakage():
    html = """
    <!doctype html><html><body><main>
      <h1>Roulette Case Sorter</h1>
      <p>Built on NDW runtime for non-deterministic website output.</p>
      <button>Save</button>
    </main></body></html>
    """
    score = score_design_discipline({"kind": "full_page_html", "html": html}, _plan())
    assert "host_brand_leakage" in score["tags"]
