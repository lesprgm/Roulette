import importlib
import os

from fastapi.testclient import TestClient
import pytest


API_HEADERS = {"x-api-key": "demo_123"}


@pytest.fixture()
def isolated_prefetch(monkeypatch, tmp_path):
    monkeypatch.setenv("PREFETCH_DIR", str(tmp_path / "fast-pfq"))
    monkeypatch.setenv("PREMIUM_PREFETCH_DIR", str(tmp_path / "premium-pfq"))
    monkeypatch.setenv("DEDUPE_RECENT_FILE", str(tmp_path / "seen.json"))

    from api import dedupe as dd
    from api import prefetch as pf

    importlib.reload(dd)
    importlib.reload(pf)

    from api import main as main_mod

    monkeypatch.setattr(main_mod, "prefetch", pf)
    return pf


def _make_doc(label: str):
    safe = label.replace(" ", "-")
    return {
        "kind": "full_page_html",
        "html": (
            "<!doctype html><html><body>"
            f"<main id='ndw-content' data-region class='case-{safe}'><section data-region><h1>{label}</h1>"
            f"<button id='act-{safe}'>Act</button>"
            f"<script>document.getElementById('act-{safe}')?.addEventListener('click',()=>{{}});</script>"
            "</section></main></body></html>"
        ),
    }


def test_prefetch_enqueue_dequeue_basic(isolated_prefetch):
    pf = isolated_prefetch
    assert pf.size() == 0
    assert pf.enqueue(_make_doc("A"))
    assert pf.enqueue(_make_doc("B"))

    assert pf.size() == 2
    assert pf.dequeue()["html"].find("A") >= 0
    assert pf.dequeue()["html"].find("B") >= 0
    assert pf.dequeue() is None


def test_premium_lane_isolated_from_fast(isolated_prefetch):
    pf = isolated_prefetch
    assert pf.enqueue(_make_doc("fast"), lane="fast")
    assert pf.enqueue(_make_doc("premium"), lane="premium")

    assert pf.size("fast") == 1
    assert pf.size("premium") == 1
    assert "fast" in pf.dequeue("fast")["html"]
    assert "premium" in pf.dequeue("premium")["html"]


def test_file_queue_drops_stale_test_fixture_docs(isolated_prefetch):
    pf = isolated_prefetch
    premium_dir = pf._lane_dir("premium")  # noqa: SLF001 - regression coverage for file fallback.
    premium_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = premium_dir / "stale-test-fixture.json"
    fixture_path.write_text(
        (
            '{"kind":"full_page_html","title":"Premium Preview","category":"unit-test",'
            '"vibe":"testing","html":"<!doctype html><html><body><h1>Premium Preview</h1></body></html>"}'
        ),
        encoding="utf-8",
    )

    assert pf.peek(lane="premium") == []
    assert not fixture_path.exists()

    fixture_path.write_text(
        (
            '{"kind":"full_page_html","title":"Premium Preview","category":"unit-test",'
            '"vibe":"testing","html":"<!doctype html><html><body><h1>Premium Preview</h1></body></html>"}'
        ),
        encoding="utf-8",
    )
    assert pf.dequeue("premium") is None
    assert not fixture_path.exists()


def test_redis_failure_disables_redis_and_falls_back_to_file_queue(isolated_prefetch, monkeypatch):
    pf = isolated_prefetch

    class BrokenRedis:
        def llen(self, *_args, **_kwargs):
            raise RuntimeError("dns failed")

    monkeypatch.setattr(pf, "_REDIS_CLIENT", BrokenRedis())
    monkeypatch.setattr(pf, "_REDIS_DISABLED_REASON", "")

    assert pf.size("premium") == 0
    assert pf.backend() == "file"
    assert pf.redis_disabled_reason() == "size_failed"

    assert pf.enqueue(_make_doc("fallback"), lane="premium")
    assert pf.size("premium") == 1


