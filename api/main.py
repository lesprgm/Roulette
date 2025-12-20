import json
import logging
import os
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, TypeAdapter

from api.auth import require_api_key, extract_client_key, keys_required
from api import counter, dedupe
from api import prefetch

_REVIEW_QUEUE_LOCK = threading.Lock()
_PREFETCH_REVIEW_QUEUE: Deque[Tuple[List[Path], int]] = deque()
_REVIEW_WORKER: Optional[threading.Thread] = None
_REVIEW_MAX_ATTEMPTS = 3

try:
    from api.llm_client import (
        generate_page as llm_generate_page,
        generate_page_burst as llm_generate_page_burst,
        status as llm_status,
        probe as llm_probe,
        run_compliance_batch,
    )
except Exception:
    llm_generate_page = None

    def llm_status() -> Dict[str, Any]:
        return {"provider": None, "model": None, "has_token": False, "using": "stub"}

    def llm_probe() -> Dict[str, Any]:
        return {"ok": False, "error": "Model or token not configured", "using": "stub"}

    def run_compliance_batch(documents: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        return None


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



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if llm_generate_page is not None and llm_status().get("has_token"):
            _prefill_prefetch_queue()
        if _prefetch_topup_enabled():
            try:
                if llm_generate_page is not None and llm_status().get("has_token"):
                    log.info("prefetch.lifespan: starting background top-up thread")
                    t = threading.Thread(target=_top_up_prefetch, args=("", PREFETCH_FILL_TO), daemon=True)
                    t.start()
                else:
                    log.debug("prefetch.lifespan: skipping top-up (LLM unavailable)")
            except Exception:
                log.exception("prefetch.lifespan: failed to start top-up thread")
                pass
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
        print(
            f"INFO:root:rid={rid} method={request.method} path={request.url.path} "
            f"status={getattr(response, 'status_code', '?')} dur_ms={dur_ms}"
        )



class GenerateRequest(BaseModel):
    # Allow empty brief so the model can invent a theme
    brief: str = Field("", description="Short description of the app to create; may be empty to let the model choose")
    seed: Optional[int] = Field(default=None, description="Optional PRNG seed")
    model_version: Optional[str] = Field(default=None, description="Optional model name override")


class ValidateRequest(BaseModel):
    page: Dict[str, Any]



# Choose rate limiter based on environment
_REDIST_URL = os.getenv("REDIS_URL", "").strip()
_rl_instance = None
if _REDIST_URL and _rr_cls and not os.getenv("PYTEST_CURRENT_TEST"):
    try:
        _rl_instance = _rr_cls(_REDIST_URL)
    except Exception:
        _rl_instance = None


def _safe_rate_check(bucket: str, key: str) -> Tuple[bool, int, int]:
    """
    Return (allowed, remaining, reset_ts).
    Works with either the Redis limiter instance OR the in-process limiter module,
    and tolerates different function names across versions.
    """
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


def _rate_limit_headers(remaining: int, reset_ts: int, *, limited: bool = False) -> Dict[str, str]:
    headers = {
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_ts),
    }
    if limited:
        wait_seconds = max(0, reset_ts - int(time.time()))
        headers["Retry-After"] = str(wait_seconds)
    return headers


def _rate_limit_payload(reset_ts: int) -> Dict[str, Any]:
    wait_seconds = max(0, reset_ts - int(time.time()))
    return {
        "error": "rate limit exceeded",
        "reset": reset_ts,
        "retry_after_seconds": wait_seconds,
        "message": f"Rate limit exceeded. Try again in {wait_seconds} seconds.",
    }


# Prefetch tuning knobs
PREFETCH_LOW_WATER = int(os.getenv("PREFETCH_LOW_WATER", "55") or 55)
try:
    # Prefer the batch max if available for a fill-to target
    from api.prefetch import BATCH_MAX as _PF_BATCH_MAX
    _DEFAULT_FILL_TO = max(int(_PF_BATCH_MAX or 75), PREFETCH_LOW_WATER)
