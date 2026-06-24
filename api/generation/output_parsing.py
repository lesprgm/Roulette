from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def extract_gemini_text(payload: Dict[str, Any]) -> Optional[str]:
    try:
        candidates = payload.get("candidates") or []
        best_text = ""
        best_structured = ""
        for cand in candidates:
            content = cand.get("content") or {}
            parts = content.get("parts") or []
            text_parts: list[str] = []
            for part in parts:
                txt = part.get("text")
                if isinstance(txt, str):
                    text_parts.append(txt)
            if text_parts:
                joined = "".join(text_parts)
                if joined.strip() and len(joined) > len(best_text):
                    best_text = joined
            for part in parts:
                function_call = part.get("functionCall")
                if isinstance(function_call, dict):
                    args = function_call.get("arguments")
                    if isinstance(args, str) and args.strip():
                        if len(args) > len(best_structured):
                            best_structured = args
                        continue
                    try:
                        encoded = json.dumps(function_call, ensure_ascii=False)
                        if len(encoded) > len(best_structured):
                            best_structured = encoded
                    except Exception:
                        pass
                data_blob = part.get("data") or part.get("json") or part.get("structValue")
                if data_blob:
                    try:
                        encoded = json.dumps(data_blob, ensure_ascii=False)
                        if len(encoded) > len(best_structured):
                            best_structured = encoded
                    except Exception:
                        pass
        if best_text:
            return best_text
        if best_structured:
            return best_structured
    except Exception:
        pass
    return None


def extract_final_html_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    if not isinstance(text, str) or not text.strip():
        return blocks
    pattern = re.compile(r"````html\s*(.*?)````|```html\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(text):
        html = (match.group(1) or match.group(2) or "").strip()
        if html:
            blocks.append(html)
    if blocks:
        return blocks
    lowered = text.lower()
    start = lowered.find("<!doctype html")
    if start < 0:
        start = lowered.find("<html")
    if start >= 0:
        blocks.append(text[start:].strip())
    return blocks


def premium_burst_site_pattern() -> re.Pattern[str]:
    return re.compile(
        r"===NDW_SITE_(\d+)_START===(.*?)===NDW_SITE_\1_END===",
        re.IGNORECASE | re.DOTALL,
    )


def extract_completed_premium_burst_sites(text: str) -> List[Tuple[int, str]]:
    sites: List[Tuple[int, str]] = []
    seen: Set[int] = set()
    for match in premium_burst_site_pattern().finditer(text or ""):
        try:
            index = int(match.group(1))
        except Exception:
            continue
        if index in seen:
            continue
        blocks = extract_final_html_blocks(match.group(2) or "")
        if not blocks:
            continue
        seen.add(index)
        sites.append((index, blocks[-1]))
    return sorted(sites, key=lambda item: item[0])
