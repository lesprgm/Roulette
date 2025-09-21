import os
import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.validators import validate_page, collect_errors
from api.llm_client import generate_page, llm_status, llm_probe
from api.auth import check_api_key

logging.basicConfig(level=logging.INFO)

IN_TEST = bool(os.getenv("PYTEST_CURRENT_TEST"))
REDIS_URL = os.getenv("REDIS_URL", "").strip()
USE_REDIS = False

# Choose backends, but be ready to fall back.
if IN_TEST or not REDIS_URL:
    from api import cache
    from api import ratelimit as rlim
else:
    try:
        from api import redis_cache as cache
        from api import redis_ratelimit as rlim
        USE_REDIS = True
    except Exception as _e:
        from api import cache
        from api import ratelimit as rlim
        logging.warning("Using in-memory backends (redis import failed): %s", _e)

def _fallback_to_memory(reason: Exception | str):
    #Switch to in-memory cache/limiter if Redis errors occur.
    global cache, rlim, USE_REDIS
    if not USE_REDIS:
        return
    try:
        from api import cache as mem_cache
        from api import ratelimit as mem_rl
        cache = mem_cache
        rlim = mem_rl
        USE_REDIS = False
        logging.warning("Redis unavailable; falling back to in-memory. Reason: %s", reason)
    except Exception as e:
        logging.error("Failed to switch to in-memory backends: %s", e)

def _call_limiter(bucket: str, key: str):
    """
    Call whichever limiter API exists:
    - check_and_increment(bucket, key) -> (allowed, remaining, reset_ts)
    - allow_request(bucket, key)       -> (allowed, remaining, reset_ts)
    """
    if hasattr(rlim, "check_and_increment"):
        return rlim.check_and_increment(bucket, key)  # type: ignore[attr-defined]
    if hasattr(rlim, "allow_request"):
        return rlim.allow_request(bucket, key)        # type: ignore[attr-defined]
    # Last resort: allow everything
    return True, getattr(rlim, "MAX_REQUESTS", 0), int(time.time()) + getattr(rlim, "WINDOW_SECONDS", 60)

def _safe_rate_check(bucket: str, key: str):
    """Limiter with fallback + one retry if the backend errors."""
    try:
        return _call_limiter(bucket, key)
    except Exception as e:
        _fallback_to_memory(e)
        return _call_limiter(bucket, key)

def _safe_cache_get(brief: str, seed: int | None, model_version: str | None):
    try:
        return cache.get(brief, seed, model_version)
    except Exception as e:
        _fallback_to_memory(e)
        return cache.get(brief, seed, model_version)

def _safe_cache_set(brief: str, seed: int | None, model_version: str | None, page: Dict[str, Any]):
    try:
        cache.set(brief, seed, model_version, page)
    except Exception as e:
        _fallback_to_memory(e)
        cache.set(brief, seed, model_version, page)

app = FastAPI(title="Non-Deterministic Website API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.time()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        dur_ms = int((time.time() - start) * 1000)
        logging.info(
            "rid=%s method=%s path=%s status=%s dur_ms=%s",
            rid, request.method, request.url.path,
            getattr(response, "status_code", "?"), dur_ms
        )

class GenerateRequest(BaseModel):
    brief: str = Field(..., description="Short description of the page to generate")
    seed: int | None = Field(None, description="Optional integer seed")
    model_version: str | None = Field(None, description="Optional override model id")

class ValidateRequest(BaseModel):
    page: Dict[str, Any]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/llm/status")
def llm_status_endpoint():
    return llm_status()

@app.get("/llm/probe")
def llm_probe_endpoint():
    return llm_probe()

@app.post("/validate")
def validate_endpoint(payload: ValidateRequest):
    try:
        validate_page(payload.page)
        return {"valid": True}
    except Exception:
        errors = collect_errors(payload.page)
        raise HTTPException(status_code=422, detail={"valid": False, "errors": errors})

@app.post("/generate")
def generate_endpoint(req: GenerateRequest, request: Request, response: Response):
    api_key = request.headers.get("x-api-key")
    if not check_api_key(api_key):
        raise HTTPException(status_code=401, detail={"message": "invalid_api_key"})

    client_ip = (request.client.host if getattr(request, "client", None) else None) or "testclient"
    client_key = api_key or client_ip

    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    response.headers["X-RateLimit-Limit"] = str(getattr(rlim, "MAX_REQUESTS", ""))
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(reset_ts)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"message": "rate_limited", "retry_after_seconds": max(1, reset_ts - int(time.time()))},
        )

    cached = _safe_cache_get(req.brief, req.seed, req.model_version)
    if cached:
        return cached

    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)

    errors = collect_errors(page)
    if errors:
        raise HTTPException(status_code=502, detail={"message": "schema_validation_failed", "errors": errors})

    _safe_cache_set(req.brief, req.seed, req.model_version, page)
    return page

@app.post("/generate/stream")
def generate_stream(req: GenerateRequest, request: Request, response: Response):
    api_key = request.headers.get("x-api-key")
    if not check_api_key(api_key):
        raise HTTPException(status_code=401, detail={"message": "invalid_api_key"})

    client_ip = (request.client.host if getattr(request, "client", None) else None) or "testclient"
    client_key = api_key or client_ip

    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    response.headers["X-RateLimit-Limit"] = str(getattr(rlim, "MAX_REQUESTS", ""))
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(reset_ts)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"message": "rate_limited", "retry_after_seconds": max(1, reset_ts - int(time.time()))},
        )

    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)

    def stream():
        for comp in page.get("components", []):
            yield json.dumps({"component": comp}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")

@app.get("/", response_class=HTMLResponse)
def home():
    tpl = Path("templates/index.html")
    if tpl.exists():
        return tpl.read_text(encoding="utf-8")
    return "<h1>Nondeterministic Website API</h1><p>Add templates/index.html for a demo UI.</p>"
