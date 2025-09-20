import os, json, hashlib, time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(os.getenv("CACHE_DIR", "cache/pages"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "0"))  

def _key(brief: str, seed: int | None, model_version: str | None, schema_version: str = "v1") -> str:
    h = hashlib.sha256()
    h.update((brief or "").encode("utf-8"))
    h.update(("\n" + str(seed)).encode("utf-8"))
    h.update(("\n" + (model_version or "")).encode("utf-8"))
    h.update(("\n" + schema_version).encode("utf-8"))
    return h.hexdigest()

def get(brief: str, seed: int | None, model_version: str | None) -> Optional[dict[str, Any]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(brief, seed, model_version)}.json"
    if not path.exists():
        return None
    if CACHE_TTL_SECONDS > 0:
        if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
            try: path.unlink()
            except: pass
            return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def set(brief: str, seed: int | None, model_version: str | None, page: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(brief, seed, model_version)}.json"
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(page, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)
