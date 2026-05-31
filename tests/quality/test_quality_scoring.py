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


def test_quality_scoring_ignores_iframe_cleanup_risks_but_keeps_accessibility_risk():
    doc = {
        "kind": "full_page_html",
        "html": """<!doctype html><html><head><link rel="stylesheet" href="/static/design-kit/fonts.css"></head>
        <body style="background:linear-gradient(#020617,#1d4ed8)">
        <main id="ndw-content"><section>Stage</section><section>Controls</section>
        <img alt="" src="/static/design-kit/overlays/contour-lines.svg"/>
        <div id="dial" style="cursor:grab"></div>
        <script type="module">
          import * as THREE from 'three';
          function animate() {
            const loopId = requestAnimationFrame(animate);
            NDW.registerCleanup(() => cancelAnimationFrame(loopId));
          }
          animate();
          window.addEventListener('mousemove',()=>{});
          window.addEventListener('touchstart',()=>{});
          document.getElementById('dial')?.addEventListener('mousedown',()=>{});
          document.getElementById('dial')?.addEventListener('touchstart',()=>{});
        </script>
        </main></body></html>""",
    }
    quality = score_page_doc(doc)
    assert quality["flags"]["loop_cleanup_risk"] is False
    assert quality["flags"]["listener_cleanup_risk"] is False
    assert quality["flags"]["accessibility_risk"] is True


def test_quality_scoring_accepts_layered_fullscreen_div_stage():
    layers = "\n".join(
        f"<div class='artifact absolute' style='left:{idx * 8}%;top:{idx * 6}%;'>Artifact layer {idx}</div>"
        for idx in range(8)
    )
    doc = {
        "kind": "full_page_html",
        "html": f"""<!doctype html><html><head><link rel="stylesheet" href="/static/design-kit/fonts.css"></head>
        <body style="background:radial-gradient(circle,#fdba74,#fff7ed)">
        <div id="ndw-content" class="relative flex items-center justify-center" style="height:100vh;width:100vw;background-image:url('/static/design-kit/overlays/noise-grid.svg')">
          <header class="absolute top-12">Scan the artifacts to reveal the registry.</header>
          <div id="lens" class="fixed">SCAN</div>
          {layers}
          <div id="status" class="absolute bottom-12">0 of 8 artifacts scanned</div>
          <script src="/static/vendor/gsap.min.js"></script>
          <script>
            document.getElementById('ndw-content').addEventListener('pointermove', () => {{
              document.getElementById('status').textContent = 'Registry responding';
              gsap.to('.artifact', {{ rotate: 4, duration: 0.3 }});
            }});
          </script>
        </div></body></html>""",
    }
    quality = score_page_doc(doc)
    assert quality["metrics"]["layout_metrics"]["layered_stage"] is True
    assert quality["flags"]["centered_card"] is False
    assert quality["score"] >= 70
