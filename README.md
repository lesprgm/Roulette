```
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║         N O N - D E T E R M I N I S T I C   W E B S I T E           ║
║                                                                       ║
║   LLM-Powered Interactive Web App Generator with Sandboxed Rendering ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

**A tiny FastAPI app that prompts an LLM to generate exactly one self‑contained interactive web app per request and renders it safely inside a sandboxed iframe.**

Key Features:
- Instant, meaningful interaction (clear controls, visible effects)
- Strict output validation and sandbox security rules
- Smart prefetch queue for fast response times
- Deduplication to ensure variety

---

## How it works

### Architecture Flow

```
┌─────────────┐
│   Client    │  POST /generate {brief, seed}
│   Request   │
└──────┬──────┘
       │
       v
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Server                       │
│                                                          │
│  ┌────────────────────┐         ┌──────────────────┐   │
│  │  Prefetch Queue    │────────>│  LLM Provider    │   │
│  │  (Disk-backed FIFO)│         │  (OpenRouter/    │   │
│  │                    │         │   Gemini)        │   │
│  │  • Dequeue first   │         └──────────────────┘   │
│  │  • Background fill │                                │
│  │  • Dedupe check    │         ┌──────────────────┐   │
│  └────────────────────┘         │  Validator       │   │
│                                  │  • JSON schema   │   │
│                                  │  • Safety rules  │   │
│                                  └──────────────────┘   │
└──────────────────┬───────────────────────────────────────┘
                   │
                   v
        ┌────────────────────┐
        │  Sandboxed Iframe  │
        │  • Strict CSP      │
        │  • No external JS  │
        │  • Auto-resize     │
        └────────────────────┘
```

### Key Components

**Request → Generation**
- POST `/generate` accepts optional `brief` and `seed`
- Server tries prefetch queue first (dequeue‑first strategy)
- Simulates LLM latency for prefetched pages
- Counter increments on success; UI shows "Sites generated" badge

**Prefetch Queue**
- Disk‑backed FIFO at `cache/prefetch/`
- Bulk generation: 5–10 pages per fill request
- Background top‑up when queue is low
- Dedupe registry avoids recent repeats

**Output Constraints & Safety**
- LLM returns JSON: `{kind:"full_page_html"}` or custom component
- Frontend strips external `<script src>` tags
- Sandboxed iframe with strict CSP
- Auto‑resize and auto‑focus for immediate interaction

---

## Quickstart

> Prerequisites: Python 3.10+ and pip  
> (Node is optional; a prebuilt `static/tailwind.css` is used in dev)

### Installation & Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# Alternative: pip install fastapi uvicorn requests pydantic jsonschema ndjson

# Run the API with dev reload
uvicorn api.main:app --reload --port 8000
```

### Access the UI

Open http://127.0.0.1:8000/ for the demo UI.

### Configuration

Put provider keys in `.env` (auto‑loaded):

```bash
OPENROUTER_API_KEY=sk-...
OPENROUTER_MODEL=google/gemma-3n-e2b-it:free
# optional: FORCE_OPENROUTER_ONLY=1
```

---

## Endpoints

<table>
<tr>
<th>Method</th>
<th>Endpoint</th>
<th>Description</th>
</tr>
<tr>
<td>GET</td>
<td><code>/</code></td>
<td>Demo UI</td>
</tr>
<tr>
<td>GET</td>
<td><code>/health</code></td>
<td>Health check: <code>{ "status": "ok" }</code></td>
</tr>
<tr>
<td>GET</td>
<td><code>/llm/status</code></td>
<td>Provider/model/has_token without calling the model</td>
</tr>
<tr>
<td>GET</td>
<td><code>/llm/probe</code></td>
<td>Lightweight readiness probe</td>
</tr>
<tr>
<td>GET</td>
<td><code>/metrics/total</code></td>
<td>Global "sites generated" counter</td>
</tr>
<tr>
<td>GET</td>
<td><code>/prefetch/status</code></td>
<td>Current queue size and directory</td>
</tr>
<tr>
<td>POST</td>
<td><code>/validate</code></td>
<td>Validate a page structure</td>
</tr>
<tr>
<td>POST</td>
<td><code>/generate</code></td>
<td>Generate or dequeue a page (dedupe applied; counter increments)</td>
</tr>
<tr>
<td>POST</td>
<td><code>/generate/stream</code></td>
<td>NDJSON stream: <code>{event:"meta"}</code> then <code>{event:"page", data:{...}}</code></td>
</tr>
<tr>
<td>POST</td>
<td><code>/prefetch/fill</code></td>
<td>Ask the LLM for N pages (5–10) and enqueue</td>
</tr>
</table>

