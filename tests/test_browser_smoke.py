import json
import time
import threading
from pathlib import Path
from socket import socket
from typing import Dict, List

import pytest
import requests
import uvicorn

from api.main import app
from api import main as main_mod

playwright = pytest.importorskip("playwright.sync_api")

ARTIFACT_DIR = Path("artifacts/playwright")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

PREVIEWS = [
    {"id": "file:alpha.json", "title": "Alpha Queue", "category": "studio", "vibe": "kinetic", "created_at": 1},
    {"id": "file:beta.json", "title": "Beta Queue", "category": "gallery", "vibe": "calm", "created_at": 2},
]

QUEUE_PAGE = {
    "kind": "full_page_html",
    "html": """<!doctype html><html><body style="background:#f8fafc;color:#0f172a;">
    <main style="min-height:100vh;display:grid;place-items:center;padding:3rem;">
      <section style="text-align:center;">
        <p style="margin:0 0 1rem;text-transform:uppercase;letter-spacing:.18em;font:600 12px/1.2 system-ui;">Queued</p>
        <h1 style="margin:0;font:800 clamp(2.5rem,8vw,5rem)/0.95 system-ui;">Queue World</h1>
      </section>
    </main>
    </body></html>""",
}

FAST_PAGE = {
    "kind": "full_page_html",
    "html": """<!doctype html><html><body style="background:#eef2ff;color:#0f172a;">
    <main style="min-height:100vh;display:grid;place-items:center;padding:3rem;">
      <section style="text-align:center;">
        <p style="margin:0 0 1rem;text-transform:uppercase;letter-spacing:.18em;font:600 12px/1.2 system-ui;">Fast</p>
        <h1 style="margin:0;font:800 clamp(2.5rem,8vw,5rem)/0.95 system-ui;">Fast World</h1>
      </section>
    </main>
    </body></html>""",
}

PREMIUM_PAGE = {
    "kind": "full_page_html",
    "html": """<!doctype html><html><body style="background:linear-gradient(135deg,#fff7ed,#fffbeb);color:#111827;">
    <main style="min-height:100vh;display:grid;place-items:center;padding:3rem;">
      <section style="text-align:center;max-width:42rem;">
        <p style="margin:0 0 1rem;text-transform:uppercase;letter-spacing:.18em;font:600 12px/1.2 system-ui;">Premium</p>
        <h1 style="margin:0;font:800 clamp(2.75rem,8vw,5.5rem)/0.92 system-ui;">Premium World</h1>
        <p style="margin:1rem 0 0;font:500 1rem/1.6 system-ui;">Slower, more art directed, and intentionally distinct.</p>
      </section>
    </main>
    </body></html>""",
}

EVAL_PAGE = {
    "kind": "full_page_html",
    "html": """<!doctype html><html><body style="background:linear-gradient(135deg,#ecfeff,#cffafe);color:#082f49;">
    <main id="ndw-content" style="min-height:100vh;display:grid;place-items:center;padding:3rem;">
      <section style="text-align:center;max-width:44rem;">
        <p style="margin:0 0 1rem;text-transform:uppercase;letter-spacing:.18em;font:600 12px/1.2 system-ui;">Eval Hook</p>
        <h1 style="margin:0;font:800 clamp(2.75rem,8vw,5.5rem)/0.92 system-ui;">Review Pack Render</h1>
        <p style="margin:1rem 0 0;font:500 1rem/1.6 system-ui;">Rendered through the real app runtime for screenshot capture.</p>
      </section>
    </main>
    </body></html>""",
}


def _free_port() -> int:
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def live_server():
    original_llm_status = main_mod.llm_status
    original_prefetch_topup = main_mod._prefetch_topup_enabled
    main_mod.llm_status = lambda: {"provider": "stub", "has_token": False, "using": "stub"}
    main_mod._prefetch_topup_enabled = lambda: False

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10
    last_error = None
    while time.time() < deadline:
      try:
          resp = requests.get(f"{base_url}/health", timeout=0.5)
          if resp.ok:
              break
      except Exception as exc:  # pragma: no cover - startup polling
          last_error = exc
          time.sleep(0.1)
    else:  # pragma: no cover - startup polling
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError(f"Timed out starting local server: {last_error}")

    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        main_mod.llm_status = original_llm_status
        main_mod._prefetch_topup_enabled = original_prefetch_topup


@pytest.fixture(scope="module")
def browser():
    manager = playwright.sync_playwright().start()
    try:
        browser = manager.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover - depends on local browser install
        manager.stop()
        pytest.skip(f"Chromium is not available for Playwright: {exc}")
    try:
        yield browser
    finally:
        browser.close()
        manager.stop()


def _capture(page, filename: str) -> Path:
    path = ARTIFACT_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    assert path.exists()
    assert path.stat().st_size > 1024
    return path


