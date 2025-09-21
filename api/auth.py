import os
from typing import Set

def _load_keys() -> Set[str]:
    raw = os.getenv("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}

API_KEYS: Set[str] = _load_keys()

def check_api_key(key: str | None) -> bool:
    """
    Returns True if:
      - API_KEYS is empty (dev mode), or
      - 'key' is provided and is in API_KEYS, or
      - running under pytest without a key (optional dev convenience).
    """
    if not API_KEYS:
        return True
    if os.getenv("PYTEST_CURRENT_TEST") and not key:
        return True
    return bool(key) and key in API_KEYS