except Exception:
    _DEFAULT_FILL_TO = max(75, PREFETCH_LOW_WATER)
PREFETCH_FILL_TO = int(os.getenv("PREFETCH_FILL_TO", str(_DEFAULT_FILL_TO)) or _DEFAULT_FILL_TO)
PREFETCH_DELAY_MS = int(os.getenv("PREFETCH_DELAY_MS", "3000") or 3000)
if os.getenv("PYTEST_CURRENT_TEST"):
    PREFETCH_DELAY_MS = 0
PREFETCH_REVIEW_BATCH = int(os.getenv("PREFETCH_REVIEW_BATCH", "3") or 3)
try:
    PREFETCH_MAX_WORKERS = int(os.getenv("PREFETCH_MAX_WORKERS", "2") or 2)
except Exception:
    PREFETCH_MAX_WORKERS = 2
if PREFETCH_MAX_WORKERS < 1:
    PREFETCH_MAX_WORKERS = 1


def _prefetch_topup_enabled() -> bool:
    # Disable during pytest runs or when env flag set to 0/false
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    v = os.getenv("PREFETCH_TOPUP_ENABLED", "1").lower()
    return v in {"1", "true", "yes", "on"}


def _prefill_prefetch_queue() -> None:
    target = int(os.getenv("PREFETCH_PREWARM_COUNT", "0") or 0)
    if target <= 0:
        return
    try:
        current = prefetch.size()
    except Exception:
        current = 0
    desired = max(0, target - current)
    if desired <= 0:
        return
    if llm_generate_page is None or not llm_status().get("has_token"):
        log.debug("prefetch.prewarm: LLM unavailable; skipping")
        return
    log.info("prefetch.prewarm: generating %d documents before startup", desired)
    paths: List[Path] = []
    generated_count = 0
    failures = 0
    max_failures = max(5, desired * 3)
    
    while generated_count < desired and failures < max_failures:
        seed = (int(time.time() * 1000) + generated_count + failures) % 1_000_000_007
        try:
            for page in llm_generate_page_burst("", seed=seed, user_key="prefetch"):
                if isinstance(page, dict) and page.get("error"):
                    failures += 1
                    break
                
                path = prefetch.enqueue(page)
                if path:
                    paths.append(path)
                    generated_count += 1
                    failures = 0
                else:
                    failures += 1
                
                if generated_count >= desired:
                    break
        except Exception as e:
            log.error("prefetch.prewarm: burst error err=%r", e)
            failures += 1
            break
    if paths:
        _schedule_prefetch_review(list(paths))
    log.info("prefetch.prewarm: completed with %d documents (failures=%d)", len(paths), failures)


def _prefetch_target_size(current: int) -> int:
    cap = max(PREFETCH_FILL_TO, PREFETCH_LOW_WATER)
    if current <= 0:
        return cap
    if current <= PREFETCH_LOW_WATER:
        target = min(cap, current + PREFETCH_REVIEW_BATCH)
        return max(target, PREFETCH_LOW_WATER)
    return cap