def _install_api_stubs(page, captured: Dict[str, List[dict]]):
    def handle_prefetch(route):
        if "/api/prefetch/previews" in route.request.url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(PREVIEWS))
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(QUEUE_PAGE))

    def handle_metrics(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"total": 128}))

    def handle_generate(route):
        payload = json.loads(route.request.post_data or "{}")
        captured["generate"].append(payload)
        page_doc = PREMIUM_PAGE if payload.get("quality") == "premium" else FAST_PAGE
        route.fulfill(status=200, content_type="application/json", body=json.dumps(page_doc))

    def handle_stream(route):
        payload = json.loads(route.request.post_data or "{}")
        captured["stream"].append(payload)
        page_doc = PREMIUM_PAGE if payload.get("quality") == "premium" else FAST_PAGE
        if payload.get("quality") == "premium":
            time.sleep(0.25)
        lines = [
            json.dumps({"event": "meta", "data": {"quality": payload.get("quality", "fast")}}),
            json.dumps({"event": "page", "data": page_doc}),
        ]
        route.fulfill(
            status=200,
            headers={"content-type": "application/x-ndjson; charset=utf-8"},
            body="\n".join(lines) + "\n",
        )

    page.route("**/metrics/total**", handle_metrics)
    page.route("**/api/prefetch/**", handle_prefetch)
    page.route("**/generate/stream", handle_stream)
    page.route("**/generate", handle_generate)


def test_landing_stays_configuration_free(browser, live_server):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    captured = {"stream": [], "generate": []}
    _install_api_stubs(page, captured)

    try:
        page.goto(f"{live_server}/?ndw_test=1", wait_until="domcontentloaded")
        page.locator("#heroHint").wait_for()
        page.wait_for_timeout(250)

        assert page.locator("#landingGenerate").count() == 0
        assert page.locator("text=Premium: slower, better art direction.").count() == 0
        assert page.locator("#landingRecoveryBtn").is_hidden()

        _capture(page, "landing-baseline.png")
    finally:
        context.close()


def test_generator_bar_flow_and_quality_persistence(browser, live_server):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    captured = {"stream": [], "generate": []}
    _install_api_stubs(page, captured)

    try:
        page.goto(f"{live_server}/?ndw_test=1&ndw_test_debug=1", wait_until="domcontentloaded")
        page.locator('[data-test-preview-id="file:alpha.json"]').click()
        page.wait_for_function("() => document.body.classList.contains('generated-mode')")
        page.locator("#floatingGenerateWrap").wait_for()
        page.locator("#sitesCounterBadge").wait_for()
        assert (page.locator("#sitesCounterBadge").text_content() or "").strip() == "128"
        assert page.evaluate(
            "() => !!document.getElementById('sitesCounterFloating')?.contains(document.getElementById('floatingGenerateWrap'))"
        ) is True

        _capture(page, "generated-bar-baseline.png")

        page.locator('[data-ndw-mode-toggle="1"]').click()
        page.locator('[data-ndw-mode-popover="1"]').wait_for()
        page.locator('[data-quality-mode="premium"]').click()

        expect_label = page.locator('[data-ndw-mode-label="1"]')
        assert (expect_label.text_content() or "").strip() == "Mode: Premium"
        assert page.evaluate("() => window.localStorage.getItem('ndw_generation_quality')") == "premium"

        page.reload(wait_until="domcontentloaded")
        page.locator('[data-test-preview-id="file:alpha.json"]').click()
        page.wait_for_function("() => document.body.classList.contains('generated-mode')")
        page.locator("#floatingGenerateWrap").wait_for()
        assert (page.locator('[data-ndw-mode-label="1"]').text_content() or "").strip() == "Mode: Premium"

        page.locator('[data-ndw-mode-toggle="1"]').click()
        page.locator('[data-ndw-mode-popover="1"]').wait_for()
        _capture(page, "generated-mode-popover-baseline.png")

        page.locator("#floatingGenerate").click()
        page.locator("#spinnerMsg").wait_for()
        assert (page.locator("#spinnerMsg").text_content() or "").strip() == "Art directing your next world…"
        page.get_by_role("heading", name="Premium World").first.wait_for(timeout=5000)
        assert (page.locator("#sitesCounterBadge").text_content() or "").strip() == "128"

        assert captured["stream"], "expected a streamed generate request"
        assert captured["stream"][-1]["quality"] == "premium"
        assert captured["generate"] == []
    finally:
        context.close()


def test_eval_hook_renders_saved_doc_for_review_pack(browser, live_server):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    captured = {"stream": [], "generate": []}
    _install_api_stubs(page, captured)

    try:
        page.goto(f"{live_server}/?ndw_test=1", wait_until="domcontentloaded")
        page.wait_for_function("() => typeof window.__ndwEvalRenderDoc === 'function'")
        result = page.evaluate(
            """async (doc) => {
              return await window.__ndwEvalRenderDoc(doc, { hideChrome: true, settleMs: 100 });
            }""",
            EVAL_PAGE,
        )
        assert result["ok"] is True
        assert result["generatedMode"] is True
        assert result["heroHidden"] is True
        page.get_by_role("heading", name="Review Pack Render").wait_for(timeout=5000)
        assert not page.locator("text=Roulette").first.is_visible()
        assert not page.locator("text=Random websites with every click").first.is_visible()
        assert not page.locator("text=Click a preview to enter").first.is_visible()
        assert page.locator(".hero-wrap").count() == 0 or page.locator(".hero-wrap").is_hidden()
        _capture(page, "review-pack-eval-hook.png")
    finally:
        context.close()
