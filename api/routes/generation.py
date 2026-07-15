import json
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Iterable, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api import counter, prefetch
from api.auth import extract_client_key, optional_api_key
from api.generation import premium_service
from api.preflight import has_blocking_issues, preflight_doc
from api.routes import shared
from api.validators import validate_page_doc


router = APIRouter()
log = logging.getLogger(__name__)


class GenerateRequest(BaseModel):
    brief: str = Field(
        "", description="Short description of the app to create; may be empty to let the model choose"
    )
    seed: Optional[int] = Field(default=None, description="Optional PRNG seed")
    model_version: Optional[str] = Field(default=None, description="Optional model name override")


class ValidateRequest(BaseModel):
    page: Dict[str, Any]


def _offline_page(seed: int) -> Dict[str, Any]:
    return {
        "components": [{
            "id": "offline-1",
            "type": "custom",
            "props": {
                "html": """<div class="p-6 rounded-xl border border-slate-200 bg-white"><h3 class="text-xl font-semibold">Offline Sandbox App</h3><p class="mt-2 text-sm text-slate-700">This was rendered without an API key.</p><button id="btn" class="mt-3 px-4 py-2 rounded bg-indigo-600 text-white hover:bg-indigo-700">Click</button><div id="out" class="mt-2 text-slate-700"></div><script>let n=0; const o=document.getElementById('out');document.getElementById('btn').onclick=()=>{n++;o.textContent='Clicks: '+n;};</script></div>""",
                "height": 260,
            },
        }],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
        "links": ["/about"],
        "seed": seed,
        "model_version": "offline",
        "review": {
            "ok": True,
            "issues": [],
            "notes": "Offline fallback page served because ALLOW_OFFLINE_GENERATION is enabled.",
        },
    }


def _test_page(seed: int) -> Dict[str, Any]:
    return {
        "components": [{
            "id": "custom-1",
            "type": "custom",
            "props": {
                "html": """<div class="p-4 rounded-xl border border-slate-200 bg-white"><h3 class="text-xl font-semibold">Test App</h3><div id="t" class="mt-2 text-sm text-slate-700">OK</div><script>document.getElementById('t').textContent='Rendered';</script></div>""",
                "height": 240,
            },
        }],
        "layout": {"flow": "stack"},
        "palette": {"primary": "slate", "accent": "indigo"},
        "links": ["/about"],
        "seed": seed,
        "model_version": "test-stub",
    }


def _serve_page(page: Dict[str, Any], client_key: str, remaining: int, reset_ts: int) -> JSONResponse:
    if isinstance(page, dict) and not page.get("error"):
        allowed, remaining, reset_ts = shared.safe_rate_check("gen", client_key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content=shared.rate_limit_payload(reset_ts),
                headers=shared.rate_limit_headers(remaining, reset_ts, limited=True),
            )
        try:
            counter.increment(1)
        except Exception:
            pass
        shared.record_user_visible_serve(page)
    return JSONResponse(page, headers=shared.rate_limit_headers(remaining, reset_ts))


def _dequeue_or_generate(
    req: GenerateRequest,
    client_key: str,
    background_tasks: BackgroundTasks,
    *,
    context: str,
) -> Dict[str, Any]:
    page = prefetch.dequeue("premium") if premium_service.premium_queue_enabled() else None
    if page:
        if (
            premium_service.PREMIUM_TOPUP_ENABLED
            and prefetch.size("premium") <= premium_service.PREMIUM_LOW_WATER
        ):
            premium_service.schedule_premium_topup(
                background_tasks,
                req.brief or "",
                premium_service.PREMIUM_FILL_TO,
                context=context,
            )
        return page
    return premium_service.stream_premium_first_page(
        req.brief or "",
        seed=req.seed or 0,
        user_key=client_key,
        background_tasks=background_tasks,
    )


