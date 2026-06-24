import json
import logging
import os
import queue
import time
import uuid
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.auth import require_api_key, optional_api_key, extract_client_key, keys_required, is_admin_key
from api import counter
from api import prefetch
from api.generation.novelty import record_served_doc
from api.generation.redis_diversity import record_site_descriptor
from api.preflight import annotate_doc as annotate_preflight_doc
from api.preflight import has_blocking_issues as preflight_has_blocking_issues
from api.preflight import preflight_doc
from api.validators import validate_page_doc as _validate_with_jsonschema

PrefetchHandle = str
_PREMIUM_TOPUP_LOCK = threading.Lock()
TAILWIND_CSS_PATH = Path("static/tailwind.css")
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


def _record_user_visible_serve(doc: Dict[str, Any]) -> None:
    try:
        record_served_doc(doc)
    except Exception:
        pass
    try:
        record_site_descriptor(doc, event="site_served")
    except Exception:
        pass

try:
    from api.llm_client import (
        generate_page_premium as llm_generate_page_premium,
        generate_page_premium_burst as llm_generate_page_premium_burst,
        premium_available as llm_premium_available,
        status as llm_status,
        probe as llm_probe,
    )
except Exception:
    llm_generate_page_premium = None
    llm_generate_page_premium_burst = None

    def llm_status() -> Dict[str, Any]:
        return {"provider": None, "model": None, "has_token": False, "using": "stub"}

    def llm_probe() -> Dict[str, Any]:
        return {"ok": False, "error": "Model or token not configured", "using": "stub"}

    def llm_premium_available() -> bool:
        return False


if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

log = logging.getLogger(__name__)

_rl_mod = None
try:
    import api.ratelimit as _rl_mod  
except Exception:
    _rl_mod = None

_rr_cls = None
try:
    from api.redis_ratelimit import RedisRateLimiter as _rr_cls  
except Exception:
    _rr_cls = None


def _is_render_env() -> bool:
    return bool(
        os.getenv("RENDER")
        or os.getenv("RENDER_SERVICE_ID")
        or os.getenv("RENDER_INSTANCE_ID")
        or os.getenv("RENDER_EXTERNAL_URL")
    )


def _log_startup_checks() -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        log.warning("startup.check: no LLM API keys set; generation will fail in production")

    if not os.getenv("PREFETCH_TOKEN_SECRET", "").strip():
        log.warning("startup.check: PREFETCH_TOKEN_SECRET not set; preview tokens reset on restart")

    required_assets = [
        TAILWIND_CSS_PATH,
        Path("static/vendor/tailwind-play.js"),
        Path("static/vendor/gsap.min.js"),
        Path("static/vendor/lucide.min.js"),
        Path("static/vendor/alpine.min.js"),
        Path("static/vendor/matter.min.js"),
        Path("static/vendor/three-addons/controls/OrbitControls.js"),
    ]
    for asset in required_assets:
        if not asset.exists():
            log.warning("startup.check: missing asset %s", asset.as_posix())

    if _is_render_env():
        cache_mount = Path("/opt/render/project/src/cache")
        prefetch_dir = Path(os.getenv("PREFETCH_DIR", "cache/prefetch")).resolve(strict=False)
        if not cache_mount.exists():
            log.warning("startup.check: Render disk not mounted at %s; prefetch queue will be ephemeral", cache_mount)
        elif not str(prefetch_dir).startswith(str(cache_mount.resolve(strict=False))):
            log.warning("startup.check: PREFETCH_DIR=%s is not on Render disk %s", prefetch_dir, cache_mount)

    # Prefetch storage backend (Redis vs file)
    try:
        from api import prefetch as _prefetch_mod
        backend = "redis" if getattr(_prefetch_mod, "_redis_enabled", lambda: False)() else "file"
        log.info("startup.check: prefetch backend=%s", backend)
    except Exception:
        log.info("startup.check: prefetch backend=unknown")



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _log_startup_checks()
    except Exception:
        log.exception("prefetch.lifespan: unexpected startup error")
        pass
    yield

