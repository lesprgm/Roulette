## Non-Deterministic Website – Deep-Dive Architecture Guide

This document explains how the “Roulette” experience is assembled, what guarantees each layer provides, and which environment knobs influence behaviour. Use it as a companion to the code when you need to trace a request or reason about production configuration.

---

### 1. Startup Sequence

1. **Dotenv loading** – `api/__init__.py` reads `.env` (unless `PYTEST_CURRENT_TEST` is set) without clobbering existing OS variables. Everything that follows assumes those variables are already in `os.environ`.
2. **FastAPI lifespan hook** – When Uvicorn starts, the `lifespan` context manager in `api/main.py` runs:
   - `_prefill_prefetch_queue()` generates `PREFETCH_PREWARM_COUNT` documents up front, *blocking startup* until it finishes. If the configured LLM credentials are missing or `llm_status()` reports no token, the prewarm quietly skips.
   - `_prefetch_topup_enabled()` checks `PREFETCH_TOPUP_ENABLED`. When true *and* the LLM is available, a daemon thread is spawned to keep the prefetch queue above water in the background.
   - **Production note:** Render now pins `PREFETCH_PREWARM_COUNT=0` and `PREFETCH_TOPUP_ENABLED=0` so cold starts and idle periods stop consuming LLM tokens. Re-enable only if you truly need a warm cache and have rate limit headroom.
3. **Middleware & static assets** – CORS is configured from `ALLOW_ORIGINS`; `/static` mounts if the folder exists; the request middleware adds a UUID-based `request_id` and prints structured latency logs to stdout (`INFO:root:rid=...`).

Key takeaway: large values for `PREFETCH_PREWARM_COUNT` can delay boot long enough for Render/hosts to time out. When rolling out, prefer `0` or a small number unless you have high rate limits.

---

### 2. Request Lifecycle (`/generate`)

1. **Rate limiting & identity**
   - `require_api_key` checks `API_KEYS`. If absent, auth is effectively open (dev default).
   - `_safe_rate_check` picks Redis + `api/redis_ratelimit.py` when `REDIS_URL` is defined, otherwise falls back to the in-process limiter (`api/ratelimit.py`). Both enforce `RATE_MAX_REQUESTS` requests per `RATE_WINDOW_SECONDS`.
   - Responses always include `X-RateLimit-Remaining` and `X-RateLimit-Reset`; 429 payloads add `Retry-After`.

2. **Prefetch fast path**
   - `prefetch.dequeue()` delivers the oldest JSON file from `PREFETCH_DIR` (`cache/prefetch` by default).
   - When served, the handler optionally sleeps `PREFETCH_DELAY_MS / 1000` to pace delivery (defaults to 3000 ms but drops to zero during pytest).
   - Once a prefetched page is used, the response is returned immediately and a background task checks queue depth: if `prefetch.size() <= PREFETCH_LOW_WATER` (default 55), `_top_up_prefetch` is scheduled.

3. **LLM fallback path**
   - If the queue is empty, `llm_generate_page` is called synchronously.
   - Offline mode: if the LLM is unavailable and `ALLOW_OFFLINE_GENERATION` is truthy, a deterministic canned experience is returned (see `generate_endpoint` for markup).
   - Successful generations increment the total counter (`api/counter.py`), which writes to Redis when configured, otherwise `cache/counter.json`.

---

### 3. Prefetch Subsystem (Always Be Stocked)

- **Storage** – `api/prefetch.py` keeps FIFO ordering by naming files with `time.time_ns()` prefixes. Writes go through a `.tmp` file then `Path.replace()` for durability.
- **Dedupe** – Every enqueue computes a signature via `api/dedupe.py`. If the signature already exists and the queue is non-empty, the item is skipped. Signatures persist in `DEDUPE_RECENT_FILE` (`cache/seen_pages.json`) with a max size of `DEDUPE_MAX` (default 200).
- **Top-up loop** (`_top_up_prefetch`)
  - Reads current queue size and computes a target: `max(min_fill, _prefetch_target_size(current))`.
  - `_prefetch_target_size` raises the target to `PREFETCH_FILL_TO` (defaults to `max(PREFETCH_BATCH_MAX, PREFETCH_LOW_WATER)`, so 55 with stock settings) whenever the queue dips below `PREFETCH_LOW_WATER`.
  - Generation now runs through a bounded worker pool (`PREFETCH_MAX_WORKERS`, default 2). The dispatcher submits LLM jobs until `prefetch.size() + inflight < target`, then waits for completions. Results arriving after the queue reaches the target are discarded instead of written, so the cache never overfills even if threads finish late.
  - Each successful doc is enqueued immediately (skipping duplicates via `dedupe`) and batched for review. Prefetch generation no longer blocks on Gemini; `_schedule_prefetch_review` processes files asynchronously, with batches of up to `PREFETCH_REVIEW_BATCH` (default 3) flowing through the Gemini reviewer. Timeouts or transient failures re-queue the affected files up to three times before giving up.