def test_prefetch_fill_enqueues_premium_docs(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    docs = [_make_doc(f"premium-{idx}") for idx in range(5)]
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(
        main_mod,
        "_generate_premium_batch_candidates",
        lambda *args, **kwargs: docs[: kwargs["batch_size"]],
    )
    client = TestClient(app)

    response = client.post("/prefetch/fill", json={"brief": "", "count": 5}, headers=API_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requested"] == 5
    assert body["added"] == 5
    assert body["queue_size"] == 5
    assert isolated_prefetch.size("premium") == 5
    assert isolated_prefetch.size("fast") == 0


def test_generate_uses_premium_queue_first(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    queued = _make_doc("queued premium")
    assert isolated_prefetch.enqueue(queued, lane="premium")
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(
        main_mod,
        "_stream_premium_first_page",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("queue should serve first")),
    )
    client = TestClient(app)

    response = client.post("/generate", json={"brief": "", "seed": 1}, headers=API_HEADERS)

    assert response.status_code == 200
    assert response.json()["html"] == queued["html"]
    assert isolated_prefetch.size("premium") == 0


def test_generate_triggers_premium_topup_when_queue_low(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "PREMIUM_LOW_WATER", 1)
    monkeypatch.setattr(main_mod, "PREMIUM_FILL_TO", 3)
    monkeypatch.setattr(main_mod, "PREMIUM_TOPUP_ENABLED", True)
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    assert isolated_prefetch.enqueue(_make_doc("one"), lane="premium")

    scheduled = []
    monkeypatch.setattr(
        main_mod,
        "_schedule_premium_topup",
        lambda background_tasks, brief, target, context: scheduled.append((brief, target, context)),
    )
    client = TestClient(app)

    response = client.post("/generate", json={"brief": "", "seed": 2}, headers=API_HEADERS)

    assert response.status_code == 200
    assert scheduled == [("", 3, "site.generate")]


def test_premium_burst_first_page_and_leftovers(monkeypatch, isolated_prefetch):
    from api import main as main_mod

    docs = [_make_doc("burst-1"), _make_doc("burst-2"), _make_doc("burst-3")]
    monkeypatch.setattr(main_mod, "prefetch", isolated_prefetch)
    monkeypatch.setattr(main_mod, "PREMIUM_BATCH_SIZE", 3)
    monkeypatch.setattr(main_mod, "PREMIUM_FILL_TO", 10)
    monkeypatch.setattr(main_mod, "_apply_local_acceptance_batch", lambda items, context: items)
    monkeypatch.setattr(main_mod, "llm_generate_page_premium_burst", lambda *args, **kwargs: iter(docs))

    first, leftovers = main_mod._start_premium_burst("", seed=12, user_key="student", context="test.burst")
    assert first == docs[0]
    assert leftovers is not None

    main_mod._drain_premium_burst_to_queue(leftovers, context="test.burst.leftovers", max_queue=10)
    assert isolated_prefetch.size("premium") == 2


def test_premium_burst_missing_slots_trigger_refill(monkeypatch, isolated_prefetch):
    from api import main as main_mod

    docs = [_make_doc("leftover-1"), _make_doc("leftover-2")]
    monkeypatch.setattr(main_mod, "prefetch", isolated_prefetch)
    monkeypatch.setattr(main_mod, "PREMIUM_REFILL_MISSING_ENABLED", True)
    monkeypatch.setattr(main_mod, "_apply_local_acceptance_batch", lambda items, context: items)

    refill_calls = []
    monkeypatch.setattr(
        main_mod,
        "_refill_missing_premium_slots",
        lambda brief, *, missing_slots, max_queue, context: refill_calls.append(
            {
                "brief": brief,
                "missing_slots": missing_slots,
                "max_queue": max_queue,
                "context": context,
            }
        ),
    )

    def interrupted():
        yield docs[0]
        yield docs[1]
        raise RuntimeError("upstream stream ended")

    main_mod._drain_premium_burst_to_queue(
        interrupted(),
        context="test.burst.leftovers",
        max_queue=10,
        requested_count=5,
        brief="random worlds",
    )

    assert isolated_prefetch.size("premium") == 2
    assert refill_calls == [
        {
            "brief": "random worlds",
            "missing_slots": 3,
            "max_queue": 10,
            "context": "test.burst.leftovers.missing_refill",
        }
    ]


def test_premium_batch_candidates_preserve_partial_success_after_upstream_error(monkeypatch):
    from api import main as main_mod

    docs = [_make_doc("candidate-1"), _make_doc("candidate-2")]
    monkeypatch.setattr(main_mod, "_apply_local_acceptance_batch", lambda items, context: items)

    def interrupted_burst(*args, **kwargs):
        yield docs[0]
        yield docs[1]
        raise RuntimeError("upstream dropped")

    monkeypatch.setattr(main_mod, "llm_generate_page_premium_burst", interrupted_burst)

    candidates = main_mod._generate_premium_batch_candidates(
        "",
        batch_size=5,
        seed=99,
        user_key="student",
        context="test.partial_batch",
    )

    assert candidates == docs


def test_missing_slot_refill_runs_one_full_replacement_burst(monkeypatch, isolated_prefetch):
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "prefetch", isolated_prefetch)
    monkeypatch.setattr(main_mod, "PREMIUM_REFILL_MISSING_ENABLED", True)
    monkeypatch.setattr(main_mod, "PREMIUM_BATCH_SIZE", 15)
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)

    calls = []
    docs = [_make_doc(f"replacement-{idx}") for idx in range(15)]

    def fake_candidates(*args, **kwargs):
        calls.append(kwargs)
        return docs

    monkeypatch.setattr(main_mod, "_generate_premium_batch_candidates", fake_candidates)

    main_mod._refill_missing_premium_slots(
        "random worlds",
        missing_slots=3,
        max_queue=10,
        context="test.missing_refill",
    )

    assert calls[0]["batch_size"] == 15
    assert isolated_prefetch.size("premium") == 10