app = FastAPI(lifespan=lifespan)

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
    # Mount subdirectories at root-level paths expected by the frontend.
    # Order matters: more specific routes first.
    js_dir = static_dir / "js"
    css_dir = static_dir / "css"
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="static_js")
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="static_css")
    # Mount tailwind.css as a single file at root (requires serving the parent dir)
    # FastAPI's StaticFiles can serve individual files if we mount the static dir
    # and reference the file directly. We'll mount for the asset and rely on catch-all.
    app.mount("/static", StaticFiles(directory=str(static_dir), html=False), name="static")




@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    start = time.time()
    request.state.request_id = rid
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        dur_ms = int((time.time() - start) * 1000)
        log.info(
            "rid=%s method=%s path=%s status=%s dur_ms=%d",
            rid,
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            dur_ms,
        )



class GenerateRequest(BaseModel):
    # Allow empty brief so the model can invent a theme
    brief: str = Field("", description="Short description of the app to create; may be empty to let the model choose")
    seed: Optional[int] = Field(default=None, description="Optional PRNG seed")
    model_version: Optional[str] = Field(default=None, description="Optional model name override")


class ValidateRequest(BaseModel):
    page: Dict[str, Any]



# Choose rate limiter based on environment
_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_rl_instance = None
if _REDIS_URL and _rr_cls and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        _rl_instance = _rr_cls(_REDIS_URL)
    except Exception:
        _rl_instance = None


def _safe_rate_check(bucket: str, key: str) -> Tuple[bool, int, int]:
    """
    Return (allowed, remaining, reset_ts).
    Works with either the Redis limiter instance OR the in-process limiter module,
    and tolerates different function names across versions.
    """
    if is_admin_key(key):
        return True, 9999, int(time.time()) + 60
    use_redis = _rl_instance and not os.getenv("PYTEST_CURRENT_TEST")
    if use_redis:
        try:
            return _rl_instance.check_and_increment(bucket, key)
        except Exception:
            # If Redis is unavailable, fall back to in-process limiter; if that fails, fail open.
            pass

    if _rl_mod:
        if hasattr(_rl_mod, "check_and_increment"):
            return _rl_mod.check_and_increment(bucket, key)  
        if hasattr(_rl_mod, "try_acquire"):
            ok, remaining, reset_ts = _rl_mod.try_acquire(bucket, key)
            return ok, remaining, reset_ts
        if hasattr(_rl_mod, "allow"):
            ok = _rl_mod.allow(bucket, key)
            remaining = getattr(_rl_mod, "remaining", lambda *_: 0)(bucket, key)
            reset_ts = getattr(_rl_mod, "reset_ts", lambda *_: int(time.time()) + 60)(bucket, key)
            return ok, remaining, reset_ts

    return True, 9999, int(time.time()) + 60


def _safe_rate_inspect(bucket: str, key: str) -> Tuple[bool, int, int]:
    if is_admin_key(key):
        return True, 9999, int(time.time()) + 60
    use_redis = _rl_instance and not os.getenv("PYTEST_CURRENT_TEST")
    if use_redis:
        try:
            return _rl_instance.inspect(bucket, key)
        except Exception:
            pass
    if _rl_mod and hasattr(_rl_mod, "inspect"):
        try:
            return _rl_mod.inspect(bucket, key)
        except Exception:
            pass
    return True, 9999, int(time.time()) + 60


def _rate_limit_headers(remaining: int, reset_ts: int, *, limited: bool = False) -> Dict[str, str]:
    headers = {
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_ts),
    }
    if limited:
        wait_seconds = max(0, reset_ts - int(time.time()))
        headers["Retry-After"] = str(wait_seconds)
    return headers


def _get_cached_prefetch_previews(limit: int) -> Optional[List[Dict[str, Any]]]:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    if PREFETCH_PREVIEW_CACHE_TTL <= 0:
        return None
    now = time.time()
    with _PREFETCH_PREVIEW_LOCK:
        cached = _PREFETCH_PREVIEW_CACHE.get(limit)
        if cached and (now - cached[0]) <= PREFETCH_PREVIEW_CACHE_TTL:
            return cached[1]
    return None