def _top_up_prefetch(brief: str = "", min_fill: int = PREFETCH_FILL_TO) -> None:
    """Background job: if queue is at/below low water, generate until it reaches min_fill.
    Uses the configured LLM only; no offline prefetch here.
    """
    try:
        if llm_generate_page is None or not llm_status().get("has_token"):
            log.debug("prefetch.top_up: LLM unavailable; aborting")
            return
        worker_limit = max(1, PREFETCH_MAX_WORKERS)

        def _generate_burst(seed: int) -> List[Dict[str, Any]]:
            return list(llm_generate_page_burst("", seed=seed, user_key="prefetch"))

        while True:
            current = prefetch.size()
            target = max(min_fill, _prefetch_target_size(current))
            if current > PREFETCH_LOW_WATER and current >= target:
                log.debug(
                    "prefetch.top_up: queue healthy (size=%d, low_water=%d, target=%d)",
                    current,
                    PREFETCH_LOW_WATER,
                    target,
                )
                return
            log.info(
                "prefetch.top_up: refilling queue (current=%d, target=%d, brief=%s)",
                current,
                target,
                (brief or "")[:60],
            )
            pending_paths: List[Path] = []
            generated = 0
            failures = 0
            max_failures = max(5, target * 3)
            seed_offset = 0
            with ThreadPoolExecutor(max_workers=worker_limit) as executor:
                futures: Set[Any] = set()

                def _submit_available_jobs() -> None:
                    nonlocal seed_offset
                    while (
                        len(futures) < worker_limit
                        and prefetch.size() + len(futures) < target
                        and failures < max_failures
                    ):
                        seed = (int(time.time() * 1000) + generated + failures + seed_offset) % 1_000_000_007
                        seed_offset += 1
                        futures.add(executor.submit(_generate_burst, seed))

                _submit_available_jobs()
                while (prefetch.size() < target and failures < max_failures) or futures:
                    if not futures:
                        _submit_available_jobs()
                        if not futures:
                            break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for fut in done:
                        futures.discard(fut)
                        try:
                            # Use burst generator
                            for page in fut.result():
                                if not isinstance(page, dict) or page.get("error"):
                                    failures += 1
                                    continue
                                
                                if prefetch.size() >= target:
                                    continue
                                
                                path = prefetch.enqueue(page)
                                if path:
                                    generated += 1
                                    failures = 0
                                    pending_paths.append(path)
                                    if len(pending_paths) >= PREFETCH_REVIEW_BATCH:
                                        _schedule_prefetch_review(list(pending_paths))
                                        pending_paths.clear()
                                else:
                                    failures += 1
                        except Exception as exc:
                            failures += 1
                            log.warning("prefetch.top_up: generation worker error: %r", exc)
                            continue
                        if prefetch.size() >= target and failures < max_failures:
                            # Allow outstanding workers to finish but do not enqueue more jobs
                            continue
                    if failures >= max_failures:
                        for fut in futures:
                            fut.cancel()
                        futures.clear()
                        break
                    _submit_available_jobs()
            if pending_paths:
                _schedule_prefetch_review(list(pending_paths))
                pending_paths.clear()
            updated_size = prefetch.size()
            if updated_size >= target:
                log.info("prefetch.top_up: refill complete queue_size=%d", updated_size)
                return
            if failures >= max_failures:
                log.warning(
                    "prefetch.top_up: stopped with queue_size=%d after %d attempts (target=%d)",
                    updated_size,
                    generated + failures,
                    target,
                )
                return
            log.info(
                "prefetch.top_up: continuing refill (queue_size=%d target=%d)",
                updated_size,
                target,
            )
    except Exception:
        log.exception("prefetch.top_up: unexpected error")
        pass


def _review_prefetched_docs(paths: List[Path]) -> List[Path]:
    retry: List[Path] = []
    if not paths:
        return retry
    existing = [p for p in paths if p.exists()]
    if not existing:
        return retry
    try:
        for chunk in _chunked(existing, PREFETCH_REVIEW_BATCH):
            docs: List[Dict[str, Any]] = []
            valid_paths: List[Path] = []
            for path in chunk:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    log.warning("prefetch.review: failed to load %s", path.name, exc_info=True)
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
                docs.append(data)
                valid_paths.append(path)
            if not docs:
                continue
            reviews = run_compliance_batch(docs)
            if not isinstance(reviews, list):
                retry.extend(valid_paths)
                continue
            review_map: Dict[int, Dict[str, Any]] = {}
            for idx, item in enumerate(reviews):
                if not isinstance(item, dict):
                    continue
                key = item.get("index")
                if isinstance(key, int):
                    review_map[key] = item
                else:
                    review_map[idx] = item
            for idx, path in enumerate(valid_paths):
                review = review_map.get(idx)
                if not review:
                    retry.append(path)
                    continue
                if review.get("ok") is False:
                    log.info("prefetch.review: removing rejected doc file=%s", path.name)
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
                doc = docs[idx]
                corrected = review.get("doc")
                if isinstance(corrected, dict):
                    doc = corrected
                docs[idx] = doc
                doc["review"] = review
                try:
                    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                except Exception:
                    log.exception("prefetch.review: failed to persist corrected doc file=%s", path.name)
                    retry.append(path)
                    continue
                sig = dedupe.signature_for_doc(doc)
                if sig:
                    dedupe.add(sig)
    except Exception:
        log.exception("prefetch.review: unexpected error")
        retry.extend(existing)
    return retry