Operational tips:
- Set `PREFETCH_TOPUP_ENABLED=0` in environments with strict rate limits or when running tests manually.
- Combine a small `PREFETCH_PREWARM_COUNT` with a relatively high `PREFETCH_LOW_WATER` so steady-state traffic rarely waits for the LLM.
- Tune `PREFETCH_MAX_WORKERS` alongside provider rate limits; higher values refill faster but increase concurrent LLM calls.

---

### 4. LLM Orchestration (`api/llm_client.py`)

- **Category rotation** – `_CATEGORY_ROTATION_NOTES` defines five prompts (Interactive Entertainment, Utility Micro-Tools, Generative Randomizers, Interactive Art, Quizzes/Learning Cards). `_next_category_note` uses a per-user ring buffer with thread locking so each caller walks the themes in order, keeping output varied even across concurrent requests.
- **Provider order & fallbacks**
  1. Gemini (`GEMINI_GENERATION_MODEL`). The primary generation model.
  2. OpenRouter (`OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODEL_1`, `_2`). Retries are rate-limited using exponential backoff (`OPENROUTER_BACKOFF_*`).
  3. Groq (`GROQ_MODEL`, `GROQ_FALLBACK_MODEL`). Requests enforce `LLM_TIMEOUT_SECS`, `LLM_MAX_TOKENS`, and provider-specific JSON output hints.
  4. If all providers fail, a `{"error": "Model generation failed"}` payload is returned; the HTTP status remains 200 so the front-end can display a friendly message.
- **Normalization pipeline**
  - `_json_from_text` extracts JSON from completions that may have stray prose.
  - `_normalize_doc` standardises to one of the supported shapes and guarantees required properties exist.
  - `_collect_js_blocks` + `_first_js_syntax_error` use Node.js (`node -e`) to verify inline scripts compile, while additional static heuristics ensure DOM selectors match real nodes and guard against obvious low-contrast CSS.
- **Compliance review**
  - Individual documents: `_call_gemini_review` receives the draft, the category note, and the user brief. JS syntax validation now runs *before* Gemini is called; only syntactically sound docs go to the reviewer, and the corrected payload is validated again afterward.
  - Prefetch review: completed JSON files land on an asynchronous queue powered by `_schedule_prefetch_review`. Worker threads pick up batches, call `_call_gemini_review_batch`, rewrite or discard docs as needed, and retry failures with short delays (up to three passes). A warning log records batches that exceeded the retry budget so operators can revisit them manually.
- **Testing shortcuts**
  - When `PYTEST_CURRENT_TEST` is set and `RUN_LIVE_LLM_TESTS` is false, `_testing_stub_enabled` switches the module to a deterministic stub so unit tests never hit live providers.

---

### 5. Front-End Contract & Rendering

- **Payload formats**
  1. `{"kind": "full_page_html", "html": "<!doctype html>..."}` – entire HTML document.
  2. `{"kind": "ndw_snippet_v1", "html": "...", "css": "...", "js": "...", ...}` – widget embedded into the NDW shell.
  3. `{"components": [...], "layout": {...}, "palette": {...}}` – component manifest for the React/TypeScript front-end.
- **NDW runtime expectations**
  - Scripts must rely on `NDW.loop`, `NDW.makeCanvas`, `NDW.onPointer`, etc., instead of raw `requestAnimationFrame`.
  - Inline external resources (no remote fonts or fetch calls).
  - Maintain accessibility: labelled controls, high-contrast palettes, no duplicated IDs.

The TypeScript app (`static/ts-src/app.ts`) receives the API response, mounts the appropriate renderer, and ensures each experience is sandboxed under `#ndw-sandbox` to avoid global CSS leakage.

---

### 6. Metrics & Observability

- **Usage counter** – `api/counter.py` exposes `counter.get_total()` via `/metrics/total`. It writes to Redis when `REDIS_URL` is set, falling back to a local JSON file. Redis reads/writes include timeouts (`REDIS_COUNTER_TIMEOUT`) so transient failures do not block the request.
- **Logging**
  - HTTP middleware prints structured request info to stdout.
  - The LLM client emits `WARNING` logs describing provider order, fallback decisions, rate-limit backoffs, and schema issues.
  - Prefetch routines log queue size transitions (`prefetch.top_up`, `prefetch.fill`, `prefetch.prewarm`).
- **Health checks**
  - `/health` returns `{"status": "ok"}` with no dependencies.
  - `/llm/status` reveals the provider currently active, whether a token is present, and if Gemini review is live.
  - `/llm/probe` performs a lightweight availability check and returns `{ok: bool, using: "openrouter|groq|stub"}`.

---