def _set_cached_prefetch_previews(limit: int, items: List[Dict[str, Any]]) -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    if PREFETCH_PREVIEW_CACHE_TTL <= 0:
        return
    with _PREFETCH_PREVIEW_LOCK:
        _PREFETCH_PREVIEW_CACHE[limit] = (time.time(), items)


def _rate_limit_payload(reset_ts: int) -> Dict[str, Any]:
    wait_seconds = max(0, reset_ts - int(time.time()))
    return {
        "error": "rate limit exceeded",
        "reset": reset_ts,
        "retry_after_seconds": wait_seconds,
        "message": f"Rate limit exceeded. Try again in {wait_seconds} seconds.",
    }


PREFETCH_PREVIEW_CACHE_TTL = float(os.getenv("PREFETCH_PREVIEW_CACHE_TTL", "2") or 2)
_PREFETCH_PREVIEW_CACHE: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
_PREFETCH_PREVIEW_LOCK = threading.Lock()
PREMIUM_QUEUE_ENABLED = os.getenv("PREMIUM_QUEUE_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
PREMIUM_LOW_WATER = int(os.getenv("PREMIUM_LOW_WATER", "3") or 3)
PREMIUM_FILL_TO = int(os.getenv("PREMIUM_FILL_TO", "10") or 10)
if PREMIUM_LOW_WATER > PREMIUM_FILL_TO:
    PREMIUM_LOW_WATER = PREMIUM_FILL_TO
PREMIUM_BATCH_SIZE = int(os.getenv("PREMIUM_BATCH_SIZE", "12") or 12)
PREMIUM_TOPUP_ENABLED = os.getenv("PREMIUM_TOPUP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
try:
    STREAM_KEEPALIVE_SECONDS = float(os.getenv("STREAM_KEEPALIVE_SECONDS", "8") or 8)
except Exception:
    STREAM_KEEPALIVE_SECONDS = 8.0

def _premium_queue_enabled() -> bool:
    return PREMIUM_QUEUE_ENABLED


def _require_admin_or_dev(api_key: str) -> None:
    if keys_required() and not is_admin_key(api_key):
        raise HTTPException(status_code=403, detail="Admin API key required")


def _summarize_preflight_issues(issues: List[Dict[str, Any]], limit: int = 4) -> str:
    parts: List[str] = []
    for issue in list(issues or [])[:limit]:
        severity = str(issue.get("severity") or "issue")
        field = str(issue.get("field") or "unknown")
        message = str(issue.get("message") or "").strip()
        parts.append(f"{severity}:{field}:{message}")
    extra = len(issues or []) - len(parts)
    if extra > 0:
        parts.append(f"+{extra} more")
    return " | ".join(parts) if parts else "none"


def _apply_local_acceptance_batch(docs: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
    approved = []
    for idx, doc in enumerate(docs):
        if not isinstance(doc, dict):
            continue
        issues = preflight_doc(doc)
        if preflight_has_blocking_issues(issues):
            log.info(
                "%s: local preflight rejected index=%d issues=%s",
                context,
                idx,
                _summarize_preflight_issues(issues),
            )
            continue
        if issues:
            doc = annotate_preflight_doc(doc, issues)
        doc["review"] = {"ok": True, "notes": "local preflight accepted"}
        approved.append(doc)
    return approved


def _enqueue_premium_docs(
    docs: List[Dict[str, Any]], *, context: str, max_queue: Optional[int] = None
) -> List[PrefetchHandle]:
    if not docs or not _premium_queue_enabled():
        return []
    stored: List[PrefetchHandle] = []
    for doc in docs:
        if max_queue is not None and prefetch.size("premium") >= max_queue:
            break
        handle = prefetch.enqueue(doc, lane="premium")
        if not handle:
            continue
        stored.append(handle)
    return stored


def _premium_seed(base_seed: int, offset: int) -> int:
    seed = (int(base_seed or 0) + ((offset + 1) * 7919)) % 1_000_000_007
    return seed or (offset + 1)


def _generate_premium_batch_candidates(
    brief: str,
    *,
    batch_size: int,
    seed: int,
    user_key: str,
    context: str,
) -> List[Dict[str, Any]]:
    if llm_generate_page_premium_burst:
        docs: List[Dict[str, Any]] = []
        try:
            for doc in llm_generate_page_premium_burst(
                brief or "",
                seed=seed,
                count=max(1, int(batch_size or 1)),
                user_key=user_key,
            ):
                if isinstance(doc, dict) and not doc.get("error"):
                    docs.append(doc)
        except Exception:
            log.exception("%s: premium burst interrupted after %d accepted candidates", context, len(docs))
        if docs:
            return _apply_local_acceptance_batch(docs, context)
    if not llm_generate_page_premium:
        return []
    docs: List[Dict[str, Any]] = []
    for idx in range(max(1, int(batch_size or 1))):
        doc = llm_generate_page_premium(brief or "", seed=_premium_seed(seed, idx), user_key=user_key)
        if isinstance(doc, dict) and not doc.get("error"):
            docs.append(doc)
    if not docs:
        return []
    return _apply_local_acceptance_batch(docs, context)


def _next_acceptable_premium_doc(iterator: Iterable[Dict[str, Any]], context: str) -> Optional[Dict[str, Any]]:
    for doc in iterator:
        if not isinstance(doc, dict) or doc.get("error"):
            continue
        approved = _apply_local_acceptance_batch([doc], context)
        if approved:
            return approved[0]
    return None


def _drain_premium_burst_to_queue(
    iterator: Iterable[Dict[str, Any]],
    *,
    context: str,
    max_queue: int = PREMIUM_FILL_TO,
    brief: str = "",
) -> None:
    del brief
    try:
        for doc in iterator:
            if not isinstance(doc, dict) or doc.get("error"):
                continue
            approved = _apply_local_acceptance_batch([doc], context)
            if not approved:
                continue
            stored = _enqueue_premium_docs(approved, context=context, max_queue=max_queue)
            if _premium_queue_enabled() and prefetch.size("premium") >= max_queue:
                break
    except Exception:
        log.exception("%s: failed draining premium burst leftovers", context)


def _start_premium_burst(
    brief: str,
    *,
    seed: int,
    user_key: str,
    context: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Iterable[Dict[str, Any]]]]:
    if llm_generate_page_premium_burst:
        iterator = iter(
            llm_generate_page_premium_burst(
                brief or "",
                seed=seed,
                count=PREMIUM_BATCH_SIZE,
                user_key=user_key,
            )
        )
        first = _next_acceptable_premium_doc(iterator, context)
        if first:
            return first, iterator
    first = _generate_single_premium_doc(brief, seed=seed, user_key=user_key, context=context)
    return first, None


def _generate_single_premium_doc(
    brief: str,
    *,
    seed: int,
    user_key: str,
    context: str,
) -> Optional[Dict[str, Any]]:
    if not llm_generate_page_premium:
        return None
    doc = llm_generate_page_premium(brief or "", seed=seed, user_key=user_key)
    if not isinstance(doc, dict) or doc.get("error"):
        return None
    issues = preflight_doc(doc)
    if preflight_has_blocking_issues(issues):
        log.info("%s: live preflight rejected output issues=%s", context, _summarize_preflight_issues(issues))
        return None
    if issues:
        doc = annotate_preflight_doc(doc, issues)
    return doc


def _premium_queue_target_size(current: int) -> int:
    return max(PREMIUM_FILL_TO, current)


def _schedule_premium_topup(background_tasks: Optional[BackgroundTasks], brief: str, target: int, *, context: str) -> None:
    if not background_tasks:
        return
    try:
        log.info(
            "%s: scheduling premium top-up queue_size=%d target=%d",
            context,
            prefetch.size("premium"),
            target,
        )
        background_tasks.add_task(_top_up_premium_queue, brief or "", target)
    except Exception:
        log.exception("%s: failed to schedule premium top-up", context)


def _top_up_premium_queue(brief: str = "", min_fill: int = PREMIUM_FILL_TO) -> None:
    if not _premium_queue_enabled() or not PREMIUM_TOPUP_ENABLED:
        return
    if not llm_generate_page_premium or not llm_premium_available():
        return
    if not _PREMIUM_TOPUP_LOCK.acquire(blocking=False):
        return
    try:
        current = prefetch.size("premium")
        target = max(int(min_fill or PREMIUM_FILL_TO), _premium_queue_target_size(current))
        attempts = 0
        max_attempts = max(1, target * 2)
        while prefetch.size("premium") < target and attempts < max_attempts:
            attempts += 1
            seed = (int(time.time() * 1000) + attempts) % 1_000_000_007
            approved = _generate_premium_batch_candidates(
                brief,
                batch_size=PREMIUM_BATCH_SIZE,
                seed=seed,
                user_key="premium-prefetch",
                context="premium.top_up",
            )
            if not approved:
                continue
            _enqueue_premium_docs(approved, context="premium.top_up", max_queue=target)
    except Exception:
        log.exception("premium.top_up: unexpected error")
    finally:
        _PREMIUM_TOPUP_LOCK.release()


def _serve_or_fill_premium_batch(
    brief: str,
    *,
    seed: int,
    user_key: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    approved = _generate_premium_batch_candidates(
        brief,
        batch_size=PREMIUM_BATCH_SIZE,
        seed=seed,
        user_key=user_key,
        context="premium.generate",
    )
    if not approved:
        return {"error": "Premium generation failed"}
    first = approved[0]
    leftovers = approved[1:]
    if leftovers:
        _enqueue_premium_docs(leftovers, context="premium.generate", max_queue=PREMIUM_FILL_TO)
    if background_tasks and _premium_queue_enabled() and prefetch.size("premium") <= PREMIUM_LOW_WATER:
        _schedule_premium_topup(background_tasks, brief or "", PREMIUM_FILL_TO, context="premium.generate")
    return first


def _stream_premium_first_page(
    brief: str,
    *,
    seed: int,
    user_key: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    first, leftovers = _start_premium_burst(
        brief,
        seed=seed,
        user_key=user_key,
        context="premium.stream.first",
    )
    if not first:
        return {"error": "Premium generation failed"}
    if leftovers and background_tasks:
        background_tasks.add_task(
            _drain_premium_burst_to_queue,
            leftovers,
            context="premium.stream.leftovers",
            max_queue=PREMIUM_FILL_TO,
            brief=brief or "",
        )
    if background_tasks and _premium_queue_enabled():
        if prefetch.size("premium") < PREMIUM_FILL_TO:
            _schedule_premium_topup(background_tasks, brief or "", PREMIUM_FILL_TO, context="premium.stream.first")
    return first


def _chunked(seq: List[Path], size: int) -> Iterable[List[Path]]:
    if size <= 0:
        size = 1
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
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


@app.get("/tailwind.css", response_class=PlainTextResponse)
def serve_tailwind():
    """Serve the built Tailwind CSS at root level (for frontend compatibility)."""
    path = TAILWIND_CSS_PATH
    if path.exists():
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/css")
    return PlainTextResponse("", status_code=404)


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/llm/status")
def llm_status_endpoint() -> Dict[str, Any]:
    return llm_status()


@app.get("/llm/probe")
def llm_probe_endpoint() -> Dict[str, Any]:
    return llm_probe()


@app.get("/metrics/total")
def metrics_total() -> JSONResponse:
    """Return the total number of websites generated across all users."""
    return JSONResponse({"total": counter.get_total()}, headers=NO_STORE_HEADERS)


@app.get("/metrics/badge")
def metrics_badge() -> JSONResponse:
    return JSONResponse(
        {
            "schemaVersion": 1,
            "label": "websites generated",
            "message": str(counter.get_total()),
            "color": "111827",
        },
        headers=NO_STORE_HEADERS,
    )


@app.get("/metrics/status")
def metrics_status(api_key: str = Depends(optional_api_key)) -> Dict[str, object]:
    _require_admin_or_dev(api_key)
    return counter.status()


# ─────────────────────────────────────────────────────────────────────────────
# Prefetch Preview API (for 3D Tunnel Hero)
# ─────────────────────────────────────────────────────────────────────────────

class QueuePreview(BaseModel):
    id: str
    title: str
    category: str
    vibe: str
    created_at: float

@app.get("/api/prefetch/previews", response_model=List[QueuePreview])
def get_prefetch_previews(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent premium queue entries for the 3D tunnel display."""
    cached = _get_cached_prefetch_previews(int(limit or 0))
    if cached is not None:
        return cached
    items = prefetch.peek(limit=limit, lane="premium")
    _set_cached_prefetch_previews(int(limit or 0), items)
    return items


@app.get("/api/premium/previews", response_model=List[QueuePreview])
def get_premium_previews(
    limit: int = 20,
    api_key: str = Depends(optional_api_key),
) -> List[Dict[str, Any]]:
    """Return recent premium queue entries for operator/debug inspection."""
    _require_admin_or_dev(api_key)
    return prefetch.peek(limit=limit, lane="premium")


@app.get("/api/prefetch/{item_id}")
def get_prefetch_entry(item_id: str) -> Dict[str, Any]:
    """Fetch a specific prefetch queue entry by token for rendering."""
    entry = prefetch.take(item_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Prefetch entry not found or already served.")
    try:
        counter.increment(1)
    except Exception:
        pass
    _record_user_visible_serve(entry)
    return entry


@app.post("/generate")
def generate_endpoint(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(optional_api_key),
):
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    premium_ready = bool(llm_generate_page_premium is not None and llm_premium_available())
    offline_allowed = os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() in {"1", "true", "yes", "on"}

    if not premium_ready:
        if offline_allowed:
            allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
            log.info("rate_limit (offline) allowed=%s remaining=%s", allowed, remaining)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content=_rate_limit_payload(reset_ts),
                    headers=_rate_limit_headers(remaining, reset_ts, limited=True),
                )
            page = {
                "components": [
                    {
                        "id": "offline-1",
                        "type": "custom",
                        "props": {
                            "html": """<div class="p-6 rounded-xl border border-slate-200 bg-white"><h3 class="text-xl font-semibold">Offline Sandbox App</h3><p class="mt-2 text-sm text-slate-700">This was rendered without an API key.</p><button id="btn" class="mt-3 px-4 py-2 rounded bg-indigo-600 text-white hover:bg-indigo-700">Click</button><div id="out" class="mt-2 text-slate-700"></div><script>let n=0; const o=document.getElementById('out');document.getElementById('btn').onclick=()=>{n++;o.textContent='Clicks: '+n;};</script></div>""",
                            "height": 260,
                        },
                    }
                ],
                "layout": {"flow": "stack"},
                "palette": {"primary": "slate", "accent": "indigo"},
                "links": ["/about"],
                "seed": req.seed or 0,
                "model_version": "offline",
                "review": {"ok": True, "issues": [], "notes": "Offline fallback page served because ALLOW_OFFLINE_GENERATION is enabled."},
            }
            return JSONResponse(page, headers=_rate_limit_headers(remaining, reset_ts))
        if os.getenv("PYTEST_CURRENT_TEST"):
            allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
            log.info("rate_limit (pytest stub) allowed=%s remaining=%s", allowed, remaining)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content=_rate_limit_payload(reset_ts),
                    headers=_rate_limit_headers(remaining, reset_ts, limited=True),
                )
            page = {
                "components": [
                    {
                        "id": "custom-1",
                        "type": "custom",
                        "props": {
                            "html": """<div class="p-4 rounded-xl border border-slate-200 bg-white"><h3 class="text-xl font-semibold">Test App</h3><div id="t" class="mt-2 text-sm text-slate-700">OK</div><script>document.getElementById('t').textContent='Rendered';</script></div>""",
                            "height": 240,
                        },
                    }
                ],
                "layout": {"flow": "stack"},
                "palette": {"primary": "slate", "accent": "indigo"},
                "links": ["/about"],
                "seed": req.seed or 0,
                "model_version": "test-stub",
            }
            return JSONResponse(page, headers=_rate_limit_headers(remaining, reset_ts))
        return JSONResponse(
            status_code=503,
            content={"error": "Missing LLM credentials"},
            headers=_rate_limit_headers(9999, int(time.time())),
        )

    allowed, remaining, reset_ts = _safe_rate_inspect("gen", client_key)
    log.info("rate_limit inspect allowed=%s remaining=%s", allowed, remaining)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=_rate_limit_payload(reset_ts),
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

    page = prefetch.dequeue("premium") if _premium_queue_enabled() else None
    if page:
        if _premium_queue_enabled() and PREMIUM_TOPUP_ENABLED and prefetch.size("premium") <= PREMIUM_LOW_WATER:
            _schedule_premium_topup(background_tasks, req.brief or "", PREMIUM_FILL_TO, context="site.generate")
    else:
        page = _stream_premium_first_page(
            req.brief or "",
            seed=req.seed or 0,
            user_key=client_key,
            background_tasks=background_tasks,
        )
    if isinstance(page, dict) and not page.get("error"):
        allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content=_rate_limit_payload(reset_ts),
                headers=_rate_limit_headers(remaining, reset_ts, limited=True),
            )
        try:
            counter.increment(1)
        except Exception:
            pass
        _record_user_visible_serve(page)
    return JSONResponse(page, headers=_rate_limit_headers(remaining, reset_ts))



@app.post("/generate/stream")
def generate_stream(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(optional_api_key),
):
    """
    NDJSON streaming endpoint: emits a couple of JSON lines.
    """
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    premium_ready = bool(llm_generate_page_premium is not None and llm_premium_available())

    if not premium_ready and os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() not in {"1", "true", "yes", "on"} and not os.getenv("PYTEST_CURRENT_TEST"):
        def _iter_error() -> Iterable[str]:
            meta = {"event": "meta", "request_id": getattr(request.state, "request_id", None)}
            yield json.dumps(meta) + "\n"
            yield json.dumps({"event": "error", "data": {"error": "Missing LLM credentials"}}) + "\n"

        return StreamingResponse(
            _iter_error(),
            media_type="application/x-ndjson",
            headers=_rate_limit_headers(9999, int(time.time())),
        )

    allowed, remaining, reset_ts = _safe_rate_inspect("gen", client_key)
    log.info("rate_limit inspect allowed=%s remaining=%s", allowed, remaining)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=_rate_limit_payload(reset_ts),
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

    def _iter() -> Iterable[str]:
        meta = {"event": "meta", "request_id": getattr(request.state, "request_id", None)}
        yield json.dumps(meta) + "\n"

        result_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)

        def _work() -> None:
            try:
                page = prefetch.dequeue("premium") if _premium_queue_enabled() else None
                if page:
                    if _premium_queue_enabled() and PREMIUM_TOPUP_ENABLED and prefetch.size("premium") <= PREMIUM_LOW_WATER:
                        _schedule_premium_topup(background_tasks, req.brief or "", PREMIUM_FILL_TO, context="site.stream")
                else:
                    page = _stream_premium_first_page(
                        req.brief or "",
                        seed=req.seed or 0,
                        user_key=client_key,
                        background_tasks=background_tasks,
                    )
                result_queue.put({"page": page})
            except Exception:
                log.exception("site.stream: generation failed")
                result_queue.put({"error": {"error": "Generation failed"}})

        worker = threading.Thread(target=_work, daemon=True)
        worker.start()
        while True:
            try:
                result = result_queue.get(timeout=max(1.0, STREAM_KEEPALIVE_SECONDS))
                break
            except queue.Empty:
                yield json.dumps({"event": "ping", "data": {"ts": int(time.time())}}) + "\n"
        if isinstance(result, dict) and result.get("error"):
            yield json.dumps({"event": "error", "data": result["error"]}) + "\n"
            return
        page = result.get("page") if isinstance(result, dict) else None
        if isinstance(page, dict) and not page.get("error"):
            allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
            if not allowed:
                yield json.dumps({"event": "error", "data": _rate_limit_payload(reset_ts)}) + "\n"
                return
            try:
                counter.increment(1)
            except Exception:
                pass
            _record_user_visible_serve(page)
            yield json.dumps({"event": "page", "data": page}) + "\n"
        else:
            yield json.dumps({"event": "error", "data": page or {"error": "Generation failed"}}) + "\n"
        return

    headers = _rate_limit_headers(remaining, reset_ts)
    return StreamingResponse(_iter(), media_type="application/x-ndjson", headers=headers)


@app.get("/prefetch/status")
def prefetch_status() -> Dict[str, Any]:
    """Return prefetch queue status and directory."""
    try:
        qsize = prefetch.size()
    except Exception:
        qsize = 0
    try:
        premium_qsize = prefetch.size("premium")
    except Exception:
        premium_qsize = 0
    return {
        "size": qsize,
        "premium_size": premium_qsize,
        "premium_queue_enabled": _premium_queue_enabled(),
        "premium_low_water": PREMIUM_LOW_WATER,
        "premium_fill_to": PREMIUM_FILL_TO,
        "premium_batch_size": PREMIUM_BATCH_SIZE,
        "premium_topup_enabled": PREMIUM_TOPUP_ENABLED,
        "stream_keepalive_seconds": STREAM_KEEPALIVE_SECONDS,
        "dir": str(prefetch.PREFETCH_DIR),
        "premium_dir": str(getattr(prefetch, "PREMIUM_PREFETCH_DIR", prefetch.PREFETCH_DIR)),
        "backend": prefetch.backend(),
        "redis_disabled_reason": getattr(prefetch, "redis_disabled_reason", lambda: "")(),
    }


## (Deprecated startup handler removed; logic moved to lifespan above)


class PrefetchRequest(BaseModel):
    brief: str = Field("", description="Optional brief to bias generation; may be empty")
    count: int = Field(10, description="How many pages to prefetch (clamped to 5-20)")


@app.post("/prefetch/fill")
def prefetch_fill(
    req: PrefetchRequest,
    request: Request,
    api_key: str = Depends(require_api_key),
):
    """Generate premium pages in advance and enqueue them for later /generate calls."""
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    allowed, remaining, reset_ts = _safe_rate_check("prefill", client_key)
    if not allowed:
        log.info("prefetch.fill: rate limited client=%s", client_key)
        return JSONResponse(
            status_code=429,
            content=_rate_limit_payload(reset_ts),
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

    premium_ready = bool(llm_generate_page_premium is not None and llm_premium_available())
    if not premium_ready:
        log.warning("prefetch.fill: premium LLM unavailable client=%s", client_key)
        return JSONResponse(
            status_code=503,
            content={"error": "Missing Gemini credentials"},
            headers=_rate_limit_headers(remaining, reset_ts),
        )

    n = prefetch.clamp_batch(int(req.count or 0))
    initial_size = prefetch.size("premium")
    target_size = initial_size + n
    new_paths: List[PrefetchHandle] = []
    generated_count = 0
    attempts = 0

    while attempts < n and generated_count < n:
        attempts += 1
        seed = (int(time.time() * 1000) + attempts) % 1_000_000_007
        try:
            requested = min(PREMIUM_BATCH_SIZE, n - generated_count)
            approved = _generate_premium_batch_candidates(
                req.brief or "",
                seed=seed,
                batch_size=requested,
                user_key="premium-prefetch",
                context="premium.fill",
            )
            added_paths = _enqueue_premium_docs(approved, context="premium.fill", max_queue=target_size)
            new_paths.extend(added_paths)
            generated_count += len(added_paths)
        except Exception as e:
            log.error("prefetch.fill: premium burst error client=%s err=%r", client_key, e)
            break

    queue_size = prefetch.size("premium")
    added = max(queue_size - initial_size, 0)

    log.info(
        "prefetch.fill: client=%s requested=%d added=%d premium_queue_size=%d",
        client_key,
        n,
        added,
        queue_size,
    )
    return JSONResponse(
        {"requested": n, "added": added, "queue_size": queue_size},
        headers=_rate_limit_headers(remaining, reset_ts),
    )


@app.post("/validate")
def validate_endpoint(req: ValidateRequest):
    """
    Validate a generated `page` against your schema (or minimal checks if schema missing).
    Returns 200 and {"detail":{"valid":true}} on success,
            422 and {"detail":{"valid":false,"errors":[...]}} on failure.
    """
    valid, errors = _validate_with_jsonschema(req.page)
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
    if preflight_has_blocking_issues(preflight_issues):
        valid = False
        errors = errors + preflight_errors
    detail = {"valid": valid}
    if not valid:
        detail["errors"] = errors
        return JSONResponse(status_code=422, content={"detail": detail})
    if preflight_errors:
        detail["warnings"] = preflight_errors
    return {"detail": detail}
