# LLM Orchestration

This system is designed to keep “novelty per dollar” high while staying robust to provider flakiness.

## Providers

Roulette supports multiple providers and uses fallbacks:

- **Gemini**: primary for burst generation (multimodal prompt support).
- **OpenRouter / Groq**: fallbacks for generation and/or review depending on config.

Exact models are configured via env vars (see `README.md` / `APP_OVERVIEW.md` and Render env vars).

## Burst Generation

Burst generation produces multiple websites in a single model call.

Rationale:
- Higher throughput per quota (especially for “limited requests/day” providers).
- Better queue refills: one user action can replenish multiple future sessions.

Tradeoffs:
- Parsing is harder (streamed arrays, partial truncations).
- Quality variance: the first site is user-facing immediately, followups are reviewed/queued.

## Category Rotation

The generator cycles through categories to avoid repeating the same “shape” every request:

- Interactive Entertainment / Web Toy
- Utility Micro-Tool
- Playable Simple Game
- Interactive Art
- Quizzes / Learning Cards

This encourages variety even when the user prompt is constant.

## Multimodal “Design Matrix”

When using Gemini, the generator can include an image (“design matrix”) to:

- Convey visual “vibes” without long text prompts
- Increase consistency of design language (palette/typography/layout)

## Why Outputs Can Still Repeat

Even with rotation, repetition can happen if:

- The prompt includes strong examples that anchor the model.
- Constraints narrow the space (no external assets, one-screen, NDW runtime).
- Dedupe resets on restart (file-backed seen history).

If repetition becomes a problem, the cheapest fix is usually: inject a few random constraints per call (input mode, layout archetype, mechanic type) and persist dedupe history (Redis).