---

## Configuration (env)

### LLM Provider

<table>
<tr>
<th>Variable</th>
<th>Default</th>
<th>Description</th>
</tr>
<tr>
<td><code>OPENROUTER_API_KEY</code></td>
<td>-</td>
<td>Required for live generation</td>
</tr>
<tr>
<td><code>OPENROUTER_MODEL</code></td>
<td><code>google/gemma-3n-e2b-it:free</code></td>
<td>Model to use</td>
</tr>
<tr>
<td><code>FORCE_OPENROUTER_ONLY</code></td>
<td><code>0</code></td>
<td>Force OpenRouter path when set</td>
</tr>
<tr>
<td><code>GEMINI_API_KEY</code> / <code>GOOGLE_API_KEY</code></td>
<td>-</td>
<td>Optional Gemini support</td>
</tr>
<tr>
<td><code>MODEL_NAME</code></td>
<td>-</td>
<td>Model name for Gemini</td>
</tr>
</table>

### Generation

- `TEMPERATURE` (default `1.2`)
- `ALLOW_OFFLINE_GENERATION` (dev only; affects `/generate` fallback, not prefetch)

### Prefetch

- `PREFETCH_DIR` (default `cache/prefetch`)
- `PREFETCH_BATCH_MIN`/`PREFETCH_BATCH_MAX` (default `5`/`10`)
- `PREFETCH_DELAY_MS` (delay when serving dequeued pages)
- `PREFETCH_LOW_WATER`, `PREFETCH_FILL_TO`, `PREFETCH_TOPUP_ENABLED`

### Dedupe

- `DEDUPE_ENABLED` (default `1`), `DEDUPE_MAX`, `DEDUPE_RECENT_FILE`

### Access / CORS / Rate Limiting

- `API_KEYS` (comma‑separated; if empty, local dev is open)
- `ALLOW_ORIGINS` (default `*`)
- `RATE_WINDOW_SECONDS`, `RATE_MAX_REQUESTS`

---

## Development

### Running Tests

```bash
pytest -q
```

The test suite covers:
- Prefetch queue (enqueue/dequeue, dedupe, fill clamping)
- Dequeue‑first generation
- Background top‑ups
- Status endpoints

> During tests, artificial delays and background workers are disabled for speed and determinism.

### Notes on Generation Rules

```
┌────────────────────────────────────────────────────────┐
│  Strictly Banned                                       │
├────────────────────────────────────────────────────────┤
│  • Passive visuals (gallery-only, slideshow)          │
│  • Randomizers‑only (no meaningful interaction)       │
│  • Menu‑only UIs                                       │
│  • Utility archetypes (calculators, clocks, to-dos)   │
│  • Quizzes                                             │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  Required for Approval                                 │
├────────────────────────────────────────────────────────┤
│  • Clear, immediate input → effect loops               │
│  • Obvious affordances                                 │
│  • At least two input modes (mouse/touch + another)   │
│  • Visible feedback for all interactions              │
│  • Responsiveness (low latency)                        │
└────────────────────────────────────────────────────────┘
```

Classic/trivial mini‑games are allowed but must still meet the interactivity bar (clear controls, visible feedback, responsiveness).

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Provider 429 rate limit | Back off; prefetch masks transient spikes |
| SSL/cert issues | Ensure system trust/certifi is up‑to‑date; avoid disabling verification globally |
| "Invalid JSON" from provider | The server extracts the first JSON object and validates/normalizes it; try again or adjust temperature/model |

---

## License

MIT — see `LICENSE`.
