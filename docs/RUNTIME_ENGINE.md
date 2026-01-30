# Runtime Engine (NDW)

Roulette is not “just an LLM that spits out HTML”.

The *runtime engine* is the glue that makes wildly different generated pages behave consistently inside the same host app, across repeated "enter a new world" transitions.

This document is intentionally detailed. If you only read one thing about the codebase, read the “Lifecycle” and “NDW API surface” sections: they explain why the app stays stable even when it renders many different worlds in one session.

## What The Runtime Engine Provides

### 1) A stable JS API surface (NDW)

Generated pages are encouraged (and in many cases required) to use the NDW API instead of ad-hoc global code. This gives you:

- **Main loop control:** `NDW.loop(dt)` for predictable animation timing.
- **Pointer handling:** `NDW.onPointer(...)` and `NDW.pointer` for unified mouse/touch support.
- **Canvas helpers:** `NDW.makeCanvas(...)` so the host can standardize DPI sizing and cleanup.
- **Particles/helpers/RNG:** shared utilities so models don’t re-implement brittle code repeatedly.

This is what turns “random HTML” into a platform.

#### NDW API surface (practical summary)

The engine works best when generated pages treat NDW as their runtime:

- **`NDW.loop(fn)`**
  - Your world’s update loop. The host can stop it during teardown to prevent background CPU usage.
- **`NDW.onPointer(fn)` + `NDW.pointer`**
  - Consistent pointer state across devices; enables “read pointer inside loop” patterns without wiring events per page.
- **`NDW.makeCanvas({ parent, width, height })`**
  - Standardized canvas creation + scaling. This avoids a common class of blurry/incorrect DPI canvases.
- **`NDW.utils.rng(seed)`**
  - Reproducibility: two runs with the same seed can behave consistently (useful for debugging and dedupe).
- **`NDW.particles.*` (if present)**
  - A common “visual feedback” system. It keeps effects consistent and reduces copy-paste JS.

Even when a model emits raw JS, keeping these primitives stable reduces the chance that “one world” breaks the host for all subsequent worlds.

### 2) Sandbox + lifecycle management

Roulette repeatedly mounts and unmounts entire experiences in one session. The engine therefore:

- Renders each doc under a controlled root (e.g. `#ndw-sandbox`) to limit CSS bleed.
- Runs cleanup between worlds (stop loops, remove listeners, clear timers) so old worlds don’t keep running.
- Removes landing-only effects (tunnel, overlays, blobs) so the generated page can own the screen.

#### Lifecycle: mount -> run -> teardown (why it matters)

In a typical “single page demo,” you can leak event listeners and timeouts because the user refreshes eventually.

Roulette is different: it is a long-lived controller that swaps entire apps repeatedly. Without lifecycle control, you get:

- stacked event handlers (click once, it fires 3 times)
- runaway `setInterval`/`requestAnimationFrame` loops
- memory growth (detached DOM nodes retained by closures)
- CSS bleed (one page changes `body` styles for the next page)

So the host treats each generated page as a *world* with a lifecycle:

1. **Prepare:** close shutter, clear runtime root, freeze/cleanup previous world.
2. **Mount:** inject new DOM, apply minimal host framing.
3. **Run:** NDW loop + handlers operate normally.
4. **Teardown:** stop loops, remove listeners, clear timers, wipe root.

This is the practical difference between “LLM output” and “platform that can run hundreds of outputs.”

### 3) Host-owned transitions

Transitions (like the shutter) are not aesthetic-only. They prevent:

- flashing intermediate blank states while DOM is replaced
- showing partially-initialized apps
- "layout thrash" during heavy DOM swaps

The key point: transitions are owned by the host, not the model.

#### Shutter in particular

The shutter gives you a consistent visual boundary between worlds:

- the host can do destructive DOM operations behind the shutter
- the user doesn’t see unstyled intermediate layouts
- you can keep the landing UI and runtime UI as two modes without jarring jumps

### 4) Compatibility guardrails

To keep outputs renderable and reliable:

- External assets may be rewritten or stripped (no CDNs required for core vendor libs).
- JS syntax checks and basic heuristics help prevent obviously broken pages from entering the queue.
- Compliance review (optional/fail-open) can correct common issues at scale.

## What This Enables (At the Product Level)

The point of having a runtime engine is to make these UX/product goals achievable:

- **Repeatable world switching:** enter a new site, then another, without refreshing the browser tab.
- **Consistent interaction shape:** even when the content varies wildly, it still behaves like “a Roulette world.”
- **Lower perceived latency:** prefetch + shutter + predictable mounting reduces the “blank screen” feeling.
- **Operational resilience:** provider timeouts/503s don’t have to break the experience; the queue and fallbacks can absorb it.

The runtime engine is the component that makes these outcomes realistic in a single, long-lived session.

## Mental Model

Think of Roulette as:

- an app shell (landing + router + transitions)
- a queue (prefetch)
- a compiler-ish layer (normalize/sanitize/review)
- a game-engine-ish runtime (NDW)

That is why the project feels like a platform rather than a single demo page.

## Extension Points (Where To Add Capability Safely)

If you want to expand what the engine can host, the safest places to invest are:

- **NDW primitives** (add small, well-tested helpers rather than letting models re-invent them)
  - ex: audio helpers, physics helpers, UI widgets that are safe-by-default
- **Cleanup hooks** (make it easy for worlds to register teardown work)
  - ex: a standard `NDW.registerCleanup(fn)` so models don’t forget to unsubscribe
- **Asset policy** (keep a predictable set of vendor scripts available locally)
  - tailwind-play / gsap / lucide are examples of “available primitives”
- **Validation** (fast checks that catch obvious breakage before users see it)
  - ex: JS syntax compile check, DOM selector sanity checks, optional review step

## Debugging A World

Useful tactics when a generated world misbehaves:

- Toggle the JSON overlay (“Peek under the hood”) to see the exact payload that produced the page.
- Use a fixed seed (when supported) to reproduce the same behavior repeatedly.
- Confirm teardown happens (no duplicate variables/errors on subsequent renders is a strong signal cleanup is working).