def test_top_up_premium_queue_uses_premium_lane(monkeypatch, isolated_prefetch):
    from api import main as main_mod

    docs = [_make_doc("premium-a"), _make_doc("premium-b"), _make_doc("premium-c")]
    monkeypatch.setattr(main_mod, "prefetch", isolated_prefetch)
    monkeypatch.setattr(main_mod, "PREMIUM_BATCH_SIZE", 3)
    monkeypatch.setattr(main_mod, "PREMIUM_FILL_TO", 3)
    monkeypatch.setattr(main_mod, "PREMIUM_TOPUP_ENABLED", True)
    monkeypatch.setattr(main_mod, "PREMIUM_QUEUE_ENABLED", True)
    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: True)
    monkeypatch.setattr(main_mod, "_generate_premium_batch_candidates", lambda *args, **kwargs: docs)

    main_mod._top_up_premium_queue("", min_fill=3)

    assert isolated_prefetch.size("premium") == 3
    assert isolated_prefetch.size("fast") == 0


def test_prefetch_fill_requires_premium_llm(monkeypatch, isolated_prefetch):
    from api.main import app
    from api import main as main_mod

    monkeypatch.setattr(main_mod, "llm_premium_available", lambda: False)
    client = TestClient(app)

    response = client.post("/prefetch/fill", json={"brief": "", "count": 5}, headers=API_HEADERS)

    assert response.status_code == 503


def test_prefetch_status_reports_both_lanes(isolated_prefetch):
    from api.main import app

    assert isolated_prefetch.enqueue(_make_doc("fast"), lane="fast")
    assert isolated_prefetch.enqueue(_make_doc("premium"), lane="premium")
    response = TestClient(app).get("/prefetch/status")

    assert response.status_code == 200
    body = response.json()
    assert body["size"] == 1
    assert body["premium_size"] == 1
    assert body["premium_queue_enabled"] is True
    assert body["premium_fill_to"] >= body["premium_low_water"]
    assert body["premium_refill_missing_enabled"] is True
    assert body["dir"] == os.getenv("PREFETCH_DIR")
    assert "redis_disabled_reason" in body
