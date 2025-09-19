from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict

from api.validators import validate_page, collect_errors
from api.llm_client import generate_page

app = FastAPI(title="Non-Deterministic Website API", version="0.1.0")

class GenerateRequest(BaseModel):
    brief: str = Field(..., description="Short description of what the page is about")
    seed: int | None = Field(None, description="Optional integer for deterministic output")
    model_version: str = Field("v0", description="Version tag for your model/prompt")

class ValidateRequest(BaseModel):
    page: Dict[str, Any]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/validate")
def validate_endpoint(payload: ValidateRequest):
    try:
        validate_page(payload.page)
        return {"valid": True}
    except Exception:
        errors = collect_errors(payload.page)
        raise HTTPException(status_code=422, detail={"valid": False, "errors": errors})

@app.post("/generate")
def generate_endpoint(req: GenerateRequest):
    page = generate_page(req.brief, seed=req.seed, model_version=req.model_version)
    errors = collect_errors(page)
    if errors:
        # Upstream model produced invalid JSON for the schema
        raise HTTPException(status_code=502, detail={"message": "schema_validation_failed", "errors": errors})
    return page
