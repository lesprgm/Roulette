from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _text(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    value = _text(name).lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


def _int(name: str, default: int, *, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        value = int(_text(name, str(default)) or default)
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float(name: str, default: float, *, minimum: Optional[float] = None) -> float:
    try:
        value = float(_text(name, str(default)) or default)
    except ValueError:
        value = default
    return max(minimum, value) if minimum is not None else value


@dataclass(frozen=True)
class LlmSettings:
    temperature: float
    timeout_seconds: int
    gemini_max_output_tokens: int
    premium_build_max_output_tokens: int
    premium_burst_min_html_bytes: int
    thinking_level: str
    api_key: str
    generation_model: str
    fallback_model: str
    high_demand_cooldown_seconds: int


@dataclass(frozen=True)
class QueueSettings:
    prefetch_dir: Path
    premium_prefetch_dir: Path
    batch_min: int
    batch_max: int
    drop_test_fixture_docs: bool
    redis_queue_key: str
    redis_doc_prefix: str
    premium_redis_queue_key: str
    premium_redis_doc_prefix: str
    redis_healthcheck: bool
    token_ttl_seconds: int
    premium_token_ttl_seconds: int
    token_secret: str
    premium_enabled: bool
    premium_low_water: int
    premium_fill_to: int
    premium_batch_size: int
    premium_topup_enabled: bool


@dataclass(frozen=True)
class RateLimitSettings:
    window_seconds: int
    max_requests: int
    premium_window_seconds: int
    premium_daily_limit: int


@dataclass(frozen=True)
class StorageSettings:
    redis_url: str
    counter_file: Path
    redis_counter_key: str
    redis_counter_timeout: float
    counter_baseline: int
    dedupe_enabled: bool
    dedupe_file: Path
    dedupe_max: int
    diversity_enabled: bool
    diversity_html_cache_ttl_seconds: int
    diversity_fingerprint_ttl_seconds: int
    novelty_ledger_path: Path
    novelty_ledger_size: int


@dataclass(frozen=True)
class RuntimeSettings:
    log_level: str
    allowed_origins: Tuple[str, ...]
    prefetch_preview_cache_ttl: float
    stream_keepalive_seconds: float
    preflight_html_warn_bytes: int
    preflight_html_block_bytes: int


@dataclass(frozen=True)
class Settings:
    llm: LlmSettings
    queue: QueueSettings
    rate_limit: RateLimitSettings
    storage: StorageSettings
    runtime: RuntimeSettings


def load_settings() -> Settings:
    batch_min = _int("PREFETCH_BATCH_MIN", 5, minimum=1)
    batch_max = _int("PREFETCH_BATCH_MAX", 20, minimum=batch_min)
    html_warn_bytes = _int("PREFLIGHT_HTML_WARN_BYTES", 180_000, minimum=1)
    html_block_bytes = _int("PREFLIGHT_HTML_BLOCK_BYTES", 280_000, minimum=html_warn_bytes)
    thinking_level = _text("GEMINI_THINKING_LEVEL", "medium").lower()
    if thinking_level not in {"minimal", "low", "medium", "high"}:
        thinking_level = "medium"
    origins = tuple(origin.strip() for origin in os.getenv("ALLOW_ORIGINS", "*").split(",") if origin.strip())

    return Settings(
        llm=LlmSettings(
            temperature=_float("TEMPERATURE", 1.5, minimum=0.0),
            timeout_seconds=_int("LLM_TIMEOUT_SECS", 105, minimum=1),
            gemini_max_output_tokens=_int("GEMINI_MAX_OUTPUT_TOKENS", 64_000, minimum=1),
            premium_build_max_output_tokens=_int("GEMINI_PREMIUM_BUILD_MAX_OUTPUT_TOKENS", 0, minimum=0),
            premium_burst_min_html_bytes=_int("PREMIUM_BURST_MIN_HTML_BYTES", 3_000, minimum=0),
            thinking_level=thinking_level,
            api_key=_text("GEMINI_API_KEY"),
            generation_model=_text("GEMINI_GENERATION_MODEL", "gemini-3.5-flash"),
            fallback_model=_text("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview"),
            high_demand_cooldown_seconds=_int("GEMINI_HIGH_DEMAND_COOLDOWN_SECONDS", 180, minimum=0),
        ),
        queue=QueueSettings(
            prefetch_dir=Path(_text("PREFETCH_DIR", "cache/prefetch")),
            premium_prefetch_dir=Path(_text("PREMIUM_PREFETCH_DIR", "cache/premium_prefetch")),
            batch_min=batch_min,
            batch_max=batch_max,
            drop_test_fixture_docs=_bool("PREFETCH_DROP_TEST_FIXTURES", True),
            redis_queue_key=_text("PREFETCH_REDIS_QUEUE_KEY", "ndw:prefetch:queue"),
            redis_doc_prefix=_text("PREFETCH_REDIS_DOC_PREFIX", "ndw:prefetch:doc:"),
            premium_redis_queue_key=_text("PREMIUM_REDIS_QUEUE_KEY", "ndw:premium:queue"),
            premium_redis_doc_prefix=_text("PREMIUM_REDIS_DOC_PREFIX", "ndw:premium:doc:"),
            redis_healthcheck=_bool("PREFETCH_REDIS_HEALTHCHECK", True),
            token_ttl_seconds=_int("PREFETCH_TOKEN_TTL_SECONDS", 1_800, minimum=1),
            premium_token_ttl_seconds=_int("PREMIUM_TOKEN_TTL_SECONDS", 900, minimum=1),
            token_secret=_text("PREFETCH_TOKEN_SECRET"),
            premium_enabled=_bool("PREMIUM_QUEUE_ENABLED", True),
            premium_low_water=_int("PREMIUM_LOW_WATER", 3, minimum=0),
            premium_fill_to=_int("PREMIUM_FILL_TO", 10, minimum=1),
            premium_batch_size=_int("PREMIUM_BATCH_SIZE", 7, minimum=1, maximum=50),
            premium_topup_enabled=_bool("PREMIUM_TOPUP_ENABLED", False),
        ),
        rate_limit=RateLimitSettings(
            window_seconds=_int("RATE_WINDOW_SECONDS", 10_800, minimum=60),
            max_requests=_int("RATE_MAX_REQUESTS", 30, minimum=1),
            premium_window_seconds=_int("PREMIUM_WINDOW_SECONDS", 86_400, minimum=60),
            premium_daily_limit=_int("PREMIUM_DAILY_LIMIT", 5, minimum=1),
        ),
        storage=StorageSettings(
            redis_url=_text("REDIS_URL"),
            counter_file=Path(_text("COUNTER_FILE", "cache/counter.json")),
            redis_counter_key=_text("REDIS_COUNTER_KEY", "ndw:metrics:total"),
            redis_counter_timeout=_float("REDIS_COUNTER_TIMEOUT", 2.0, minimum=0.1),
            counter_baseline=_int("COUNTER_BASELINE", 0, minimum=0),
            dedupe_enabled=_bool("DEDUPE_ENABLED", True),
            dedupe_file=Path(_text("DEDUPE_RECENT_FILE", "cache/seen_pages.json")),
            dedupe_max=_int("DEDUPE_MAX", 200, minimum=1),
            diversity_enabled=_bool("REDIS_DIVERSITY_ENABLED", True),
            diversity_html_cache_ttl_seconds=_int("DIVERSITY_HTML_CACHE_TTL_SECONDS", 604_800, minimum=1),
            diversity_fingerprint_ttl_seconds=_int("DIVERSITY_FINGERPRINT_TTL_SECONDS", 604_800, minimum=1),
            novelty_ledger_path=Path(_text("NOVELTY_LEDGER_PATH", "cache/novelty_ledger.json")),
            novelty_ledger_size=_int("NOVELTY_LEDGER_SIZE", 80, minimum=10),
        ),
        runtime=RuntimeSettings(
            log_level=_text("LOG_LEVEL", "INFO").upper(),
            allowed_origins=origins or ("*",),
            prefetch_preview_cache_ttl=_float("PREFETCH_PREVIEW_CACHE_TTL", 2.0, minimum=0.0),
            stream_keepalive_seconds=_float("STREAM_KEEPALIVE_SECONDS", 8.0, minimum=0.1),
            preflight_html_warn_bytes=html_warn_bytes,
            preflight_html_block_bytes=html_block_bytes,
        ),
    )


SETTINGS = load_settings()
