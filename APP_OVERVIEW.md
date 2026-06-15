# Non-Deterministic Website Overview

Roulette is a non-deterministic website generator for polished, one-off interactive web experiences. Users do not prompt websites into existence. They enter a queue-backed stream of random pages and can jump to the next world.

For deeper detail, use:

- `docs/ARCHITECTURE.md` for the full system map.
- `docs/PREMIUM_QUEUE.md` for queue behavior and counter semantics.
- `docs/LLM_ORCHESTRATION.md` for Gemini planner/build routing.
- `docs/EXPERIENCE_GRAMMAR.md` for visitor-role and primary-loop requirements.
- `docs/REDIS_DIVERSITY_TRACKING.md` for descriptor storage and quality-diversity steering.

## Current Product Path

1. The landing tunnel displays preview tiles from the shared queue.
2. Clicking a preview consumes that queued page and renders it in the iframe sandbox.
3. Pressing Generate first tries the queue.
4. If the queue is empty, the backend starts one Gemini streaming burst and serves the first locally valid page.
5. Later valid pages from the same stream can be drained into the queue for future users.
6. The served page increments the public `Sites generated` counter.
7. After serving, Redis can record compact descriptors, quality-diversity counters, fingerprints, and generation events.

There is no public mode split. User-facing generation is only.

## Generation Model

The generator uses Gemini as the primary provider:

- Planner: chooses semantic anchors, experience cell, visitor role, first interaction, primary loop, visual axes, and local design-kit assets.
- Builder: outputs raw HTML in a final fenced `html` block after a single-call self-review sequence.
- Backend gates: normalize HTML, rewrite unsafe assets, run preflight/static checks, score visual richness, score experience quality, and dedupe.

## Experience Grammar

Every strong generated site should answer:

- What is the visitor’s role?
- What should the visitor do first?
- What visibly changes after that action?
- What state changed?
- Why would the visitor keep interacting?

This is tracked in the plan and evaluated by `api/generation/experience_quality.py`.

## Queue And Redis

`api/prefetch.py` is still the queue implementation name, but the public lane is the shared queue.

Redis is used for production state:

- queued docs and preview tokens
- served-site descriptors
- quality-diversity counters
- event streams
- fingerprint dedupe
- counters and rate limits when configured

Redis is not used as a giant prompt memory. The model receives positive targets like `museum_exhibit:scan_to_discover`, not long lists of prior websites to avoid.

## Runtime

Generated pages render inside a full-screen iframe sandbox. Replacing the iframe destroys old timers, WebGL contexts, styles, and event listeners without relying on generated code cleanup.

The parent app keeps host controls, counter display, JSON overlay, and Generate behavior outside the generated page. Generated pages can request the next world through `postMessage`.

## Operational Defaults

For low-cost Render deployments:

- keep startup prewarm disabled
- keep background top-up disabled unless you have rate-limit headroom
- use Redis if queue persistence matters across restarts
- run review-pack evals in fixture mode for harness checks and live mode only when intentionally spending Gemini quota

Key commands:

```bash
npm run build
pytest -q
python3 scripts/run_generation_review_pack.py --fixture-mode --no-screenshots --out /tmp/ndw_eval_harness
```
