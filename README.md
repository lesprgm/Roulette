# Non‑Deterministic Website

A tiny FastAPI app that prompts an LLM to generate exactly one self‑contained interactive web app per request and renders it safely inside a sandboxed iframe. It emphasizes instant, meaningful interaction (clear controls, visible effects) and enforces strict output and sandbox rules.

## How it works

- Request → Generation
  - POST `/generate` accepts an optional `brief` and `seed`.
  - The server first tries to serve a prefetched page (dequeue‑first). If it serves from prefetch, it simulates LLM latency with a small configurable delay.
  - On success, a persistent counter increments; the UI shows a floating “Sites generated” badge sourced from `/metrics/total`.

- Prefetch queue
  - Disk‑backed FIFO at `cache/prefetch/`. A fill endpoint asks the LLM for 5–10 pages and enqueues them (LLM‑only; no offline prefetch).
  - Background top‑up: when the queue is low, the server refills in the background (guarded by env flags). A small warmup can run at startup.
  - Dedupe: a signature registry avoids recent repeats; duplicates prompt a retry with a nudged seed.

- Output constraints and safety
  - The LLM must return JSON in one of two shapes only: a single `{kind:"full_page_html"}` document or a single custom component with inline HTML/JS.
  - The frontend strips external `<script src>` tags and runs only inline JS in a sandboxed iframe with a strict CSP. The iframe auto‑resizes and auto‑focuses so keyboard input works immediately.

## Quickstart

Prereqs: Python 3.10+ and pip. (Node is optional; a prebuilt `static/tailwind.css` is used in dev.)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # or: pip install fastapi uvicorn requests pydantic jsonschema ndjson

# Run the API (dev reload)
uvicorn api.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/ for the demo UI.

Put provider keys in `.env` (auto‑loaded), for example:

```bash
OPENROUTER_API_KEY=sk-...
OPENROUTER_MODEL=google/gemma-3n-e2b-it:free
# optional: FORCE_OPENROUTER_ONLY=1
```

## Endpoints

- GET `/` — Demo UI
- GET `/health` — `{ "status": "ok" }`
- GET `/llm/status` — Provider/model/has_token without calling the model
- GET `/llm/probe` — Lightweight readiness probe
- GET `/metrics/total` — Global “sites generated” counter
- GET `/prefetch/status` — Current queue size and directory
- POST `/validate` — Validate a page structure
- POST `/generate` — Generate or dequeue a page (dedupe applied; counter increments)
- POST `/generate/stream` — NDJSON stream: `{event:"meta"}` then `{event:"page", data:{...}}`
- POST `/prefetch/fill` — Ask the LLM for N pages (5–10) and enqueue

## Configuration (env)

LLM provider (OpenRouter by default):
- `OPENROUTER_API_KEY` (required for live generation)
- `OPENROUTER_MODEL` (default: `google/gemma-3n-e2b-it:free`)
- `FORCE_OPENROUTER_ONLY` (default: `0`) — force OpenRouter path when set
- Optional Gemini: `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `MODEL_NAME`

Generation:
- `TEMPERATURE` (default `1.2`)
- `ALLOW_OFFLINE_GENERATION` (dev only; affects `/generate` fallback, not prefetch)

Prefetch:
- `PREFETCH_DIR` (default `cache/prefetch`)
- `PREFETCH_BATCH_MIN`/`PREFETCH_BATCH_MAX` (default `5`/`10`)
- `PREFETCH_DELAY_MS` (delay when serving dequeued pages)
- `PREFETCH_LOW_WATER`, `PREFETCH_FILL_TO`, `PREFETCH_TOPUP_ENABLED`

Dedupe:
- `DEDUPE_ENABLED` (default `1`), `DEDUPE_MAX`, `DEDUPE_RECENT_FILE`

Access / CORS / rate limiting:
- `API_KEYS` (comma‑separated; if empty, local dev is open)
- `ALLOW_ORIGINS` (default `*`)
- `RATE_WINDOW_SECONDS`, `RATE_MAX_REQUESTS`

## Development

Run tests:

```bash
pytest -q
```

The test suite covers the prefetch queue (enqueue/dequeue, dedupe, fill clamping), dequeue‑first generation, background top‑ups, and status endpoints. During tests, artificial delays and background workers are disabled for speed and determinism.

## Notes on generation rules

- The prompt strictly bans passive visuals, randomizers‑only, and menu‑only UIs, plus utility archetypes like calculators/clocks/to‑dos/quizzes.
- Classic/trivial mini‑games are allowed but must still meet the interactivity bar (clear controls, visible feedback, responsiveness).
- Apps must provide clear, immediate input → effect loops, obvious affordances, and at least two input modes (mouse/touch plus another) with visible feedback.

## Troubleshooting

- Provider 429 rate limit: back off; prefetch masks transient spikes.
- SSL/cert issues: ensure system trust/certifi is up‑to‑date; avoid disabling verification globally.
- “Invalid JSON” from provider: the server extracts the first JSON object and validates/normalizes it; try again or adjust temperature/model.

## License

MIT — see `LICENSE`.