@router.post("/generate")
def generate_endpoint(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(optional_api_key),
):
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    if not premium_service.premium_ready():
        offline_allowed = os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() in {
            "1", "true", "yes", "on"
        }
        if offline_allowed or os.getenv("PYTEST_CURRENT_TEST"):
            allowed, remaining, reset_ts = shared.safe_rate_check("gen", client_key)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content=shared.rate_limit_payload(reset_ts),
                    headers=shared.rate_limit_headers(remaining, reset_ts, limited=True),
                )
            page = _offline_page(req.seed or 0) if offline_allowed else _test_page(req.seed or 0)
            return JSONResponse(page, headers=shared.rate_limit_headers(remaining, reset_ts))
        return JSONResponse(
            status_code=503,
            content={"error": "Missing LLM credentials"},
            headers=shared.rate_limit_headers(9999, int(time.time())),
        )

    allowed, remaining, reset_ts = shared.safe_rate_inspect("gen", client_key)
    log.info("rate_limit inspect allowed=%s remaining=%s", allowed, remaining)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=shared.rate_limit_payload(reset_ts),
            headers=shared.rate_limit_headers(remaining, reset_ts, limited=True),
        )
    page = _dequeue_or_generate(req, client_key, background_tasks, context="site.generate")
    return _serve_page(page, client_key, remaining, reset_ts)


@router.post("/generate/stream")
def generate_stream(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(optional_api_key),
):
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    offline_allowed = os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() in {"1", "true", "yes", "on"}
    if not premium_service.premium_ready() and not offline_allowed and not os.getenv("PYTEST_CURRENT_TEST"):
        def error_events() -> Iterable[str]:
            yield json.dumps({"event": "meta", "request_id": getattr(request.state, "request_id", None)}) + "\n"
            yield json.dumps({"event": "error", "data": {"error": "Missing LLM credentials"}}) + "\n"

        return StreamingResponse(
            error_events(),
            media_type="application/x-ndjson",
            headers=shared.rate_limit_headers(9999, int(time.time())),
        )

    allowed, remaining, reset_ts = shared.safe_rate_inspect("gen", client_key)
    log.info("rate_limit inspect allowed=%s remaining=%s", allowed, remaining)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=shared.rate_limit_payload(reset_ts),
            headers=shared.rate_limit_headers(remaining, reset_ts, limited=True),
        )

    def events() -> Iterable[str]:
        yield json.dumps({"event": "meta", "request_id": getattr(request.state, "request_id", None)}) + "\n"
        results: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)

        def work() -> None:
            try:
                results.put({"page": _dequeue_or_generate(req, client_key, background_tasks, context="site.stream")})
            except Exception:
                log.exception("site.stream: generation failed")
                results.put({"error": {"error": "Generation failed"}})

        threading.Thread(target=work, daemon=True).start()
        while True:
            try:
                result = results.get(timeout=max(1.0, premium_service.STREAM_KEEPALIVE_SECONDS))
                break
            except queue.Empty:
                yield json.dumps({"event": "ping", "data": {"ts": int(time.time())}}) + "\n"
        if result.get("error"):
            yield json.dumps({"event": "error", "data": result["error"]}) + "\n"
            return
        page = result.get("page")
        if isinstance(page, dict) and not page.get("error"):
            allowed_now, _, reset_now = shared.safe_rate_check("gen", client_key)
            if not allowed_now:
                yield json.dumps({"event": "error", "data": shared.rate_limit_payload(reset_now)}) + "\n"
                return
            try:
                counter.increment(1)
            except Exception:
                pass
            shared.record_user_visible_serve(page)
            yield json.dumps({"event": "page", "data": page}) + "\n"
        else:
            yield json.dumps({"event": "error", "data": page or {"error": "Generation failed"}}) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers=shared.rate_limit_headers(remaining, reset_ts),
    )


@router.post("/validate")
def validate_endpoint(req: ValidateRequest):
    valid, errors = validate_page_doc(req.page)
    preflight_issues = preflight_doc(req.page)
    preflight_errors = [
        {
            "path": item.get("field", "(preflight)"),
            "message": item.get("message", "invalid"),
            "severity": item.get("severity", "warn"),
        }
        for item in preflight_issues
        if isinstance(item, dict)
    ]
    if has_blocking_issues(preflight_issues):
        valid = False
        errors += preflight_errors
    detail = {"valid": valid}
    if not valid:
        detail["errors"] = errors
        return JSONResponse(status_code=422, content={"detail": detail})
    if preflight_errors:
        detail["warnings"] = preflight_errors
    return {"detail": detail}
