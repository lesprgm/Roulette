from api.quality import score_page_doc


def test_quality_scoring_penalizes_centered_card_shell():
    doc = {
        "kind": "full_page_html",
        "html": "<!doctype html><html><body><main class='min-h-screen flex items-center justify-center'><section class='mx-auto max-w-md rounded-3xl shadow-xl'>Card</section></main></body></html>",
    }
    quality = score_page_doc(doc)
    assert quality["flags"]["centered_card"] is True
    assert quality["score"] < 70


def test_quality_scoring_rewards_motion_and_local_design_kit():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><head><link rel="stylesheet" href="/static/design-kit/fonts.css"></head>
        <body style="background:linear-gradient(#020617,#1d4ed8)">
        <main id="ndw-content"><section>Stage</section><section>Controls</section>
        <img alt="" src="/static/design-kit/overlays/orbital-dots.svg"/>
        <script>requestAnimationFrame(()=>{});window.addEventListener('pointermove',()=>{});</script>
        </main></body></html>""",
    }
    quality = score_page_doc(doc)
    assert quality["flags"]["motion"] is True
    assert quality["flags"]["design_kit"] is True
    assert quality["score"] >= 70
