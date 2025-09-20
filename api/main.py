import os
import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.validators import validate_page, collect_errors
from api.llm_client import generate_page, llm_status, llm_probe
from api import cache, ratelimit

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Non-Deterministic Website API", version="0.1.0")

# CORS so a local HTML page can call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve /static (tailwind.css, js, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Request logging with request-id + latency
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
    brief: str = Field(..., description="Short description of what the page is about")
    seed: int | None = Field(None, description="Optional integer for deterministic output")
    model_version: str | None = Field(
        None, description="Override model id (e.g., mistralai/Mistral-7B-Instruct-v0.2)"
    )


class ValidateRequest(BaseModel):
    page: Dict[str, Any]



@app.get("/health")
def health():
    """
    Basic API health check.
    """
    return {"status": "ok"}


@app.get("/llm/status")
def llm_status_endpoint():
    """
    Configuration-level LLM status (doesn't call the model).
    """
    return llm_status()


@app.get("/llm/probe")
def llm_probe_endpoint():
    """
    Makes a tiny JSON-only probe request to the first available model.
    Returns ok=true if a model actually responded.
    """
    return llm_probe()


@app.post("/validate")
def validate_endpoint(payload: ValidateRequest):
    """
    Validates the provided JSON against the page schema.
    Returns 200 with {"valid": true} or 422 with readable errors.
    """
    try:
        validate_page(payload.page)
        return {"valid": True}
    except Exception:
        errors = collect_errors(payload.page)
        raise HTTPException(status_code=422, detail={"valid": False, "errors": errors})


@app.post("/generate")
def generate_endpoint(req: GenerateRequest, request: Request):
    """
    Calls the LLM (or stub), validates, and returns page JSON.
    IMPORTANT: Rate-limit happens BEFORE cache so even cache hits are counted.
    """
    # ---- 1) RATE LIMIT FIRST (before cache) ----
    # Prefer x-api-key; fall back to a stable IP or "testclient" when request.client is None (pytest).
    client_ip = (request.client.host if getattr(request, "client", None) else None) or "testclient"
    client_key = request.headers.get("x-api-key") or client_ip
    if not ratelimit.allow(f"gen:{client_key}"):
        raise HTTPException(status_code=429, detail={"message": "rate_limited", "retry_after_seconds": 60})

    # ---- 2) CACHE LOOKUP ----
    cached = cache.get(req.brief, req.seed, req.model_version)
    if cached:
        return cached

    # ---- 3) GENERATE ----
    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)

    # ---- 4) VALIDATE + STORE ----
    errors = collect_errors(page)
    if errors:
        raise HTTPException(status_code=502, detail={"message": "schema_validation_failed", "errors": errors})

    cache.set(req.brief, req.seed, req.model_version, page)
    return page


@app.post("/generate/stream")
def generate_stream(req: GenerateRequest, request: Request):
    """
    Streams NDJSON lines for each component: one JSON object per line:
    {"component": {...}}
    NOTE: We also count this route in the same limiter namespace.
    """
    # Rate-limit streaming calls too.
    client_ip = (request.client.host if getattr(request, "client", None) else None) or "testclient"
    client_key = request.headers.get("x-api-key") or client_ip
    if not ratelimit.allow(f"gen:{client_key}"):
        raise HTTPException(status_code=429, detail={"message": "rate_limited", "retry_after_seconds": 60})

    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)

    def stream():
        for comp in page.get("components", []):
            yield json.dumps({"component": comp}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/", response_class=HTMLResponse)
def home():
    """
    Serves the simple demo UI (if you created templates/index.html).
    """
    tpl = Path("templates/index.html")
    if tpl.exists():
        return tpl.read_text(encoding="utf-8")
    return "<h1>Nondeterministic Website API</h1><p>Add templates/index.html for a demo UI.</p>"
