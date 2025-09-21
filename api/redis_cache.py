import os, json, hashlib
from typing import Optional, Any
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "0"))  # 0 = never expire

_redis = redis.from_url(REDIS_URL, decode_responses=True)

def _key(brief: str, seed: int | None, model_version: str | None, schema_version: str = "v1") -> str:
    h = hashlib.sha256()
    h.update((brief or "").encode("utf-8"))
    h.update(("\n" + str(seed)).encode("utf-8"))
    h.update(("\n" + (model_version or "")).encode("utf-8"))
    h.update(("\n" + schema_version).encode("utf-8"))
    return f"page:{h.hexdigest()}"

def get(brief: str, seed: int | None, model_version: str | None) -> Optional[dict[str, Any]]:
    k = _key(brief, seed, model_version)
    raw = _redis.get(k)
    return json.loads(raw) if raw else None

def set(brief: str, seed: int | None, model_version: str | None, page: dict[str, Any]) -> None:
    k = _key(brief, seed, model_version)
    raw = json.dumps(page, separators=(",", ":"), ensure_ascii=False)
    if CACHE_TTL_SECONDS > 0:
        _redis.setex(k, CACHE_TTL_SECONDS, raw)
    else:
        _redis.set(k, raw)