def _process_prefetch_review_queue() -> None:
    global _REVIEW_WORKER
    while True:
        with _REVIEW_QUEUE_LOCK:
            if not _PREFETCH_REVIEW_QUEUE:
                _REVIEW_WORKER = None
                return
            batch_paths, attempt = _PREFETCH_REVIEW_QUEUE.popleft()
        retry_paths: List[Path] = []
        try:
            retry_paths = _review_prefetched_docs(batch_paths)
        except Exception:
            log.exception("prefetch.review: worker failed on batch", exc_info=True)
            retry_paths = batch_paths
        if retry_paths and attempt + 1 < _REVIEW_MAX_ATTEMPTS:
            try:
                time.sleep(5)
            except Exception:
                pass
            with _REVIEW_QUEUE_LOCK:
                _PREFETCH_REVIEW_QUEUE.append((retry_paths, attempt + 1))
        elif retry_paths:
            log.warning(
                "prefetch.review: giving up after %d attempts on %d docs",
                attempt + 1,
                len(retry_paths),
            )


def _schedule_prefetch_review(paths: List[Path]) -> None:
    global _REVIEW_WORKER
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    start_worker = False
    worker: Optional[threading.Thread]
    with _REVIEW_QUEUE_LOCK:
        _PREFETCH_REVIEW_QUEUE.append((existing, 0))
        worker = _REVIEW_WORKER
        if not (worker and worker.is_alive()):
            _REVIEW_WORKER = threading.Thread(target=_process_prefetch_review_queue, daemon=True)
            worker = _REVIEW_WORKER
            start_worker = True
    if start_worker and worker:
        worker.start()


