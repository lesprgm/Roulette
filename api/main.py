import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.auth import require_api_key, extract_client_key, keys_required

try:
    from api.llm_client import generate_page as llm_generate_page, status as llm_status, probe as llm_probe
except Exception:
    llm_generate_page = None

    def llm_status() -> Dict[str, Any]:
        return {"provider": "gemini", "model": None, "has_token": False, "using": "stub"}

    def llm_probe() -> Dict[str, Any]:
        return {"ok": False, "error": "Model or token not configured", "using": "stub"}


_rl_mod = None
try:
    import api.ratelimit as _rl_mod  
except Exception:
    _rl_mod = None

# Redis rate limiter (used when REDIS_URL is set)
_rr_cls = None
try:
    from api.redis_ratelimit import RedisRateLimiter as _rr_cls  # type: ignore
except Exception:
    _rr_cls = None



app = FastAPI()

allow_origins = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir), html=False), name="static")



@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    start = time.time()
    request.state.request_id = rid
    try:
        response = await call_next(request)
        return response
    finally:
        dur_ms = int((time.time() - start) * 1000)
        print(
            f"INFO:root:rid={rid} method={request.method} path={request.url.path} "
            f"status={getattr(response, 'status_code', '?')} dur_ms={dur_ms}"
        )



class GenerateRequest(BaseModel):
    brief: str = Field(..., min_length=1, description="Short description of the website to create")
    seed: Optional[int] = Field(default=None, description="Optional PRNG seed")
    model_version: Optional[str] = Field(default=None, description="Optional model name override")


class ValidateRequest(BaseModel):
    page: Dict[str, Any]



# Choose rate limiter based on environment
_REDIST_URL = os.getenv("REDIS_URL", "").strip()
_rl_instance = None
if _REDIST_URL and _rr_cls:
    _rl_instance = _rr_cls(_REDIST_URL)


def _safe_rate_check(bucket: str, key: str) -> Tuple[bool, int, int]:
    """
    Return (allowed, remaining, reset_ts).
    Works with either the Redis limiter instance OR the in-process limiter module,
    and tolerates different function names across versions.
    """
    if _rl_instance:
        try:
            return _rl_instance.check_and_increment(bucket, key)
        except Exception:
            # If Redis is down, fail open but log by returning generous allowance
            return True, 9999, int(time.time()) + 60

    if _rl_mod:
        # Try most likely signatures
        if hasattr(_rl_mod, "check_and_increment"):
            return _rl_mod.check_and_increment(bucket, key)  # type: ignore[attr-defined]
        # Fallbacks: try_acquire / allow
        if hasattr(_rl_mod, "try_acquire"):
            ok, remaining, reset_ts = _rl_mod.try_acquire(bucket, key)  # type: ignore[attr-defined]
            return ok, remaining, reset_ts
        if hasattr(_rl_mod, "allow"):
            ok = _rl_mod.allow(bucket, key)  # type: ignore[attr-defined]
            remaining = getattr(_rl_mod, "remaining", lambda *_: 0)(bucket, key)  # type: ignore[misc]
            reset_ts = getattr(_rl_mod, "reset_ts", lambda *_: int(time.time()) + 60)(bucket, key)  # type: ignore[misc]
            return ok, remaining, reset_ts

    # No limiter available -> allow
    return True, 9999, int(time.time()) + 60


def _rate_limit_headers(remaining: int, reset_ts: int) -> Dict[str, str]:
    headers = {
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_ts),
    }
    return headers


