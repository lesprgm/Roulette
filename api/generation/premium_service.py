import logging
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import BackgroundTasks

from api import prefetch
from api.preflight import annotate_doc, has_blocking_issues, preflight_doc
from api.settings import SETTINGS

try:
    from api.llm_client import (
        generate_page_premium as llm_generate_page_premium,
        generate_page_premium_burst as llm_generate_page_premium_burst,
        premium_available as llm_premium_available,
        probe as llm_probe,
        status as llm_status,
    )
except Exception:
    llm_generate_page_premium = None
    llm_generate_page_premium_burst = None

    def llm_status() -> Dict[str, Any]:
        return {"provider": None, "model": None, "has_token": False, "using": "stub"}

    def llm_probe() -> Dict[str, Any]:
        return {"ok": False, "error": "Model or token not configured", "using": "stub"}

    def llm_premium_available() -> bool:
        return False


PrefetchHandle = str
PREMIUM_QUEUE_ENABLED = SETTINGS.queue.premium_enabled
PREMIUM_FILL_TO = SETTINGS.queue.premium_fill_to
PREMIUM_LOW_WATER = min(SETTINGS.queue.premium_low_water, PREMIUM_FILL_TO)
PREMIUM_BATCH_SIZE = SETTINGS.queue.premium_batch_size
PREMIUM_TOPUP_ENABLED = SETTINGS.queue.premium_topup_enabled
STREAM_KEEPALIVE_SECONDS = SETTINGS.runtime.stream_keepalive_seconds

log = logging.getLogger(__name__)
_topup_lock = threading.Lock()


def premium_queue_enabled() -> bool:
    return PREMIUM_QUEUE_ENABLED


def premium_ready() -> bool:
    return bool(llm_generate_page_premium is not None and llm_premium_available())


def summarize_preflight_issues(issues: List[Dict[str, Any]], limit: int = 4) -> str:
    parts = []
    for issue in list(issues or [])[:limit]:
        severity = str(issue.get("severity") or "issue")
        field = str(issue.get("field") or "unknown")
        message = str(issue.get("message") or "").strip()
        parts.append(f"{severity}:{field}:{message}")
    extra = len(issues or []) - len(parts)
    if extra > 0:
        parts.append(f"+{extra} more")
    return " | ".join(parts) if parts else "none"


def apply_local_acceptance_batch(docs: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
    approved = []
    for index, doc in enumerate(docs):
        if not isinstance(doc, dict):
            continue
        issues = preflight_doc(doc)
        if has_blocking_issues(issues):
            log.info(
                "%s: local preflight rejected index=%d issues=%s",
                context,
                index,
                summarize_preflight_issues(issues),
            )
            continue
        if issues:
            doc = annotate_doc(doc, issues)
        doc["review"] = {"ok": True, "notes": "local preflight accepted"}
        approved.append(doc)
    return approved


def enqueue_premium_docs(
    docs: List[Dict[str, Any]], *, context: str, max_queue: Optional[int] = None
) -> List[PrefetchHandle]:
    del context
    if not docs or not premium_queue_enabled():
        return []
    stored = []
    for doc in docs:
        if max_queue is not None and prefetch.size("premium") >= max_queue:
            break
        handle = prefetch.enqueue(doc, lane="premium")
        if handle:
            stored.append(handle)
    return stored


def _premium_seed(base_seed: int, offset: int) -> int:
    seed = (int(base_seed or 0) + ((offset + 1) * 7919)) % 1_000_000_007
    return seed or (offset + 1)


def generate_premium_batch_candidates(
    brief: str,
    *,
    batch_size: int,
    seed: int,
    user_key: str,
    context: str,
) -> List[Dict[str, Any]]:
    if llm_generate_page_premium_burst:
        docs = []
        try:
            for doc in llm_generate_page_premium_burst(
                brief or "", seed=seed, count=max(1, int(batch_size or 1)), user_key=user_key
            ):
                if isinstance(doc, dict) and not doc.get("error"):
                    docs.append(doc)
        except Exception:
            log.exception("%s: premium burst interrupted after %d accepted candidates", context, len(docs))
        if docs:
            return apply_local_acceptance_batch(docs, context)
    if not llm_generate_page_premium:
        return []

    docs = []
    for index in range(max(1, int(batch_size or 1))):
        doc = llm_generate_page_premium(brief or "", seed=_premium_seed(seed, index), user_key=user_key)
        if isinstance(doc, dict) and doc.get("error") == "model_temporarily_unavailable":
            break
        if isinstance(doc, dict) and not doc.get("error"):
            docs.append(doc)
    return apply_local_acceptance_batch(docs, context) if docs else []


def next_acceptable_premium_doc(
    iterator: Iterable[Dict[str, Any]], context: str
) -> Optional[Dict[str, Any]]:
    for doc in iterator:
        if isinstance(doc, dict) and doc.get("error") == "model_temporarily_unavailable":
            return None
        if not isinstance(doc, dict) or doc.get("error"):
            continue
        approved = apply_local_acceptance_batch([doc], context)
        if approved:
            return approved[0]
    return None


def drain_premium_burst_to_queue(
    iterator: Iterable[Dict[str, Any]],
    *,
    context: str,
    max_queue: int = PREMIUM_FILL_TO,
    brief: str = "",
) -> None:
    del brief
    try:
        for doc in iterator:
            if not isinstance(doc, dict) or doc.get("error"):
                continue
            approved = apply_local_acceptance_batch([doc], context)
            if not approved:
                continue
            enqueue_premium_docs(approved, context=context, max_queue=max_queue)
            if premium_queue_enabled() and prefetch.size("premium") >= max_queue:
                break
    except Exception:
        log.exception("%s: failed draining premium burst leftovers", context)


def start_premium_burst(
    brief: str, *, seed: int, user_key: str, context: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Iterable[Dict[str, Any]]]]:
    if llm_generate_page_premium_burst:
        iterator = iter(
            llm_generate_page_premium_burst(
                brief or "", seed=seed, count=PREMIUM_BATCH_SIZE, user_key=user_key
            )
        )
        first = next_acceptable_premium_doc(iterator, context)
        if first:
            return first, iterator
    return generate_single_premium_doc(brief, seed=seed, user_key=user_key, context=context), None


