from pathlib import Path

from scripts.run_generation_review_pack import _build_generators
from api.review_pack import (
    build_review_row,
    load_benchmark_cases,
    run_review_pack,
    write_review_pack_bundle,
)


def test_load_benchmark_cases_reads_fixed_manifest():
    cases = load_benchmark_cases(Path("benchmarks/review_pack_v1.json"))
    assert len(cases) == 12
    assert cases[0]["id"] == "music-control-room"
    assert isinstance(cases[0]["seed"], int)


def test_build_review_row_captures_preflight_blocking_and_metrics():
    case = {"id": "bad-case", "brief": "broken", "seed": 12, "tags": ["test"]}
    doc = {
        "kind": "full_page_html",
        "html": """
        <!doctype html><html><body class="text-slate-500">
          <main class="min-h-screen flex items-center justify-center">
            <section class="mx-auto max-w-md">Broken</section>
          </main>
          <script>fetch('/bad');</script>
        </body></html>
        """,
    }
    row = build_review_row(case, "fast", doc, 1234, {"doc_json": "cases/bad-case/fast/doc.json"})
    assert row["preflight_blocking"] is True
    assert row["quality_flags"]["centered_card"] is True
    assert row["layout_metrics"]["region_count"] >= 1
    assert row["color_metrics"]["color_count"] >= 0


def test_run_review_pack_writes_artifacts_and_summary(tmp_path):
    cases = [{"id": "one", "brief": "brief", "seed": 7, "tags": ["demo"]}]
    rows = run_review_pack(
        cases,
        modes=["fast", "premium"],
        out_dir=tmp_path,
        generators={
            "fast": lambda brief, seed: {"kind": "full_page_html", "html": "<!doctype html><html><body><main>Fast</main></body></html>"},
            "premium": lambda brief, seed: {"kind": "full_page_html", "html": "<!doctype html><html><body><main style='background:linear-gradient(#fff,#ddd)'>Premium</main></body></html>"},
        },
    )
    assert len(rows) == 2
    assert (tmp_path / "cases" / "one" / "fast" / "doc.json").exists()
    assert (tmp_path / "cases" / "one" / "premium" / "doc.html").exists()

    summary = write_review_pack_bundle(rows, tmp_path, benchmark_name="review_pack_v1", generated_at="2026-03-23 12:00:00")
    assert summary["summary"]["by_mode"]["fast"]["count"] == 1
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.csv").exists()
    assert (tmp_path / "index.html").exists()


def test_review_pack_generators_disable_fast_review_by_default(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "scripts.run_generation_review_pack.generate_page",
        lambda brief, seed, user_key=None, run_review=True: calls.append(
            {"brief": brief, "seed": seed, "user_key": user_key, "run_review": run_review}
        ) or {"kind": "full_page_html", "html": "<!doctype html><html><body>Fast</body></html>"},
    )
    monkeypatch.setattr(
        "scripts.run_generation_review_pack.generate_page_premium",
        lambda brief, seed, user_key=None: {"kind": "full_page_html", "html": "<!doctype html><html><body>Premium</body></html>"},
    )

    generators = _build_generators(enable_review=False)
    generators["fast"]("brief", 9)
    assert calls[0]["run_review"] is False
    assert calls[0]["user_key"] == "review_pack"
