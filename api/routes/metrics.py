from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api import counter
from api.auth import optional_api_key
from api.generation import premium_service
from api.routes import shared


router = APIRouter()
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


@router.get("/llm/status")
def llm_status_endpoint() -> Dict[str, Any]:
    return premium_service.llm_status()


@router.get("/llm/probe")
def llm_probe_endpoint() -> Dict[str, Any]:
    return premium_service.llm_probe()


@router.get("/metrics/total")
def metrics_total() -> JSONResponse:
    return JSONResponse({"total": counter.get_total()}, headers=NO_STORE_HEADERS)


@router.get("/metrics/badge")
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


@router.get("/metrics/status")
def metrics_status(api_key: str = Depends(optional_api_key)) -> Dict[str, object]:
    shared.require_admin_or_dev(api_key)
    return counter.status()
