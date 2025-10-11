Non‑Deterministic Website
=========================

Generate a brand-new interactive site every time you ask. The FastAPI backend orchestrates Groq/OpenRouter LLMs, normalizes the response into rich HTML or NDW snippets, and the TypeScript front-end renders the result directly into the page—no iframes, no reloads.

## Demo

[🌠 Demo screenshot (add link here)](https://example.com/path-to-demo-image)

> Replace the URL above with your production screenshot when it’s ready.

## Highlights

- **Two rendering modes:** full HTML pages or compact `ndw_snippet_v1` apps powered by the shared NDW runtime.
- **LLM orchestration:** Groq primary with configurable OpenRouter fallback, automatic retries, and duplication checks.
- **Prompt guardrails:** strict JSON schema, dt usage rules, category rotation, instructions/context requirements, and canvas safety nets.
- **Prefetch engine:** background top-ups keep generations snappy while dedupe stops repeats.
- **UX polish:** floating summon button, generation counter, error overlays, and automatic theme adoption from generated output.
- **End-to-end tests:** pytest suite covering prompt expectations, runtime validation, schema conformance, and renderer behavior.

## Architecture

```mermaid
flowchart TD
    subgraph Client
        UI[Landing UI & Controls]
        Renderer[Renderer (full HTML / NDW runtime)]
    end

    subgraph Backend
        API[FastAPI
        /generate]
        Orchestrator[LLM Orchestrator
        (Groq ▶ OpenRouter)]
        Normalizer[Shape Normalizer
        & Validator]
        Prefetcher[Prefetch Queue
        + Dedupe]
        Metrics[(Metrics Store)]
    end

    UI -->|POST /generate| API
    API --> Orchestrator --> Normalizer --> Renderer
    API <-->|queue refill| Prefetcher
    Prefetcher --> Orchestrator
    Renderer -->|UX updates| UI
    UI -->|GET /metrics/total| Metrics --> UI
    Normalizer -->|ndw_snippet_v1| Renderer
    Normalizer -->|full_page_html| Renderer
```

### Component rundown

| Layer | Responsibilities |
|-------|------------------|
| **Browser UI (`templates/index.html`, `static/ts-src/app.ts`)** | Handles user prompts, seeds, status overlays, and renders generated documents. |
| **NDW Runtime (`static/ts-src/ndw.ts`)** | Tiny game/visual library providing `loop(dt)`, input helpers, RNG utilities, and canvas helpers with validation guards. |
| **FastAPI Backend (`api/main.py`)** | Exposes `/generate`, `/metrics`, `/prefetch`, `/llm/status`; manages lifespan hooks and background tasks. |
| **LLM Client (`api/llm_client.py`)** | Builds prompt, enforces schema, rotates categories, and retries across Groq/OpenRouter. |
| **Prefetch & Dedupe (`api/prefetch.py`, `api/dedupe.py`)** | Warms a queue of ready-to-serve pages and prevents near-duplicate outputs. |

## Runtime & Prompt Guardrails

The latest prompt instructions (see `_PAGE_SHAPE_HINT`) enforce:

- Use `NDW.loop((dt) => {...})` with the provided millisecond delta—no manual `Date.now()` tracking.
- Register `NDW.onKey` / `NDW.onPointer` once, outside the loop, and avoid chaining `.NDW` on other expressions.
- Provide HTML-based instructions or descriptive context so players know how to interact.
- Rotate genres and mediums so the generator doesn’t spam Asteroids clones.
- For websites, output multi-section layouts with headings, copy, CTAs, and visuals—not just a fullscreen canvas.
- NDW snippets must clear the canvas each frame, initialize state before the loop, and use the shared RNG helper correctly.

## API Surface

| Endpoint | Description |
|----------|-------------|
| `GET /` | Landing page + summon controls. |
| `POST /generate` | Returns full-page HTML or `ndw_snippet_v1` JSON. |
| `POST /generate/stream` | NDJSON streaming version (metadata then document). |
| `GET /metrics/total` | Total number of conjured experiences. |
| `GET /prefetch/status`, `POST /prefetch/fill` | Inspect or manually refill the prefetch queue. |
| `GET /llm/status`, `GET /llm/probe` | Provider diagnostics. |

Environment configuration (see `.env.sample` if present):

| Variable | Purpose | Default |
|----------|---------|---------|
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODEL` | Primary LLM provider credentials & models. | `meta-llama/llama-4-scout-17b-16e-instruct`, fallback `llama-3.1-8b-instant` |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `FORCE_OPENROUTER_ONLY` | Optional fallback provider. | `google/gemma-3n-e2b-it:free` |
| `LLM_MAX_TOKENS`, `GROQ_MAX_TOKENS`, `OPENROUTER_MAX_TOKENS` | Output limits. | `15000` |
| `LLM_TIMEOUT_SECS` | Request timeout seconds. | `75` |
| `PREFETCH_DIR`, `PREFETCH_LOW_WATER`, `PREFETCH_FILL_TO`, `PREFETCH_TOPUP_ENABLED` | Prefetch queue tuning. | reasonable defaults |
| `ALLOW_OFFLINE_GENERATION` | Dev/test stub mode for `/generate`. | Disabled |

## Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install

# Build or watch TypeScript + CSS
npm run build      # once
npm run watch      # dev loop (Ctrl+C to stop)

# Start API
uvicorn api.main:app --reload

# Visit http://localhost:8000
```

Run the full validation suite:

```bash
pytest
```

## Deploying to Render

This repo ships with [`render.yaml`](render.yaml) so you can spin up a fully managed Render Web Service:

1. Push the latest code to GitHub.
2. In Render, click **New > Blueprint** and point it at your repo.
3. Review the generated service (plan defaults to the Free tier). The blueprint:
    - Installs Python deps, installs Node deps, and runs `npm run build` during the build step.
    - Starts FastAPI via `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.
4. Add your secrets under **Environment** (at minimum `GROQ_API_KEY` and `OPENROUTER_API_KEY`).
5. Deploy. Render will auto-redeploy on subsequent pushes to the tracked branch.

Need additional env vars? Edit `render.yaml` or add them in the Render dashboard.

## Testing & Quality Gates

The pytest collection (70+ tests) verifies:

- Prompt guidance strings (dt usage, category rotation, instructions, etc.).
- NDW runtime safety (dt propagation, error overlays, canvas helpers).
- Schema normalization, dedupe, provider fallback, and renderer behavior.
- DOM rendering of both full-page HTML and snippet documents.

## Roadmap

- Expose a lightweight metrics dashboard.
- Explore WebGL helpers inside NDW runtime.
- Add automated visual diffing for generated pages.
- Offer downloadable generation history.

## License

MIT