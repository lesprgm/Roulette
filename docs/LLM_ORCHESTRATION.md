# LLM Orchestration

This system is designed to keep “novelty per dollar” high while staying robust to provider flakiness.

## Providers

Roulette supports multiple providers and uses fallbacks:

- **Gemini**: primary for both user-facing lanes.
  - `fast`: Gemini-first shared queue and burst generation.
  - `premium`: Gemini premium planner + builder path feeding a smaller shared premium queue.
- **OpenRouter / Groq**: emergency fallback only for `fast` when Gemini fast generation fails.

Exact models are configured via env vars (see `README.md` / `APP_OVERVIEW.md` and Render env vars).

## Fast Lane

The fast lane is the cheap, high-throughput path:

- Prefer the shared fast queue.
- If the queue is empty, call the Gemini fast generator.
- The Gemini fast generator uses a single call path tuned for throughput and diversity.
- Only if Gemini fast fails completely do secondary providers get a chance.

Fast generations are still random. The user is not steering toward a specific site.

## Premium Lane

The premium lane is also random, but it is scarcer and more art-directed:

- Prefer the shared premium queue.
- If the premium queue is empty, generate a small premium batch.
- Serve the first acceptable premium page immediately.
- Enqueue the remaining approved premium pages for later premium requests.
- Premium serving is quota-limited per user.

Premium uses Gemini-only generation with a planner + builder structure rather than the fast one-shot path.

## Burst Generation

Burst generation still matters because it produces multiple websites in a single model call for the fast lane.

Rationale:
- Higher throughput per quota (especially for “limited requests/day” providers).
- Better queue refills: one user action can replenish multiple future sessions.

Tradeoffs:
- Parsing is harder (streamed arrays, partial truncations).
- Quality variance: the first site is user-facing immediately, followups are reviewed/queued.

## Diversity Steering

Older category rotation was replaced by cheaper orthogonal assignment axes in the fast path:

- layout archetype
- motion archetype
- visual density
- interaction model
- rendering mode
- tone

Premium uses a small structured plan over similar axes, plus local design-kit keys.

## Why Outputs Can Still Repeat

Even with axis steering and dedupe, repetition can still happen if:

- Constraints narrow the space (no external assets, host runtime compatibility, compliance/preflight).
- Dedupe resets on restart when Redis is unavailable.
- The premium queue is small and currently optimized for quality more than total stylistic spread.

If repetition becomes a problem, the cheapest fixes are usually:

- improve the fast assignment packs
- expand the local design kit
- keep dedupe persisted in Redis
- review queue ranking and diversity bucketing, not just prompts
