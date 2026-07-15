import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from api import prefetch
from api.routes.generation import router as generation_router
from api.routes.metrics import router as metrics_router
from api.routes.prefetch import router as prefetch_router
from api.settings import SETTINGS


TAILWIND_CSS_PATH = Path("static/tailwind.css")

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=SETTINGS.runtime.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

log = logging.getLogger(__name__)


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
    if not SETTINGS.llm.api_key:
        log.warning("startup.check: no LLM API keys set; generation will fail in production")
    if not SETTINGS.queue.token_secret:
        log.warning("startup.check: PREFETCH_TOKEN_SECRET not set; preview tokens reset on restart")

    required_assets = [
        TAILWIND_CSS_PATH,
        Path("static/vendor/tailwind-play.js"),
        Path("static/vendor/gsap.min.js"),
        Path("static/vendor/Draggable.min.js"),
        Path("static/vendor/lucide.min.js"),
        Path("static/vendor/alpine.min.js"),
        Path("static/vendor/matter.min.js"),
        Path("static/vendor/three-addons/controls/OrbitControls.js"),
        Path("static/vendor/three-addons/controls/DragControls.js"),
        Path("static/vendor/three-addons/controls/TransformControls.js"),
        Path("static/vendor/three-addons/renderers/CSS2DRenderer.js"),
    ]
    for asset in required_assets:
        if not asset.exists():
            log.warning("startup.check: missing asset %s", asset.as_posix())

    if _is_render_env():
        cache_mount = Path("/opt/render/project/src/cache")
        prefetch_dir = SETTINGS.queue.prefetch_dir.resolve(strict=False)
        if not cache_mount.exists():
            log.warning(
                "startup.check: Render disk not mounted at %s; prefetch queue will be ephemeral",
                cache_mount,
            )
        elif not str(prefetch_dir).startswith(str(cache_mount.resolve(strict=False))):
            log.warning(
                "startup.check: PREFETCH_DIR=%s is not on Render disk %s",
                prefetch_dir,
                cache_mount,
            )

    try:
        backend = "redis" if getattr(prefetch, "_redis_enabled", lambda: False)() else "file"
        log.info("startup.check: prefetch backend=%s", backend)
    except Exception:
        log.info("startup.check: prefetch backend=unknown")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        _log_startup_checks()
    except Exception:
        log.exception("prefetch.lifespan: unexpected startup error")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SETTINGS.runtime.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path("static")
if static_dir.exists():
    if (static_dir / "js").exists():
        app.mount("/js", StaticFiles(directory=str(static_dir / "js")), name="static_js")
    if (static_dir / "css").exists():
        app.mount("/css", StaticFiles(directory=str(static_dir / "css")), name="static_css")
    app.mount("/static", StaticFiles(directory=str(static_dir), html=False), name="static")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started_at = time.time()
    request.state.request_id = request_id
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        log.info(
            "rid=%s method=%s path=%s status=%s dur_ms=%d",
            request_id,
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            int((time.time() - started_at) * 1000),
        )


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def root() -> str:
    for path in (Path("templates/index.html"), Path("index.html")):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return "<!doctype html><html><body><h1>Non-Deterministic Website</h1><p>Add templates/index.html for the UI.</p></body></html>"


@app.get("/tailwind.css", response_class=PlainTextResponse)
def serve_tailwind() -> PlainTextResponse:
    if TAILWIND_CSS_PATH.exists():
        return PlainTextResponse(
            TAILWIND_CSS_PATH.read_text(encoding="utf-8"), media_type="text/css"
        )
    return PlainTextResponse("", status_code=404)


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> Dict[str, str]:
    return {"status": "ok"}


app.include_router(metrics_router)
app.include_router(prefetch_router)
app.include_router(generation_router)
