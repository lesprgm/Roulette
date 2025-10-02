# Non‑Deterministic Website

LLM‑as‑backend demo: a thin FastAPI gateway prompts an LLM to synthesize exactly one self‑contained interactive web app per request and renders it safely in a sandboxed iframe.

- Backend: FastAPI + a minimal LLM client (OpenRouter by default) that enforces strict output shapes, normalizes results, dedupes repeats, and can prefetch in batches.
- Frontend: vanilla JS + Tailwind v4; renders returned HTML/JS inside a sandboxed iframe (no external scripts) and auto‑resizes.
- “Backendless” for business logic: no DB, no classic models—just a tiny server that proxies the LLM and enforces safety.


## Prerequisites

- Python 3.10+ and pip
- Node.js 18+ and npm
- Optional: Redis (only if you swap in a Redis rate limiter; default is in‑process)

## Setup

1) Python env and dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install fastapi pydantic uvicorn jsonschema requests ndjson redis
```

2) Node dependencies

```bash
npm install
```

## Build CSS (Tailwind)

One-off build:

```bash
npm run build:css
```

Watch during development:

```bash
npm run watch:css
```

Input: `src/styles/input.css` → Output: `static/tailwind.css`.
Tailwind v4 scans sources via `@source` directives in `src/styles/input.css` (templates + JS).

## Run the API

With auto-reload for development:

```bash
uvicorn api.main:app --reload --port 8000
```

Then visit:
- Health: http://127.0.0.1:8000/health
- Demo UI: http://127.0.0.1:8000/ (renders and regenerates pages on click)

Environment is auto‑loaded from `.env` on startup (no extra deps). Put your keys there.

Allow CORS origins via env:

```bash
export ALLOW_ORIGINS="http://localhost:3000,https://yourdomain.com"
```

## API endpoints
- GET `/health` → `{ "status": "ok" }`
- GET `/llm/status` → Current provider/model/has_token (no model call)
- GET `/llm/probe` → Quick readiness probe
- POST `/validate` → Validate a page against the schema or minimal checks
- POST `/generate` → Generate a page (dedupe applied; dequeues from prefetch queue first)
- POST `/generate/stream` → NDJSON stream: `{ "event":"meta" }` then `{ "event":"page", "data":{...} }`
- POST `/prefetch/fill` → Generate 5–10 pages per request and enqueue them for later `/generate`
- POST `/generate/stream` → NDJSON stream with two events: `{ "event":"meta" }` then `{ "event":"page", "data":{...} }`

### Example: validate JSON

```bash
curl -s -X POST http://127.0.0.1:8000/validate \
	-H 'Content-Type: application/json' \
	-d @example_outputs/gold.json | jq
```

### Example: generate a page

```bash
curl -s -X POST http://127.0.0.1:8000/generate \
	-H 'Content-Type: application/json' \
	-H 'x-api-key: demo_123' \
	-d '{"brief":"Landing page for a JSON-first site","seed":123}' | jq
```

Notes:
- `brief` may be empty: the model invents a theme. `seed` is optional.
- If the server’s own rate limit triggers (HTTP 429), check `X-RateLimit-*` headers.
- If the LLM provider rate limits you, the server will return a page with `{ "error": "..." }` in the body; prefetch helps hide transient outages.

### Example: stream (NDJSON)

```bash
curl -N -X POST http://127.0.0.1:8000/generate/stream \
	-H 'Content-Type: application/json' \
	-H 'x-api-key: dev-key' \
	-d '{"brief":"Landing page for a JSON-first site"}'
```

## Development

- Run tests:

```bash
pytest -q
```

- Lint/format (optional if installed): `flake8`, `black .`

- Tailwind scanning is configured in `src/styles/input.css` via `@source`.

## Configuration

Environment is read from `.env` at startup.

LLM provider (OpenRouter by default):
- `OPENROUTER_API_KEY` (required for live generation)
- `OPENROUTER_MODEL` (default: `google/gemma-3n-e2b-it:free`)
- `FORCE_OPENROUTER_ONLY` (default: `1`) — ignore Gemini even if set

Legacy Gemini vars (optional):
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- `MODEL_NAME` (e.g., `gemini-1.5-pro`)

Generation controls:
- `TEMPERATURE` (default: `1.2`)
- `ALLOW_OFFLINE_GENERATION` (dev only): if set, generates a tiny sandbox app without calling an LLM

Access and rate limiting:
- `API_KEYS` (comma‑separated). If empty, auth is disabled for local dev.
- `ALLOW_ORIGINS` (default `*`)
- `RATE_WINDOW_SECONDS`, `RATE_MAX_REQUESTS`

Caching / dedupe / prefetch:
- `CACHE_DIR`, `CACHE_TTL_SECONDS`
- `DEDUPE_ENABLED` (default `1`), `DEDUPE_MAX` (default `200`)
- `PREFETCH_DIR` (default `cache/prefetch`)
- `PREFETCH_BATCH_MIN` (default `5`), `PREFETCH_BATCH_MAX` (default `10`)

Notes:
- The backend normalizes model output to exactly one of two shapes:
	1) `{ "kind":"full_page_html", "html":"<!doctype html>..." }`
	2) `{ "components": [ { "id": "custom-1", "type": "custom", "props": { "html": "<div>...<script>...</script></div>", "height": 360 } } ] }`
- The frontend renders either a full‑page HTML app or the first custom component’s HTML inside a sandboxed iframe.
- External `<script src>` tags are stripped; only inline scripts run inside the sandbox.

## Project structure (minimal)

```
.
├── api/
│   ├── main.py          # FastAPI app (routes, rate limiting, prefetch)
│   ├── llm_client.py    # OpenRouter/Gemini client + normalization + dedupe
│   ├── prefetch.py      # File‑backed prefetch queue (5–10 per /prefetch/fill)
│   ├── dedupe.py        # Signature‑based recent app registry
│   └── auth.py          # Optional API key enforcement
├── static/
│   └── js/app.js        # Frontend: sandboxed iframe renderer + spinner
├── src/styles/input.css # Tailwind v4 source (+ @source scan globs)
├── templates/index.html # Demo UI (hands‑off regenerate button)
├── page_schema.json (optional)
├── requirements.txt (optional)
├── package.json
└── README.md
```

That’s it: a small, pragmatic stack that turns LLM output into a live, sandboxed app.

## Optional: live LLM tests

To verify real provider calls (skipped by default):

```bash
RUN_LIVE_LLM_TESTS=1 ./venv/bin/pytest -q tests/test_live_llm_openrouter.py
```

Requires `OPENROUTER_API_KEY` set in `.env`.

## License

See `LICENSE` for details.