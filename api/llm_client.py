import os
import json
import random
import logging
import requests
from typing import Optional
from dotenv import load_dotenv
from api.validators import collect_errors

log = logging.getLogger(__name__)
load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

# Start with a small, widely available model; try a 4B as a fallback.
CANDIDATE_MODELS = [
    "google/gemma-3-1b-it",
    "google/gemma-3-4b-it",
]

SYSTEM_PROMPT = """You are a planner. Output ONE JSON object that VALIDATES against my schema.
Rules:
- Output JSON only. No prose, markdown, or comments.
- Must include: components[], layout, palette, links, seed (int), model_version (string).
- For components: each item must have id, type ∈ {hero, card, cta, grid, text, image}, props as an object.
- Keep props concise and schema-friendly (no HTML, no markdown).
- If you cannot satisfy the schema, output exactly: {"error":"schema_violation"}.
"""

def _query_hf(model: str, prompt: str) -> str:
    """
    Calls the Hugging Face Inference API for a given model.
    Returns the generated text (string). Raises for HTTP errors or unexpected shapes.
    """
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set. Put it in your .env")

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}
    resp = requests.post(url, headers=headers, json=payload, timeout=90)

    # 404/403 → you likely haven’t accepted access to the repo yet
    if resp.status_code in (403, 404):
        raise FileNotFoundError(f"Model unavailable via HF API: {model} ({resp.status_code})")

    # 503 sometimes means “model is loading”; bubble it up for a retry at higher level
    resp.raise_for_status()

    data = resp.json()
    # Common response: [{"generated_text": "..."}]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
        return data[0]["generated_text"]
    # Some backends return a raw string
    if isinstance(data, str):
        return data
    # Last-ditch: try common keys
    if isinstance(data, dict):
        for k in ("generated_text", "text", "output"):
            if k in data:
                return data[k]

    raise RuntimeError(f"Unexpected HF response shape: {data}")

def _fallback_stub(brief: str, seed: Optional[int], model_label: str) -> dict:
    """
    Deterministic local fallback so your API keeps working even if the remote model fails.
    """
    rng = random.Random(seed or 42)
    return {
        "components": [
            {"id": "hero-1", "type": "hero",
             "props": {"title": (brief[:32] or "Welcome"), "subtitle": "Fast, cached pages"}}
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": rng.choice(["slate", "gray"]), "accent": rng.choice(["indigo", "emerald"])},
        "links": ["/about"],
        "seed": seed or 42,
        "model_version": model_label,
    }

def generate_page(brief: str, seed: Optional[int] = None, model_version: Optional[str] = None) -> dict:
    """
    High-level function your API calls.
    1) Builds a strict prompt.
    2) Tries the provided model_version (if any), else tries candidates in order.
    3) Parses JSON, validates against your schema, returns the page.
    4) If everything fails, returns the deterministic stub (so your UI doesn’t break).
    """
    prompt = f"{SYSTEM_PROMPT}\nBrief: {brief}\nSeed: {seed or 42}"
    last_err: Exception | None = None

    # List of models to try this call
    models_to_try = [model_version] if model_version else []
    models_to_try += [m for m in CANDIDATE_MODELS if m not in models_to_try]

    for model in models_to_try:
        try:
            text = _query_hf(model, prompt)
            data = json.loads(text)
            errors = collect_errors(data)
            if errors:
                log.warning("LLM schema fail for %s: %s", model, errors)
                raise RuntimeError(f"Schema validation failed: {errors}")
            log.info("LLM: %s ok (seed=%s)", model, seed or 42)
            return data
        except FileNotFoundError as e:
            log.warning("Model not available: %s", e)
            last_err = e
            continue
        except Exception as e:
            log.error("LLM call failed for %s: %s", model, e)
            last_err = e
            # If it’s a transient 503 you could continue; we stop here to avoid long loops.
            break

    # Fallback stub keeps the app usable
    log.warning("Falling back to deterministic stub due to: %s", last_err)
    return _fallback_stub(brief, seed, (model_version or CANDIDATE_MODELS[0]))

def llm_status() -> dict:
    """
    Report which models are configured and whether HF_TOKEN is set.
    This does NOT make a network call — it's just a quick check.
    """
    return {
        "hf_token_set": bool(HF_TOKEN),
        "candidate_models": CANDIDATE_MODELS,
        "default_model": os.getenv("MODEL_NAME", CANDIDATE_MODELS[0]),
    }

