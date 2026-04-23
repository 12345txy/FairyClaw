# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Tests for ClawBench idle-wait helper."""

from __future__ import annotations

import time

from fairyclaw.bench_clawbench import (
    events_fingerprint,
    last_assistant_reply_from_history_events,
    run_clawbench_benchmark,
)


def test_last_assistant_reply_from_history_events() -> None:
    ev = [
        {"kind": "session_event", "role": "user", "text": "hi", "ts_ms": 1},
        {"kind": "session_event", "role": "assistant", "text": "a1", "ts_ms": 2},
        {"kind": "session_event", "role": "assistant", "text": "a2", "ts_ms": 3},
    ]
    assert last_assistant_reply_from_history_events(ev) == "a2"
    assert last_assistant_reply_from_history_events(None) is None
    tool_only = [
        {"kind": "session_event", "role": "user", "text": "hi", "ts_ms": 1},
        {"kind": "operation_event", "tool_name": "t", "result_preview": "tool_out", "ts_ms": 2},
    ]
    assert last_assistant_reply_from_history_events(tool_only) == "tool_out"
    assert (
        last_assistant_reply_from_history_events(
            [{"kind": "session_event", "role": "system", "text": "notice", "ts_ms": 1}]
        )
        == "notice"
    )


def test_events_fingerprint_stable() -> None:
    ev = [{"kind": "session_event", "role": "user", "text": "hi", "ts_ms": 1}]
    assert events_fingerprint(ev) == events_fingerprint(ev)


def test_run_clawbench_benchmark_idle_success() -> None:
    calls: list[str] = []
    events_state = [
        [{"kind": "session_event", "role": "user", "text": "x", "ts_ms": 1}],
        [
            {"kind": "session_event", "role": "user", "text": "x", "ts_ms": 1},
            {"kind": "session_event", "role": "assistant", "text": "y", "ts_ms": 2},
        ],
    ]
    idx = [0]

    def ws(op: str, body: dict) -> dict:
        calls.append(op)
        if op != "sessions.history":
            raise AssertionError(op)
        i = min(idx[0], len(events_state) - 1)
        idx[0] += 1
        return {"events": events_state[i]}

    t0 = time.perf_counter()
    out = run_clawbench_benchmark(
        ws_request=ws,
        session_id="sess_1",
        timeout_sec=30.0,
        idle_sec=0.15,
        poll_interval_sec=0.05,
        min_wait_after_send_sec=0.05,
    )
    assert out["ok"] is True
    assert out["reason"] == "idle"
    assert out["session_id"] == "sess_1"
    assert out["event_count"] == 2
    assert time.perf_counter() - t0 < 5.0


def test_run_clawbench_benchmark_timeout() -> None:
    def ws(_op: str, _body: dict) -> dict:
        return {"events": [{"kind": "session_event", "ts_ms": 1}]}

    out = run_clawbench_benchmark(
        ws_request=ws,
        session_id="sess_x",
        timeout_sec=0.2,
        idle_sec=5.0,
        poll_interval_sec=0.05,
        min_wait_after_send_sec=0.0,
    )
    assert out["ok"] is False
    assert out["reason"] == "timeout"
