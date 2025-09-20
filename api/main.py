from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict
import json
import logging
from api.llm_client import generate_page, llm_status


from api.validators import validate_page, collect_errors
from api.llm_client import generate_page

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Non-Deterministic Website API", version="0.1.0")

class GenerateRequest(BaseModel):
    brief: str = Field(..., description="Short description of what the page is about")
    seed: int | None = Field(None, description="Optional integer for deterministic output")
    model_version: str | None = Field(None, description="Override model id (e.g., google/gemma-3-1b-it)")

class ValidateRequest(BaseModel):
    page: Dict[str, Any]

@app.get("/health")
def health():
    return {"status": "ok"}

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
def generate_endpoint(req: GenerateRequest):
    """
    Calls the LLM (or stub), validates, and returns page JSON.
    If model fails or returns invalid JSON, a deterministic stub is returned by generate_page().
    """
    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)
    # Double-check: should already be valid, but keep this guard
    errors = collect_errors(page)
    if errors:
        raise HTTPException(status_code=502, detail={"message": "schema_validation_failed", "errors": errors})
    return page

@app.post("/generate/stream")
def generate_stream(req: GenerateRequest):
    """
    Streams NDJSON lines for each component: one JSON object per line:
    {"component": {...}}
    """
    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)

    def stream():
        for comp in page["components"]:
            yield json.dumps({"component": comp}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")

@app.get("/llm/status")
def llm_status_endpoint():
    """
    Quick status check for the LLM backend.
    Tells you if the HF token is set and which models are configured.
    """
    return llm_status()