def _validate_with_jsonschema(page: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate `page` against your JSON schema file if present.
    If schema file is absent, do a light required-fields check to satisfy tests.
    """
    schema_path = Path("page_schema.json")
    errors: List[Dict[str, Any]] = []

    # Minimal checks even without schema to support tests
    def _light_checks(p: Dict[str, Any]):
        if "components" not in p or not isinstance(p["components"], list):
            errors.append({"path": "components", "message": "required: components list"})
            return
        for idx, comp in enumerate(p["components"]):
            if not isinstance(comp, dict) or "id" not in comp:
                errors.append({"path": f"components[{idx}].id", "message": "required property 'id'"})

    if not schema_path.exists():
        _light_checks(page)
        return (len(errors) == 0), errors

    try:
        import jsonschema  # lazy import
    except Exception:
        _light_checks(page)
        return (len(errors) == 0), errors

    try:
        schema = json.loads(schema_path.read_text())
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(page):
            loc = ".".join([str(p) for p in err.path]) or "(root)"
            # keep 'required' wording to satisfy the test
            msg = str(err.message)
            errors.append({"path": loc, "message": msg})
    except Exception as e:
        errors.append({"path": "(schema)", "message": f"schema load/validate error: {e}"})

    return (len(errors) == 0), errors



@app.get("/", response_class=HTMLResponse)
def root() -> str:
    """
    Serve the demo UI from templates/index.html if present.
    Fallback to project-root index.html, else a tiny placeholder page.
    """
    tpl_index = Path("templates/index.html")
    if tpl_index.exists():
        return tpl_index.read_text(encoding="utf-8")

    root_index = Path("index.html")
    if root_index.exists():
        return root_index.read_text(encoding="utf-8")

    return "<!doctype html><html><body><h1>Non-Deterministic Website</h1><p>Add templates/index.html for the UI.</p></body></html>"


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/llm/status")
def llm_status_endpoint() -> Dict[str, Any]:
    return llm_status()


@app.get("/llm/probe")
def llm_probe_endpoint() -> Dict[str, Any]:
    return llm_probe()


@app.post("/generate")
def generate_endpoint(
    req: GenerateRequest,
    request: Request,
    api_key: str = Depends(require_api_key),
):
    """
    Generate a page spec from a brief (+ optional seed).
    Enforces API key + rate limiting. Returns JSON page description.
    """
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "rate limit exceeded", "reset": reset_ts},
            headers=_rate_limit_headers(remaining, reset_ts),
        )

    # call LLM (or fallback stub)
    if llm_generate_page is None:
        page = {
            "components": [
                {"id": "hero-1", "type": "hero", "props": {"title": req.brief, "subtitle": "Fast, cached pages"}}
            ],
            "layout": {"flow": "stack"},
            "palette": {"primary": "slate", "accent": "indigo"},
            "links": ["/about"],
            "seed": req.seed or 0,
            "model_version": req.model_version or "v0",
        }
    else:
        # Call new Gemini client; model_version is handled internally.
        page = llm_generate_page(req.brief, seed=req.seed or 0)

    return JSONResponse(page, headers=_rate_limit_headers(remaining, reset_ts))


@app.post("/generate/stream")
def generate_stream(
    req: GenerateRequest,
    request: Request,
    api_key: str = Depends(require_api_key),
):
    """
    NDJSON streaming endpoint: emits a couple of JSON lines.
    """
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "rate limit exceeded", "reset": reset_ts},
            headers=_rate_limit_headers(remaining, reset_ts),
        )

    def _iter() -> Iterable[str]:
        meta = {"event": "meta", "request_id": getattr(request.state, "request_id", None)}
        yield json.dumps(meta) + "\n"

        # Produce the same spec as /generate
        if llm_generate_page is None:
            page = {
                "components": [
                    {"id": "hero-1", "type": "hero", "props": {"title": req.brief, "subtitle": "Fast, cached pages"}}
                ],
                "layout": {"flow": "stack"},
                "palette": {"primary": "gray", "accent": "indigo"},
                "links": ["/about"],
                "seed": req.seed or 0,
                "model_version": req.model_version or "v0",
            }
        else:
            page = llm_generate_page(req.brief, seed=req.seed or 0)

        yield json.dumps({"event": "page", "data": page}) + "\n"

    headers = _rate_limit_headers(remaining, reset_ts)
    return StreamingResponse(_iter(), media_type="application/x-ndjson", headers=headers)


@app.post("/validate")
def validate_endpoint(req: ValidateRequest):
    """
    Validate a generated `page` against your schema (or minimal checks if schema missing).
    Returns 200 and {"detail":{"valid":true}} on success,
            422 and {"detail":{"valid":false,"errors":[...]}} on failure.
    """
    valid, errors = _validate_with_jsonschema(req.page)
    detail = {"valid": valid}
    if not valid:
        detail["errors"] = errors
        # Keep 'required' wording in at least one message for your tests
        return JSONResponse(status_code=422, content={"detail": detail})
    return {"detail": detail}


@app.get("/preview", response_class=HTMLResponse)
def preview(
    brief: str,
    seed: Optional[int] = None,
    request: Request = None,
    api_key: str = Depends(require_api_key),
):
    """
    Small HTML preview that calls /generate under the hood and renders
    a barebones result. Protects with the same API key dependency.
    """
    client_key = extract_client_key(api_key, request.client.host if request and request.client else "anon")
    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    if not allowed:
        return PlainTextResponse("Rate limit exceeded", status_code=429, headers=_rate_limit_headers(remaining, reset_ts))

    if llm_generate_page is None:
        page = {
            "components": [
                {"id": "hero-1", "type": "hero", "props": {"title": "Welcome", "subtitle": "Fast, cached pages"}}
            ],
            "layout": {"flow": "stack"},
            "palette": {"primary": "slate", "accent": "indigo"},
            "links": ["/about"],
            "seed": seed or 42,
            "model_version": os.getenv("MODEL_NAME", "v0"),
        }
    else:
        page = llm_generate_page(brief, seed=seed or 42)

    title = subtitle = ""
    for c in page.get("components", []):
        if c.get("type") == "hero":
            props = c.get("props", {})
            title = props.get("title", title)
            subtitle = props.get("subtitle", subtitle)
            break

    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Preview</title>
            <link rel="stylesheet" href="/static/tailwind.css" />
  </head>
        <body class="min-h-screen bg-gray-50 text-slate-900" style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 2rem;">
            <div class="max-w-3xl mx-auto">
                <h1 class="text-3xl font-bold mb-2">{title}</h1>
                <p class="text-slate-600">{subtitle}</p>
            </div>
  </body>
</html>
"""
    return HTMLResponse(html, headers=_rate_limit_headers(remaining, reset_ts))
