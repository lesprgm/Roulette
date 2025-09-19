import random
from typing import Optional

def generate_page(brief: str, seed: Optional[int] = None, model_version: str = "v0") -> dict:
    rng = random.Random(seed or 42)

    title = brief[:32] or "Welcome"
    subtitle = "Fast, cached pages"

    palette_primary = rng.choice(["slate", "gray", "zinc", "stone"])
    palette_accent = rng.choice(["indigo", "violet", "emerald", "cyan"])

    page = {
        "components": [
            {"id": "hero-1", "type": "hero",
             "props": {"title": title, "subtitle": subtitle}}
        ],
        "layout": {"flow": "stack"},
        "palette": {"primary": palette_primary, "accent": palette_accent},
        "links": ["/about"],
        "seed": seed or 42,
        "model_version": model_version,
    }
    return page
