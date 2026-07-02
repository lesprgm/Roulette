from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

from api.llm_parsing import _json_from_text

JsonExtractor = Callable[[Dict[str, Any]], Optional[str]]

_tls = threading.local()
_high_demand_lock = threading.Lock()
_high_demand_until = 0.0

try:
    HIGH_DEMAND_COOLDOWN_SECONDS = int(os.getenv("GEMINI_HIGH_DEMAND_COOLDOWN_SECONDS", "180"))
except Exception:
    HIGH_DEMAND_COOLDOWN_SECONDS = 180


def _quota_flag_set(val: bool) -> None:
    _tls.quota_exhausted = val


def was_quota_exhausted() -> bool:
    return getattr(_tls, "quota_exhausted", False)


def high_demand_retry_after_seconds() -> int:
    with _high_demand_lock:
        remaining = int(max(0, _high_demand_until - time.time()))
    return remaining


def is_high_demand_blocked() -> bool:
    return high_demand_retry_after_seconds() > 0


def is_high_demand_response(resp: requests.Response) -> bool:
    if resp.status_code != 503:
        return False
    try:
        text = resp.text[:800].lower()
    except Exception:
        text = ""
    return "unavailable" in text or "high demand" in text


def mark_high_demand(label: str) -> None:
    if HIGH_DEMAND_COOLDOWN_SECONDS <= 0:
        return
    until = time.time() + HIGH_DEMAND_COOLDOWN_SECONDS
    with _high_demand_lock:
        global _high_demand_until
        _high_demand_until = max(_high_demand_until, until)
    logging.warning(
        "Gemini high-demand cooldown active after %s for %ss",
        label,
        HIGH_DEMAND_COOLDOWN_SECONDS,
    )


def call_structured(
    *,
    parts: List[Dict[str, Any]],
    schema: Dict[str, Any],
    api_key: str,
    endpoint: str,
    fallback_endpoint: str = "",
    temperature: float,
    max_output_tokens: int,
    timeout_secs: int,
    thinking_level: str = "",
    extract_text: JsonExtractor,
    retry_without_thinking: bool = True,
) -> Optional[Any]:
    if is_high_demand_blocked():
        logging.warning("Gemini structured skipped during high-demand cooldown (%ss remaining)", high_demand_retry_after_seconds())
        _quota_flag_set(False)
        return None

    generation_config = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
        "responseMimeType": "application/json",
        "responseSchema": schema,
    }
    if thinking_level:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config,
    }
    endpoints = [endpoint]
    if fallback_endpoint:
        endpoints.append(fallback_endpoint)
    _quota_flag_set(True)
    for idx, target_endpoint in enumerate(endpoints):
        label = "primary" if idx == 0 else "fallback"
        try:
            resp = requests.post(
                target_endpoint,
                params={"key": api_key},
                json=body,
                timeout=timeout_secs,
            )
        except Exception as exc:
            logging.warning("Gemini structured %s request error: %r", label, exc)
            _quota_flag_set(False)
            continue

        if retry_without_thinking and resp.status_code == 400 and "thinkingConfig" in generation_config:
            retry_config = dict(generation_config)
            retry_config.pop("thinkingConfig", None)
            retry_body = dict(body)
            retry_body["generationConfig"] = retry_config
            try:
                resp = requests.post(
                    target_endpoint,
                    params={"key": api_key},
                    json=retry_body,
                    timeout=timeout_secs,
                )
                if resp.status_code == 200:
                    logging.info("Gemini structured %s succeeded after removing thinkingConfig", label)
            except Exception as exc:
                logging.warning("Gemini structured %s retry without thinkingConfig error: %r", label, exc)
                _quota_flag_set(False)
                continue

        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Gemini structured %s HTTP %s: %s", label, resp.status_code, msg)
            if is_high_demand_response(resp):
                mark_high_demand(f"structured {label}")
                _quota_flag_set(False)
                break
            if resp.status_code != 429:
                _quota_flag_set(False)
            continue

        try:
            data = resp.json()
            text = extract_text(data)
            if not text:
                _quota_flag_set(False)
                continue
            try:
                return json.loads(text)
            except Exception:
                return _json_from_text(text)
        except Exception as exc:
            logging.warning("Gemini structured %s extraction error: %r", label, exc)
            _quota_flag_set(False)
            continue
    return None


