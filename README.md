# Non‑Deterministic Website

<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Generate unique, interactive mini-sites with AI — one click, infinite possibilities**

</div>

---

A tiny FastAPI app that prompts an LLM to generate exactly one self‑contained interactive web app per request and renders it safely inside a sandboxed iframe. It emphasizes instant, meaningful interaction (clear controls, visible effects) and enforces strict output and sandbox rules.

---

## How it works

```
┌─────────────┐
│ User clicks │
│  Generate   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐      ┌──────────────┐
│ Prefetch Queue? │─Yes─→│ Dequeue page │
└────────┬────────┘      └──────┬───────┘
         │                      │
         No                     │
         │                      │
         ▼                      │
  ┌──────────┐                 │
  │ Call LLM │                 │
  └─────┬────┘                 │
        │                      │
        └──────────┬───────────┘
                   │
                   ▼
          ┌────────────────┐
          │ Render in      │
          │ sandboxed      │
          │ iframe         │
          └────────┬───────┘
                   │
                   ▼
          ┌────────────────┐
          │ Increment      │
          │ counter        │
          └────────┬───────┘
                   │
                   ▼
          ┌────────────────┐
          │ Display site   │
          └────────────────┘
```

### Request → Generation
- **POST** `/generate` accepts an optional `brief` and `seed`
- Server first tries to serve a **prefetched page** (dequeue‑first approach)
- If serving from prefetch, simulates LLM latency with a small configurable delay
- On success, a persistent counter increments; the UI shows a floating **"Sites generated"** badge from `/metrics/total`

### Prefetch queue
- **Disk‑backed FIFO** at `cache/prefetch/`
- Fill endpoint asks the LLM for **5–10 pages** and enqueues them (LLM‑only; no offline prefetch)
- **Background top‑up**: when the queue is low, the server refills in the background (guarded by env flags)
- **Dedupe**: a signature registry avoids recent repeats; duplicates prompt a retry with a nudged seed

### Output constraints and safety
- LLM must return JSON in one of two shapes: a single `{kind:"full_page_html"}` document or a single custom component with inline HTML/JS
- Frontend **strips external `<script src>` tags** and runs only inline JS in a **sandboxed iframe** with a strict CSP
- Iframe auto‑resizes and auto‑focuses so keyboard input works immediately

---

## Quickstart

**Prerequisites:** Python 3.10+ and pip. (Node is optional; a prebuilt `static/tailwind.css` is used in dev.)

```bash
# 1. Set up virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
# or: pip install fastapi uvicorn requests pydantic jsonschema ndjson

# 3. Run the API (dev reload)
uvicorn api.main:app --reload --port 8000
```

**Open** http://127.0.0.1:8000/ for the demo UI.

### API Configuration

Put provider keys in `.env` (auto‑loaded):

```bash
OPENROUTER_API_KEY=sk-...
OPENROUTER_MODEL=google/gemma-3n-e2b-it:free
# optional: FORCE_OPENROUTER_ONLY=1
```

---

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **GET** | `/` | Demo UI |
| **GET** | `/health` | Health check: `{ "status": "ok" }` |
| **GET** | `/llm/status` | Provider/model/has_token without calling the model |
| **GET** | `/llm/probe` | Lightweight readiness probe |
| **GET** | `/metrics/total` | Global "sites generated" counter |
| **GET** | `/prefetch/status` | Current queue size and directory |
| **POST** | `/validate` | Validate a page structure |
| **POST** | `/generate` | Generate or dequeue a page (dedupe applied; counter increments) |
| **POST** | `/generate/stream` | NDJSON stream: `{event:"meta"}` then `{event:"page", data:{...}}` |
| **POST** | `/prefetch/fill` | Ask the LLM for N pages (5–10) and enqueue |

---

## Configuration (env)

### LLM provider (OpenRouter by default)
```bash
OPENROUTER_API_KEY=        # (required for live generation)
OPENROUTER_MODEL=          # default: google/gemma-3n-e2b-it:free
FORCE_OPENROUTER_ONLY=     # default: 0 — force OpenRouter path when set

# Optional Gemini:
GEMINI_API_KEY=            # or GOOGLE_API_KEY
MODEL_NAME=                # Gemini model name
```

### Generation
```bash
TEMPERATURE=               # default: 1.2
ALLOW_OFFLINE_GENERATION=  # dev only; affects /generate fallback, not prefetch
```

### Prefetch
```bash
PREFETCH_DIR=              # default: cache/prefetch
PREFETCH_BATCH_MIN=        # default: 5
PREFETCH_BATCH_MAX=        # default: 10
PREFETCH_DELAY_MS=         # delay when serving dequeued pages
PREFETCH_LOW_WATER=        # trigger background refill threshold
PREFETCH_FILL_TO=          # target queue size for refill
PREFETCH_TOPUP_ENABLED=    # enable background top-up
```

### Dedupe
```bash
DEDUPE_ENABLED=            # default: 1
DEDUPE_MAX=                # max dedupe registry size
DEDUPE_RECENT_FILE=        # dedupe registry file path
```

### Access / CORS / rate limiting
```bash
API_KEYS=                  # comma‑separated; if empty, local dev is open
ALLOW_ORIGINS=             # default: *
RATE_WINDOW_SECONDS=       # rate limit window
RATE_MAX_REQUESTS=         # max requests per window
```

---

## Development

Run tests:

```bash
pytest -q
```

The test suite covers:
- Prefetch queue (enqueue/dequeue, dedupe, fill clamping)
- Dequeue‑first generation
- Background top‑ups
- Status endpoints

> **Note:** During tests, artificial delays and background workers are disabled for speed and determinism.

---

## Notes on generation rules

The prompt enforces strict quality and interactivity standards:

- **Strictly banned:** Passive visuals, randomizers‑only, menu‑only UIs, utility archetypes (calculators/clocks/to‑dos/quizzes)
- **Classic/trivial mini‑games allowed** but must meet the interactivity bar:
  - Clear controls
  - Visible feedback
  - Responsive interaction
- **Required features:**
  - Clear, immediate input → effect loops
  - Obvious affordances
  - At least two input modes (mouse/touch + another)
  - Visible feedback

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Provider 429 rate limit** | Back off; prefetch masks transient spikes |
| **SSL/cert issues** | Ensure system trust/certifi is up‑to‑date; avoid disabling verification globally |
| **"Invalid JSON" from provider** | The server extracts the first JSON object and validates/normalizes it; try again or adjust temperature/model |

---

## License

MIT — see `LICENSE`.