def generate_single_premium_doc(
    brief: str, *, seed: int, user_key: str, context: str
) -> Optional[Dict[str, Any]]:
    if not llm_generate_page_premium:
        return None
    doc = llm_generate_page_premium(brief or "", seed=seed, user_key=user_key)
    if not isinstance(doc, dict) or doc.get("error"):
        return None
    issues = preflight_doc(doc)
    if has_blocking_issues(issues):
        log.info("%s: live preflight rejected output issues=%s", context, summarize_preflight_issues(issues))
        return None
    return annotate_doc(doc, issues) if issues else doc


def premium_queue_target_size(current: int) -> int:
    return max(PREMIUM_FILL_TO, current)


def schedule_premium_topup(
    background_tasks: Optional[BackgroundTasks], brief: str, target: int, *, context: str
) -> None:
    if not background_tasks:
        return
    try:
        log.info(
            "%s: scheduling premium top-up queue_size=%d target=%d",
            context,
            prefetch.size("premium"),
            target,
        )
        background_tasks.add_task(top_up_premium_queue, brief or "", target)
    except Exception:
        log.exception("%s: failed to schedule premium top-up", context)


def top_up_premium_queue(brief: str = "", min_fill: int = PREMIUM_FILL_TO) -> None:
    if not premium_queue_enabled() or not PREMIUM_TOPUP_ENABLED or not premium_ready():
        return
    if not _topup_lock.acquire(blocking=False):
        return
    try:
        current = prefetch.size("premium")
        target = max(int(min_fill or PREMIUM_FILL_TO), premium_queue_target_size(current))
        attempts = 0
        while prefetch.size("premium") < target and attempts < max(1, target * 2):
            attempts += 1
            seed = (int(time.time() * 1000) + attempts) % 1_000_000_007
            approved = generate_premium_batch_candidates(
                brief,
                batch_size=PREMIUM_BATCH_SIZE,
                seed=seed,
                user_key="premium-prefetch",
                context="premium.top_up",
            )
            if approved:
                enqueue_premium_docs(approved, context="premium.top_up", max_queue=target)
    except Exception:
        log.exception("premium.top_up: unexpected error")
    finally:
        _topup_lock.release()


def stream_premium_first_page(
    brief: str,
    *,
    seed: int,
    user_key: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    first, leftovers = start_premium_burst(
        brief, seed=seed, user_key=user_key, context="premium.stream.first"
    )
    if not first:
        return {"error": "Premium generation failed"}
    if leftovers and background_tasks:
        background_tasks.add_task(
            drain_premium_burst_to_queue,
            leftovers,
            context="premium.stream.leftovers",
            max_queue=PREMIUM_FILL_TO,
            brief=brief or "",
        )
    if background_tasks and premium_queue_enabled() and prefetch.size("premium") < PREMIUM_FILL_TO:
        schedule_premium_topup(
            background_tasks, brief or "", PREMIUM_FILL_TO, context="premium.stream.first"
        )
    return first
