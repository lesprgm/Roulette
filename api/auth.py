import os
from typing import Optional, Set

from fastapi import Header, HTTPException, status


def _load_keys() -> Set[str]:
    """
    Read API_KEYS from environment:
      API_KEYS="key1,key2"  -> {"key1","key2"}
    If empty or unset -> returns empty set (auth disabled for local dev/tests).
    """
    raw = os.getenv("API_KEYS", "").strip()
    if not raw:
        return set()
    parts = []
    for token in raw.split(","):
        token = token.strip()
        if "#" in token:
            token = token.split("#", 1)[0].strip()
        if token:
            parts.append(token)
    return set(parts)


def _load_admin_keys() -> Set[str]:
    raw = os.getenv("ADMIN_API_KEYS", "").strip()
    if not raw:
        return set()
    parts = []
    for token in raw.split(","):
        token = token.strip()
        if "#" in token:
            token = token.split("#", 1)[0].strip()
        if token:
            parts.append(token)
    return set(parts)


_ADMIN_KEYS: Set[str] = _load_admin_keys()
_ALLOWED_KEYS: Set[str] = _load_keys() | _ADMIN_KEYS


def keys_required() -> bool:
    """
    True if API keys are configured (auth enforced).
    """
    return len(_ALLOWED_KEYS) > 0


def is_admin_key(key: Optional[str]) -> bool:
    if not key:
        return False
    return key.strip() in _ADMIN_KEYS


def require_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency to enforce the 'x-api-key' header
    * If API_KEYS is unset/empty -> returns "anonymous" (auth disabled).
    * If set, the header must be present and valid or we raise 401.
    Returns the caller key (or 'anonymous' in dev).
    """
    if not keys_required():
        return "anonymous"

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header",
        )
    if x_api_key not in _ALLOWED_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key


def optional_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Optional API key dependency:
    - If API_KEYS is empty -> returns "anonymous" (auth disabled).
    - If API_KEYS is set and ALLOW_PUBLIC_GENERATION=1 -> missing key is allowed ("public").
    - If a key is provided, it must be valid or we raise 401.
    """
    if not keys_required():
        return "anonymous"

    allow_public = os.getenv("ALLOW_PUBLIC_GENERATION", "0").lower() in {"1", "true", "yes", "on"}
    if not x_api_key:
        if allow_public:
            return "public"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header",
        )
    if x_api_key not in _ALLOWED_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key


def extract_client_key(possible_key: Optional[str], fallback: str = "anon") -> str:
    """
    Utility: normalize a client bucket key for rate-limiting.
    Prefer the API key if present, otherwise a fallback (like IP).
    """
    if possible_key and possible_key.strip():
        return possible_key.strip()
    return fallback
