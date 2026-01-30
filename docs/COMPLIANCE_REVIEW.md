# Compliance Review

Roulette can run a “review” step that checks and optionally corrects generated docs.

## Two Review Shapes

1. **Single-doc review**
   - Used when an individual generation needs review/correction.
2. **Batch review**
   - Used for burst followups and queue fills to reduce provider calls.
   - Batch size is controlled by `PREFETCH_REVIEW_BATCH` (default 3).

## Why Review Exists

- Generated HTML/JS is untrusted by default.
- Review acts as a guardrail: reject obvious policy violations and patch common correctness issues.
- It reduces broken outputs (missing elements, duplicated IDs, invalid JS, etc.).

## Fail-Open vs Fail-Closed

The pipeline supports fail-open:

- **Fail-open (recommended for UX):** if the reviewer is overloaded/timeouts, allow enqueue/serve anyway.
  - Controlled via `COMPLIANCE_FAIL_OPEN=1`.
- **Fail-closed (stricter):** if reviewer fails, drop those docs.

Fail-open is useful because reviewer providers (Gemini/OpenRouter) can return 503s, timeouts, or malformed JSON under load.

## Common Failure Modes Seen in Logs

- `ReadTimeout` to `generativelanguage.googleapis.com`: reviewer took too long.
- `HTTP 503`: model overloaded.
- “batch review response unparsable”: truncated JSON (usually the provider stopped early).

## Practical Recommendations

- Keep the batch size small (3–5) to reduce truncation risk.
- Consider a cheaper fallback reviewer (OpenRouter) when Gemini review is down.
- Treat review as a guardrail, not a hard dependency, unless you are willing to drop content aggressively.

