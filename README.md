# Non‑Deterministic Website

A tiny, hands‑off demo that generates a different landing page on each click.

- Backend (FastAPI) calls an LLM (Gemini) that returns JSON‑only page specs.
- Frontend renders that JSON with Tailwind and obvious palette variations.
- No inputs required: each request picks a theme, palette, and layout for you.


## Prerequisites

- Python 3.10+ and pip
- Node.js 18+ and npm
- Optional: Redis (if you configure cache to use it; see `api/cache.py`)

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

Allow CORS origins via env:

```bash
export ALLOW_ORIGINS="http://localhost:3000,https://yourdomain.com"
```

## API endpoints

- GET `/health` → `{ "status": "ok" }`
- GET `/llm/status` → LLM configuration status (no model call)
- GET `/llm/probe` → Tiny JSON-only probe of the first available model
- POST `/validate` → Validate a page JSON against the schema
- POST `/generate` → Generate a page JSON (rate-limited, cached)
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
	-H 'x-api-key: dev-key' \
	-d '{"brief":"Landing page for a JSON-first site","seed":123}' | jq
```

Notes:
- `/generate` accepts a minimal body (brief can be a single space) and the server will choose a theme/seed/palette.
- If rate-limited (HTTP 429), retry after the indicated seconds. The `x-api-key` header distinguishes clients for rate limiting.

### Example: stream components (NDJSON)

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

- `GEMINI_API_KEY` or `GOOGLE_API_KEY`: API key for the Gemini model.
- `MODEL_NAME`: Gemini model (default: `gemini-1.5-pro`).
- `TEMPERATURE`: Controls variety (default: `1.2`).
- `ALLOW_ORIGINS`: comma-separated list of allowed CORS origins (default: `*`).
- Optional Redis cache/limits: see `api/cache.py` and `api/ratelimit.py`.

Behavioral notes:
- The backend nudges variety: fresh seed/brief per call, palettes from {slate, indigo, rose, emerald, amber, violet}, ≥3 component types, grid layout ~30% of runs.
- The frontend applies palette styles to visible surfaces (hero background/text, CTA button, card borders) and uses safe defaults in renderers.

## Project structure (minimal)

```
.
├── api/
│   ├── main.py          # FastAPI app (routes, static mount, preview)
│   └── llm_client.py    # Gemini call + JSON page generation
├── static/
│   └── js/app.js        # Frontend: generate, renderers, palette + spinner
├── src/styles/input.css # Tailwind v4 source (+ @source scan globs)
├── templates/index.html # Demo UI (hands‑off regenerate button)
├── schemas/page_schema.json
├── prompts/page_prompt.md
├── requirements.txt
├── package.json
└── README.md
```

That’s it: a small, pragmatic stack that turns LLM output into a live page preview.

## License

See `LICENSE` for details.