def call_text(
    *,
    parts: List[Dict[str, Any]],
    api_key: str,
    endpoint: str,
    fallback_endpoint: str = "",
    temperature: float,
    max_output_tokens: int,
    timeout_secs: int,
    thinking_level: str = "",
    extract_text: JsonExtractor,
    retry_without_thinking: bool = True,
) -> Optional[str]:
    if is_high_demand_blocked():
        logging.warning("Gemini text skipped during high-demand cooldown (%ss remaining)", high_demand_retry_after_seconds())
        _quota_flag_set(False)
        return None

    generation_config: Dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
    }
    if thinking_level:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    body = {"contents": [{"parts": parts}], "generationConfig": generation_config}
    endpoints = [endpoint]
    if fallback_endpoint:
        endpoints.append(fallback_endpoint)
    _quota_flag_set(True)
    for idx, target_endpoint in enumerate(endpoints):
        label = "primary" if idx == 0 else "fallback"
        try:
            resp = requests.post(
                target_endpoint,
                params={"key": api_key},
                json=body,
                timeout=timeout_secs,
            )
        except Exception as exc:
            logging.warning("Gemini text %s request error: %r", label, exc)
            _quota_flag_set(False)
            continue
        if retry_without_thinking and resp.status_code == 400 and "thinkingConfig" in generation_config:
            retry_config = dict(generation_config)
            retry_config.pop("thinkingConfig", None)
            retry_body = dict(body)
            retry_body["generationConfig"] = retry_config
            try:
                resp = requests.post(
                    target_endpoint,
                    params={"key": api_key},
                    json=retry_body,
                    timeout=timeout_secs,
                )
                if resp.status_code == 200:
                    logging.info("Gemini text %s succeeded after removing thinkingConfig", label)
            except Exception as exc:
                logging.warning("Gemini text %s retry without thinkingConfig error: %r", label, exc)
                _quota_flag_set(False)
                continue
        if resp.status_code != 200:
            try:
                msg = resp.text[:400]
            except Exception:
                msg = str(resp.status_code)
            logging.warning("Gemini text %s HTTP %s: %s", label, resp.status_code, msg)
            if is_high_demand_response(resp):
                mark_high_demand(f"text {label}")
                _quota_flag_set(False)
                break
            if resp.status_code != 429:
                _quota_flag_set(False)
            continue
        try:
            payload = resp.json()
            text = extract_text(payload)
            if text:
                return text
        except Exception as exc:
            logging.warning("Gemini text %s extraction error: %r", label, exc)
            _quota_flag_set(False)
            continue
    return None


def iter_stream_text(resp: requests.Response, *, extract_text: JsonExtractor) -> Iterable[str]:
    buffer = ""
    brace_count = 0
    in_string = False
    escape = False
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = line.decode("utf-8")
        raw = chunk.strip()
        if raw.startswith("event:") or raw.startswith(":"):
            continue
        if raw.startswith("data:"):
            raw = raw[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            chunk = raw
        for char in chunk:
            buffer += char
            if char == '"' and not escape:
                in_string = not in_string
            if in_string:
                escape = (char == "\\") and not escape
            else:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0 and buffer.strip():
                        clean_buf = buffer.strip()
                        if clean_buf.startswith(","):
                            clean_buf = clean_buf[1:].strip()
                        if clean_buf.startswith("["):
                            clean_buf = clean_buf[1:].strip()
                        if clean_buf.endswith(","):
                            clean_buf = clean_buf[:-1].strip()
                        if clean_buf.endswith("]"):
                            clean_buf = clean_buf[:-1].strip()
                        try:
                            data = json.loads(clean_buf)
                            text = extract_text(data)
                            if text:
                                yield text
                        except Exception as exc:
                            logging.debug("Gemini stream text parse skipped chunk: %r", exc)
                        buffer = ""