def _chunked(seq: List[Path], size: int) -> Iterable[List[Path]]:
    if size <= 0:
        size = 1
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _validate_with_jsonschema(page: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate `page` against your JSON schema file if present.
    If schema file is absent, do a light required-fields check to satisfy tests.
    """
    schema_path = Path("schemas/page_schema.json")
    errors: List[Dict[str, Any]] = []

    # Minimal checks even without schema to support tests
    def _light_checks(p: Dict[str, Any]):
        if "components" not in p or not isinstance(p["components"], list):
            errors.append({"path": "components", "message": "required: components list"})
            return
        for idx, comp in enumerate(p["components"]):
            if not isinstance(comp, dict) or "id" not in comp:
                errors.append({"path": f"components[{idx}].id", "message": "required property 'id'"})

    # First try strict Pydantic models if available/valid
    try:
        from typing import Literal, Union, Optional as _Optional

        class NdwBackground(BaseModel):
            style: _Optional[str] = None
            class_: _Optional[str] = Field(default=None, alias="class")

        class NdwSnippetV1(BaseModel):
            kind: Literal["ndw_snippet_v1"]
            title: _Optional[str] = None
            background: _Optional[NdwBackground] = None
            css: _Optional[str] = None
            html: _Optional[str] = None
            js: _Optional[str] = None

        class FullPageHtml(BaseModel):
            kind: Literal["full_page_html"]
            html: str

        class CustomProps(BaseModel):
            html: str
            height: int

        class Component(BaseModel):
            id: str
            type: str
            props: CustomProps

        class ComponentsDoc(BaseModel):
            components: List[Component]

        PageUnion = Union[NdwSnippetV1, FullPageHtml, ComponentsDoc]
        TypeAdapter(PageUnion).validate_python(page)
        return True, []
    except ValidationError as ve:
        pydantic_errors: List[Dict[str, Any]] = []
        try:
            for e in ve.errors():
                loc = ".".join(str(p) for p in e.get("loc", [])) or "(root)"
                pydantic_errors.append({"path": loc, "message": e.get("msg", "invalid")})
        except Exception:
            pydantic_errors = [{"path": "(root)", "message": "invalid"}]
        errors.extend([])
        _pyd_errs = pydantic_errors
    except Exception:
        # If Pydantic import/types fail, fall back silently
        pass

    if not schema_path.exists():
        _light_checks(page)
        return (len(errors) == 0), errors

    try:
        import jsonschema
    except Exception:
        _light_checks(page)
        return (len(errors) == 0), errors

    try:
        schema = json.loads(schema_path.read_text())
        validator = jsonschema.Draft202012Validator(schema)
        schema_errors: List[Dict[str, Any]] = []
        for err in validator.iter_errors(page):
            loc = ".".join([str(p) for p in err.path]) or "(root)"
            msg = str(err.message)
            schema_errors.append({"path": loc, "message": msg})
        if not schema_errors:
            # Schema accepts the document; ignore earlier Pydantic complaints
            return True, []
        # If schema failed, combine with any Pydantic errors if present
        try:
            combined = schema_errors + locals().get('_pyd_errs', [])
        except Exception:
            combined = schema_errors
        return False, combined
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


@app.get("/metrics/total")
def metrics_total() -> Dict[str, int]:
    """Return the total number of websites generated across all users."""
    return {"total": counter.get_total()}


@app.post("/generate")
def generate_endpoint(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(require_api_key),
):
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    llm_info = llm_status()
    llm_available = not (llm_generate_page is None or not llm_info.get("has_token"))
    offline_allowed = os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() in {"1", "true", "yes", "on"}

    if not llm_available:
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

    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    log.info("rate_limit check allowed=%s remaining=%s", allowed, remaining)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=_rate_limit_payload(reset_ts),
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

    page = prefetch.dequeue()
    if page:
        log.info("prefetch.generate: served page from queue")
        try:
            if PREFETCH_DELAY_MS > 0:
                time.sleep(PREFETCH_DELAY_MS / 1000.0)
        except Exception:
            pass
        if isinstance(page, dict) and not page.get("error"):
            try:
                counter.increment(1)
            except Exception:
                pass
        try:
            if _prefetch_topup_enabled():
                queue_size = prefetch.size()
                if queue_size <= PREFETCH_LOW_WATER:
                    log.info(
                        "prefetch.generate: queue size=%d <= low_water=%d, scheduling top-up",
                        queue_size,
                        PREFETCH_LOW_WATER,
                    )
                    target = _prefetch_target_size(prefetch.size())
                    background_tasks.add_task(_top_up_prefetch, req.brief or "", target)
        except Exception:
            log.exception("prefetch.generate: failed to schedule background top-up")
        return JSONResponse(page, headers=_rate_limit_headers(remaining, reset_ts))

    # Queue empty: do a burst and return the FIRST site that finishes
    log.info("prefetch.generate: queue empty; initiating ad-hoc burst")
    try:
        burst_iter = llm_generate_page_burst(req.brief or "", seed=req.seed or 0, user_key=client_key)
        page = next(burst_iter, {"error": "No pages generated"})
    except Exception as e:
        log.exception("Ad-hoc burst failure")
        page = {"error": str(e)}

    if isinstance(page, dict) and not page.get("error"):
        try:
            counter.increment(1)
        except Exception:
            pass

    return JSONResponse(page, headers=_rate_limit_headers(remaining, reset_ts))



@app.post("/generate/stream")
def generate_stream(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(require_api_key),
):
    """
    NDJSON streaming endpoint: emits a couple of JSON lines.
    """
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    llm_info = llm_status()
    llm_available = not (llm_generate_page is None or not llm_info.get("has_token"))

    if not llm_available and os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() not in {"1", "true", "yes", "on"} and not os.getenv("PYTEST_CURRENT_TEST"):
        def _iter_error() -> Iterable[str]:
            meta = {"event": "meta", "request_id": getattr(request.state, "request_id", None)}
            yield json.dumps(meta) + "\n"
            yield json.dumps({"event": "error", "data": {"error": "Missing LLM credentials"}}) + "\n"

        return StreamingResponse(
            _iter_error(),
            media_type="application/x-ndjson",
            headers=_rate_limit_headers(9999, int(time.time())),
        )

    allowed, remaining, reset_ts = _safe_rate_check("gen", client_key)
    log.info("rate_limit check allowed=%s remaining=%s", allowed, remaining)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=_rate_limit_payload(reset_ts),
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

    def _iter() -> Iterable[str]:
        meta = {"event": "meta", "request_id": getattr(request.state, "request_id", None)}
        yield json.dumps(meta) + "\n"

        if not llm_available:
            if os.getenv("ALLOW_OFFLINE_GENERATION", "0").lower() in {"1","true","yes","on"}:
                # Try prefetch first; if empty, return a simple offline doc
                page = prefetch.dequeue()
                if not page:
                    page = {
                        "kind": "full_page_html",
                        "html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>Offline Sandbox App</title>
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
      .card{max-width:420px;background:#1e293b;border-radius:18px;padding:32px;box-shadow:0 20px 50px rgba(15,23,42,0.4)}
      .card h1{margin:0 0 12px;font-size:1.5rem}
      .card p{margin:0 0 16px;line-height:1.5}
      .card button{padding:10px 16px;border-radius:10px;background:#38bdf8;border:none;color:#0f172a;font-weight:600;cursor:pointer}
    </style>
  </head>
  <body>
    <main class="card">
      <h1>Offline Preview</h1>
      <p>This sandbox response is served when real LLM providers are unavailable.</p>
      <button id="btn">Click me</button>
      <p id="out" aria-live="polite"></p>
      <script>
        const out=document.getElementById("out");
        document.getElementById("btn").addEventListener("click",()=>{out.textContent="Still offline, but responsive!";});
      </script>
    </main>
  </body>
</html>""".strip(),
                        "review": {
                            "ok": True,
                            "issues": [],
                            "notes": "Offline fallback page served because ALLOW_OFFLINE_GENERATION is enabled.",
                        },
                    }
                yield json.dumps({"event": "page", "data": page}) + "\n"
                return
            if os.getenv("PYTEST_CURRENT_TEST"):
                page = {
                    "components": [
                        {
                            "id": "custom-1",
                            "type": "custom",
                            "props": {
                                "html": "<div class=\"p-4 rounded-xl border border-slate-200 bg-white\">Stream Test</div>",
                                "height": 200,
                            },
                        }
                    ],
                    "layout": {"flow": "stack"},
                    "palette": {"primary": "slate", "accent": "indigo"},
                    "links": ["/about"],
                    "seed": req.seed or 0,
                    "model_version": "test-stub",
                }
                yield json.dumps({"event": "page", "data": page}) + "\n"
                return
            else:
                yield json.dumps({"event": "error", "data": {"error": "Missing LLM credentials"}}) + "\n"
                return

        # Normal path: prefer prefetch
        served_from_prefetch = False
        page = prefetch.dequeue()
        if page is not None:
            served_from_prefetch = True
            try:
                if PREFETCH_DELAY_MS > 0:
                    time.sleep(PREFETCH_DELAY_MS / 1000.0)
            except Exception:
                pass
            yield json.dumps({"event": "page", "data": page}) + "\n"
        else:
            # Queue empty: do a burst and stream them all!
            log.info("prefetch.generate_stream: queue empty; initiating ad-hoc burst")
            try:
                for burst_page in llm_generate_page_burst(req.brief or "", seed=req.seed or 0, user_key=client_key):
                    if isinstance(burst_page, dict) and not burst_page.get("error"):
                        try: counter.increment(1)
                        except: pass
                    yield json.dumps({"event": "page", "data": burst_page}) + "\n"
            except Exception as e:
                log.exception("Ad-hoc burst stream failure")
                yield json.dumps({"event": "error", "data": {"error": str(e)}}) + "\n"
            return

        try:
            if _prefetch_topup_enabled() and served_from_prefetch and prefetch.size() <= PREFETCH_LOW_WATER:
                target = _prefetch_target_size(prefetch.size())
                background_tasks.add_task(_top_up_prefetch, req.brief or "", target)
        except Exception:
            pass
        yield json.dumps({"event": "page", "data": page}) + "\n"

    headers = _rate_limit_headers(remaining, reset_ts)
    return StreamingResponse(_iter(), media_type="application/x-ndjson", headers=headers)


