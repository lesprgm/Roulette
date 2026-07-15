import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api import counter, prefetch
from api.auth import extract_client_key, optional_api_key, require_api_key
from api.generation import premium_service
from api.routes import shared
from api.settings import SETTINGS


router = APIRouter()
log = logging.getLogger(__name__)

_preview_cache: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
_preview_cache_lock = threading.Lock()


class QueuePreview(BaseModel):
    id: str
    title: str
    category: str
    vibe: str
    created_at: float


class PrefetchRequest(BaseModel):
    brief: str = Field("", description="Optional brief to bias generation; may be empty")
    count: int = Field(10, description="How many pages to prefetch (clamped to 5-20)")


def _cached_previews(limit: int) -> Optional[List[Dict[str, Any]]]:
    ttl = SETTINGS.runtime.prefetch_preview_cache_ttl
    if os.getenv("PYTEST_CURRENT_TEST") or ttl <= 0:
        return None
    with _preview_cache_lock:
        cached = _preview_cache.get(limit)
        if cached and time.time() - cached[0] <= ttl:
            return cached[1]
    return None


def _cache_previews(limit: int, items: List[Dict[str, Any]]) -> None:
    ttl = SETTINGS.runtime.prefetch_preview_cache_ttl
    if os.getenv("PYTEST_CURRENT_TEST") or ttl <= 0:
        return
    with _preview_cache_lock:
        _preview_cache[limit] = (time.time(), items)


@router.get("/api/prefetch/previews", response_model=List[QueuePreview])
def get_prefetch_previews(limit: int = 20) -> List[Dict[str, Any]]:
    cache_key = int(limit or 0)
    cached = _cached_previews(cache_key)
    if cached is not None:
        return cached
    items = prefetch.peek(limit=limit, lane="premium")
    _cache_previews(cache_key, items)
    return items


@router.get("/api/premium/previews", response_model=List[QueuePreview])
def get_premium_previews(
    limit: int = 20, api_key: str = Depends(optional_api_key)
) -> List[Dict[str, Any]]:
    shared.require_admin_or_dev(api_key)
    return prefetch.peek(limit=limit, lane="premium")


@router.get("/api/prefetch/{item_id}")
def get_prefetch_entry(item_id: str) -> Dict[str, Any]:
    entry = prefetch.take(item_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Prefetch entry not found or already served.")
    try:
        counter.increment(1)
    except Exception:
        pass
    shared.record_user_visible_serve(entry)
    return entry


@router.get("/prefetch/status")
def prefetch_status() -> Dict[str, Any]:
    try:
        queue_size = prefetch.size()
    except Exception:
        queue_size = 0
    try:
        premium_size = prefetch.size("premium")
    except Exception:
        premium_size = 0
    return {
        "size": queue_size,
        "premium_size": premium_size,
        "premium_queue_enabled": premium_service.premium_queue_enabled(),
        "premium_low_water": premium_service.PREMIUM_LOW_WATER,
        "premium_fill_to": premium_service.PREMIUM_FILL_TO,
        "premium_batch_size": premium_service.PREMIUM_BATCH_SIZE,
        "premium_topup_enabled": premium_service.PREMIUM_TOPUP_ENABLED,
        "stream_keepalive_seconds": premium_service.STREAM_KEEPALIVE_SECONDS,
        "dir": str(prefetch.PREFETCH_DIR),
        "premium_dir": str(getattr(prefetch, "PREMIUM_PREFETCH_DIR", prefetch.PREFETCH_DIR)),
        "backend": prefetch.backend(),
        "redis_disabled_reason": getattr(prefetch, "redis_disabled_reason", lambda: "")(),
    }


@router.post("/prefetch/fill")
def prefetch_fill(
    req: PrefetchRequest,
    request: Request,
    api_key: str = Depends(require_api_key),
):
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    allowed, remaining, reset_ts = shared.safe_rate_check("prefill", client_key)
    if not allowed:
        log.info("prefetch.fill: rate limited client=%s", client_key)
        return JSONResponse(
            status_code=429,
            content=shared.rate_limit_payload(reset_ts),
            headers=shared.rate_limit_headers(remaining, reset_ts, limited=True),
        )
    if not premium_service.premium_ready():
        log.warning("prefetch.fill: premium LLM unavailable client=%s", client_key)
        return JSONResponse(
            status_code=503,
            content={"error": "Missing Gemini credentials"},
            headers=shared.rate_limit_headers(remaining, reset_ts),
        )

    requested_count = prefetch.clamp_batch(int(req.count or 0))
    initial_size = prefetch.size("premium")
    target_size = initial_size + requested_count
    generated_count = 0
    attempts = 0
    while attempts < requested_count and generated_count < requested_count:
        attempts += 1
        seed = (int(time.time() * 1000) + attempts) % 1_000_000_007
        try:
            batch_size = min(
                premium_service.PREMIUM_BATCH_SIZE, requested_count - generated_count
            )
            approved = premium_service.generate_premium_batch_candidates(
                req.brief or "",
                seed=seed,
                batch_size=batch_size,
                user_key="premium-prefetch",
                context="premium.fill",
            )
            generated_count += len(
                premium_service.enqueue_premium_docs(
                    approved, context="premium.fill", max_queue=target_size
                )
            )
        except Exception as exc:
            log.error("prefetch.fill: premium burst error client=%s err=%r", client_key, exc)
            break

    queue_size = prefetch.size("premium")
    added = max(queue_size - initial_size, 0)
    log.info(
        "prefetch.fill: client=%s requested=%d added=%d premium_queue_size=%d",
        client_key,
        requested_count,
        added,
        queue_size,
    )
    return JSONResponse(
        {"requested": requested_count, "added": added, "queue_size": queue_size},
        headers=shared.rate_limit_headers(remaining, reset_ts),
    )
