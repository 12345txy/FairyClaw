# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""ClawBench v2 integration: wait until a session's history stops changing.

Used by ``fairyclaw bench run`` and intended to be invoked from ClawBench adapters
after ``fairyclaw start`` is running.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any


def last_assistant_reply_from_history_events(events: list[Any] | None) -> str | None:
    """Last model-visible line from history rows (chronological order).

    Prefer the last non-user ``session_event`` with non-empty ``text`` (``assistant`` or
    ``system``). If none, use the last non-empty ``operation_event.result_preview`` so
    tool-only turns still surface something in the CLI.
    """
    if not isinstance(events, list):
        return None
    last_msg: str | None = None
    last_tool: str | None = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind")
        if kind == "session_event":
            role = str(ev.get("role") or "").strip().lower()
            if role == "user":
                continue
            if role not in ("assistant", "system"):
                continue
            t = (ev.get("text") or "").strip()
            if t:
                last_msg = t
        elif kind == "operation_event":
            rp = ev.get("result_preview")
            if isinstance(rp, str) and rp.strip():
                last_tool = rp.strip()
    return last_msg or last_tool


def events_fingerprint(events: list[Any]) -> str:
    """Stable string for comparing history snapshots (tail to avoid huge payloads)."""
    if not events:
        return "0"
    tail = events[-16:] if len(events) > 16 else events
    return json.dumps(tail, sort_keys=True, ensure_ascii=False)


def run_clawbench_benchmark(
    *,
    ws_request: Callable[[str, dict[str, Any]], dict[str, Any]],
    session_id: str,
    timeout_sec: float,
    idle_sec: float = 3.0,
    poll_interval_sec: float = 0.5,
    min_wait_after_send_sec: float = 2.0,
) -> dict[str, Any]:
    """Poll ``sessions.history`` until the fingerprint is unchanged for ``idle_sec`` or ``timeout_sec``.

    Args:
        ws_request: Callable implementing gateway ops (e.g. ``sessions.history``).
        session_id: Target session id.
        timeout_sec: Wall-clock budget from call start.
        idle_sec: Require this many seconds with no history change before success.
        poll_interval_sec: Sleep between polls.
        min_wait_after_send_sec: Do not allow idle-success before this elapsed time (lets planner start).

    Returns:
        Dict with at least ``ok`` (bool), ``session_id``, ``reason`` (``idle`` | ``timeout`` | ``error``),
        and timing / counts.
    """
    t0 = time.perf_counter()
    deadline = t0 + timeout_sec
    min_wait_until = t0 + min_wait_after_send_sec

    last_fp: str | None = None
    stable_since: float | None = None

    while True:
        now = time.perf_counter()
        if now >= deadline:
            return {
                "ok": False,
                "session_id": session_id,
                "reason": "timeout",
                "elapsed_sec": round(now - t0, 3),
                "event_count": None,
            }

        try:
            body = ws_request("sessions.history", {"session_id": session_id, "limit": 500})
        except Exception as exc:
            return {
                "ok": False,
                "session_id": session_id,
                "reason": "error",
                "error": str(exc),
                "elapsed_sec": round(now - t0, 3),
                "event_count": None,
            }

        events = body.get("events") if isinstance(body.get("events"), list) else []
        fp = events_fingerprint(events)

        if fp != last_fp:
            last_fp = fp
            stable_since = now
            time.sleep(poll_interval_sec)
            continue

        # Unchanged since last poll
        if stable_since is None:
            stable_since = now
        if now < min_wait_until:
            time.sleep(poll_interval_sec)
            continue
        if (now - stable_since) >= idle_sec:
            return {
                "ok": True,
                "session_id": session_id,
                "reason": "idle",
                "elapsed_sec": round(now - t0, 3),
                "event_count": len(events),
            }

        time.sleep(poll_interval_sec)


async def run_clawbench_benchmark_async(
    *,
    op_request: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    session_id: str,
    timeout_sec: float,
    idle_sec: float = 3.0,
    poll_interval_sec: float = 0.5,
    min_wait_after_send_sec: float = 2.0,
) -> dict[str, Any]:
    """Async variant: poll ``sessions.history`` via an async handler (in-process ``BusinessGatewayControl``).

    Idle is only declared once the history contains a non-user response (assistant/tool) **and** the
    fingerprint has been stable for ``idle_sec``.  Without this guard the bench would falsely
    terminate while the planner's LLM call is still in-flight (the fingerprint never changes because
    only the user event has been written yet).
    """
    t0 = time.perf_counter()
    deadline = t0 + timeout_sec
    min_wait_until = t0 + min_wait_after_send_sec

    last_fp: str | None = None
    stable_since: float | None = None

    while True:
        now = time.perf_counter()
        if now >= deadline:
            return {
                "ok": False,
                "session_id": session_id,
                "reason": "timeout",
                "elapsed_sec": round(now - t0, 3),
                "event_count": None,
            }

        try:
            body = await op_request("sessions.history", {"session_id": session_id, "limit": 500})
        except Exception as exc:
            return {
                "ok": False,
                "session_id": session_id,
                "reason": "error",
                "error": str(exc),
                "elapsed_sec": round(now - t0, 3),
                "event_count": None,
            }

        events = body.get("events") if isinstance(body.get("events"), list) else []
        fp = events_fingerprint(events)

        if fp != last_fp:
            last_fp = fp
            stable_since = now
            await asyncio.sleep(poll_interval_sec)
            continue

        if stable_since is None:
            stable_since = now
        if now < min_wait_until:
            await asyncio.sleep(poll_interval_sec)
            continue

        # Require at least one non-user event before allowing idle.
        # Without this, the bench would declare idle before the planner has even started
        # calling the LLM (user event written instantly; history fingerprint never changes).
        has_model_response = any(
            isinstance(ev, dict)
            and (
                (ev.get("kind") == "session_event" and str(ev.get("role") or "").lower() != "user")
                or ev.get("kind") == "operation_event"
            )
            for ev in events
        )
        if not has_model_response:
            await asyncio.sleep(poll_interval_sec)
            continue

        if (now - stable_since) >= idle_sec:
            return {
                "ok": True,
                "session_id": session_id,
                "reason": "idle",
                "elapsed_sec": round(now - t0, 3),
                "event_count": len(events),
                "_events_for_reply": list(events),
            }

        await asyncio.sleep(poll_interval_sec)