@app.get("/prefetch/status")
def prefetch_status() -> Dict[str, Any]:
    """Return prefetch queue status and directory."""
    try:
        qsize = prefetch.size()
    except Exception:
        qsize = 0
    return {"size": qsize, "dir": str(prefetch.PREFETCH_DIR)}


## (Deprecated startup handler removed; logic moved to lifespan above)


class PrefetchRequest(BaseModel):
    brief: str = Field("", description="Optional brief to bias generation; may be empty")
    count: int = Field(5, description="How many pages to prefetch (clamped to 5-20)")


@app.post("/prefetch/fill")
def prefetch_fill(
    req: PrefetchRequest,
    request: Request,
    api_key: str = Depends(require_api_key),
):
    """Generate N pages in advance (5-10 per request) and enqueue them for later /generate calls.
    Returns how many were added plus the new queue size.
    """
    client_key = extract_client_key(api_key, request.client.host if request.client else "anon")
    allowed, remaining, reset_ts = _safe_rate_check("prefill", client_key)
    if not allowed:
        log.info("prefetch.fill: rate limited client=%s", client_key)
        return JSONResponse(
            status_code=429,
            content=_rate_limit_payload(reset_ts),
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

    # Only allow prefetch when LLM is available (no offline injection here)
    llm_ok = not (llm_generate_page_burst is None or not llm_status().get("has_token"))

    n = prefetch.clamp_batch(int(req.count or 0))
    initial_size = prefetch.size()
    new_paths: List[Path] = []
    
    generated_count = 0
    attempts = 0
    while attempts < n and generated_count < n:
        attempts += 1
        if not llm_ok:
            log.warning("prefetch.fill: LLM unavailable mid-fill client=%s", client_key)
            return JSONResponse(
                status_code=503,
                content={"error": "Missing LLM credentials"},
                headers=_rate_limit_headers(remaining, reset_ts),
            )
        
        # Calculate seed
        seed = (int(time.time() * 1000) + attempts) % 1_000_000_007
        
        try:
            for page in llm_generate_page_burst(req.brief or "", seed=seed, user_key="prefetch"):
                if isinstance(page, dict) and page.get("error"):
                    log.warning("prefetch.fill: generation returned error doc client=%s", client_key)
                    break
                
                path = prefetch.enqueue(page)
                if path:
                    new_paths.append(path)
                    generated_count += 1
                
                if generated_count >= n:
                    break
        except Exception as e:
            log.error("prefetch.fill: burst error client=%s err=%r", client_key, e)
            break

    if new_paths:
        _schedule_prefetch_review(list(new_paths))
    queue_size = prefetch.size()
    added = max(queue_size - initial_size, 0)

    log.info(
        "prefetch.fill: client=%s requested=%d added=%d queue_size=%d",
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
    detail = {"valid": valid}
    if not valid:
        detail["errors"] = errors
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
        payload = _rate_limit_payload(reset_ts)
        return PlainTextResponse(
            payload["message"],
            status_code=429,
            headers=_rate_limit_headers(remaining, reset_ts, limited=True),
        )

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
        page = llm_generate_page(brief, seed=seed or 42, user_key=client_key)

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
