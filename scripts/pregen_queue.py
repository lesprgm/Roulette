#!/usr/bin/env python3
"""
Prefetch queue pre-generation helper.

Usage (local or from your laptop against prod):
  NDW_URL="https://your-app.onrender.com" \
  NDW_API_KEY="your-key" \
  NDW_TARGET=500 \
  NDW_BATCH=20 \
  NDW_HTTP_TIMEOUT=1800 \
  NDW_ONCE=1 \
  NDW_BRIEF="" \
  python scripts/pregen_queue.py
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple


def _post_json(url: str, payload: Dict[str, Any], api_key: str | None) -> Tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("content-type", "application/json")
    if api_key:
        req.add_header("x-api-key", api_key)
    # /prefetch/fill can take a while (generation + batch review).
    # Default is intentionally high; override per-run with NDW_HTTP_TIMEOUT.
    http_timeout = int(os.getenv("NDW_HTTP_TIMEOUT", "1800"))
    try:
        with urllib.request.urlopen(req, timeout=http_timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:  # network or timeout
        return 0, str(e)


def main() -> None:
    base_url = os.getenv("NDW_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key = os.getenv("NDW_API_KEY", "").strip() or None
    target = int(os.getenv("NDW_TARGET", "500"))
    batch = int(os.getenv("NDW_BATCH", "20"))
    brief = os.getenv("NDW_BRIEF", "").strip()
    run_once = os.getenv("NDW_ONCE", "0").strip() not in ("", "0", "false", "False")

    sleep_ok = int(os.getenv("NDW_SLEEP_OK", "2"))
    sleep_429 = int(os.getenv("NDW_SLEEP_429", "3600"))
    sleep_503 = int(os.getenv("NDW_SLEEP_503", "1800"))
    sleep_err = int(os.getenv("NDW_SLEEP_ERR", "60"))

    endpoint = f"{base_url}/prefetch/fill"
    queue_size: int | None = None
    attempts = 0

    if not api_key:
        print("Warning: NDW_API_KEY is not set. If API_KEYS is configured on the server, this will 401.")

    while True:
        if queue_size is not None and queue_size >= target:
            print(f"Done. queue_size={queue_size} target={target}")
            break

        payload: Dict[str, Any] = {"count": batch}
        if brief:
            payload["brief"] = brief

        attempts += 1
        status, body = _post_json(endpoint, payload, api_key)
        if status == 429:
            print(f"[{attempts}] 429 rate limited. Sleeping {sleep_429}s.")
            time.sleep(sleep_429)
            continue
        if status == 503:
            print(f"[{attempts}] 503 LLM unavailable. Sleeping {sleep_503}s.")
            time.sleep(sleep_503)
            continue
        if status in (401, 403):
            print(f"[{attempts}] auth failed (status={status}). Check NDW_API_KEY.")
            time.sleep(sleep_err)
            continue
        if status == 0:
            print(f"[{attempts}] network error: {body}. Sleeping {sleep_err}s.")
            time.sleep(sleep_err)
            continue
        if status >= 400:
            print(f"[{attempts}] error status={status} body={body[:300]}")
            time.sleep(sleep_err)
            continue

        try:
            data = json.loads(body)
        except Exception:
            print(f"[{attempts}] invalid JSON response: {body[:300]}")
            time.sleep(sleep_err)
            continue

        queue_size = int(data.get("queue_size") or 0)
        added = int(data.get("added") or 0)
        print(f"[{attempts}] added={added} queue_size={queue_size} target={target}")

        if queue_size >= target:
            print(f"Done. queue_size={queue_size} target={target}")
            break
        if run_once:
            print("NDW_ONCE=1 set; stopping after one request.")
            break
        time.sleep(sleep_ok)


if __name__ == "__main__":
    main()