### 7. Configuration Cheat Sheet

| Concern | Key Variables | Notes |
|---------|---------------|-------|
| LLM providers | `GEMINI_GENERATION_MODEL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL` | Gemini is first; set `FORCE_OPENROUTER_ONLY=1` to skip Groq/Gemini fallbacks. |
| Compliance review | `GEMINI_REVIEW_ENABLED`, `GEMINI_API_KEY`, `GEMINI_REVIEW_MODEL` | When disabled, compliance hooks simply return `None`. |
| Prefetch | `PREFETCH_TOPUP_ENABLED`, `PREFETCH_PREWARM_COUNT`, `PREFETCH_LOW_WATER`, `PREFETCH_FILL_TO`, `PREFETCH_DELAY_MS`, `PREFETCH_BATCH_MIN/MAX`, `PREFETCH_REVIEW_BATCH`, `PREFETCH_DIR` | High `PREFETCH_PREWARM_COUNT` + strict rate limits can stall boot. |
| Deduping | `DEDUPE_ENABLED`, `DEDUPE_RECENT_FILE`, `DEDUPE_MAX` | Dedupe writes on every enqueue; consider a shared store for multi-instance deployments. |
| Rate limit | `API_KEYS`, `RATE_MAX_REQUESTS`, `RATE_WINDOW_SECONDS`, `REDIS_URL` | Without `API_KEYS`, generation is open to the world. |
| Metrics | `REDIS_COUNTER_KEY`, `REDIS_COUNTER_TIMEOUT`, `COUNTER_FILE` | Redis writes mirror to the local file for resiliency. |
| Offline/dev | `ALLOW_OFFLINE_GENERATION`, `PYTEST_CURRENT_TEST`, `RUN_LIVE_LLM_TESTS` | Offline mode serves a canned app; tests disable background threads automatically. |

---

### 8. Failure Modes & Operational Guidance

- **Provider rate limits** – The OpenRouter client applies exponential backoff and logs “OpenRouter rate limited; backing off…” messages. Sustained 429s inside `_prefill_prefetch_queue` will keep the lifespan hook alive, preventing the HTTP server from listening. Mitigation: lower `PREFETCH_PREWARM_COUNT` or temporarily disable prewarm (`0`).
- **Prefetch starvation** – If Gemini rejects many prefetched docs, the top-up loop can spin without increasing queue size. Monitor logs for repeated “generation returned error” / “continuing refill” lines. Consider counting rejections toward `failures` if this becomes common.
- **Redis outages** – Rate limiting and counters fall back to in-process implementations; logs warn but requests continue. Restarting the process reinitialises Redis clients automatically.
- **File-system constraints** – The project expects write access to `cache/`. On platforms with ephemeral storage (Render free tier), the queue and counters reset on each deploy; attach a persistent disk if durability matters.
- **Concurrency** – Background threads (`_top_up_prefetch`) and request handlers both touch the prefetch queue and dedupe store. There is no file locking beyond Python’s GIL for JSON reads/writes; in multi-process setups, move to a shared datastore.
- **Quality drift** – Even with Gemini review, subtle animation bugs can slip through (e.g., canvas content faded to transparency). Consider adding automated heuristics or lightweight simulations to lint generated JS/HTML before enqueueing, especially for canvas-heavy categories.

---

### 9. Local Development Tips

1. `uvicorn api.main:app --reload` – hot-reloads API changes; prefetch delay is disabled automatically under pytest, but not during local manual runs.
2. `npm install && npm run dev` – recompiles the UI (if using the TypeScript frontend) and proxies to the API.
3. ENV hygiene – copy `.env.example` (if available) or create `.env` with the variables described above. Avoid committing live API keys.
4. Tests – `pytest` uses stubbed LLM responses, disables prefetch top-up, and relies on temporary directories for queue/dedupe files.

---

### 10. Quick Reference for New Contributors

- **Main entry points** – `api/main.py` (FastAPI app), `api/llm_client.py` (generation + compliance), `static/ts-src/app.ts` (frontend).
- **Background jobs** – Prefetch thread (daemon) + on-demand background tasks via FastAPI’s `BackgroundTasks`.
- **Extending categories** – Update `_CATEGORY_ROTATION_NOTES`, provide new inspirational examples, and ensure the frontend can render the novel content.
- **Deploying** – The provided `render.yaml` installs Python + Node dependencies, builds the frontend, and launches `uvicorn`. Remember to set runtime env vars (`PREFETCH_TOPUP_ENABLED`, provider keys, Redis URL) via Render’s dashboard or infrastructure pipeline.

With these pieces in mind you can reason about why generation sometimes feels instant (prefetch), why logs mention category assignments (prompt rotation), and how compliance corrections end up in cached files. The overall system is deliberately modular: each component can be tuned—or disabled—via environment variables without modifying code.
