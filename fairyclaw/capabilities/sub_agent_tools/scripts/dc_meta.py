from __future__ import annotations

import json
from typing import Any

from fairyclaw.infrastructure.database.models import SessionModel
from fairyclaw.infrastructure.database.session import AsyncSessionLocal

ALLOWED_RULE_TYPES = {
    "file_exists",
    "json_parseable",
    "json_schema",
    "command_exit_code",
    "text_contains",
    "text_not_contains",
}


def validate_done_when(done_when: Any) -> tuple[bool, str | None, list[dict[str, Any]]]:
    if done_when is None:
        return True, None, []
    if not isinstance(done_when, list):
        return False, "done_when must be an array.", []
    normalized: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(done_when):
        if not isinstance(raw_rule, dict):
            return False, f"done_when[{index}] must be an object.", []
        if set(raw_rule.keys()) != {"type", "args"}:
            return False, f"done_when[{index}] must contain exactly 'type' and 'args'.", []
        rule_type = raw_rule.get("type")
        args = raw_rule.get("args")
        if not isinstance(rule_type, str) or rule_type not in ALLOWED_RULE_TYPES:
            return False, f"done_when[{index}].type unsupported.", []
        if not isinstance(args, dict):
            return False, f"done_when[{index}].args must be an object.", []
        normalized.append({"type": rule_type, "args": dict(args)})
    return True, None, normalized


async def load_done_when_and_state(session_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    done_when: list[dict[str, Any]] = []
    dc_state = {
        "false_finish_count": 0,
        "last_status": "unknown",
        "last_failed_rules": [],
        "last_checked_at_ms": 0,
    }
    async with AsyncSessionLocal() as db:
        model = await db.get(SessionModel, session_id)
        if model is None or not isinstance(model.meta, dict):
            return done_when, dc_state
        meta = dict(model.meta)
        ok, _err, normalized = validate_done_when(meta.get("done_when"))
        if ok:
            done_when = normalized
        state_raw = meta.get("dc_state")
        if isinstance(state_raw, dict):
            dc_state["false_finish_count"] = int(state_raw.get("false_finish_count", 0))
            dc_state["last_status"] = str(state_raw.get("last_status", "unknown"))
            lfr = state_raw.get("last_failed_rules")
            dc_state["last_failed_rules"] = list(lfr) if isinstance(lfr, list) else []
            dc_state["last_checked_at_ms"] = int(state_raw.get("last_checked_at_ms", 0))
    return done_when, dc_state


async def save_dc_state(session_id: str, dc_state: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        model = await db.get(SessionModel, session_id)
        if model is None:
            return
        meta = dict(model.meta) if isinstance(model.meta, dict) else {}
        meta["dc_state"] = {
            "false_finish_count": int(dc_state.get("false_finish_count", 0)),
            "last_status": str(dc_state.get("last_status", "unknown")),
            "last_failed_rules": list(dc_state.get("last_failed_rules", [])),
            "last_checked_at_ms": int(dc_state.get("last_checked_at_ms", 0)),
        }
        model.meta = meta
        await db.commit()


def to_failed_summary(failed_rules: list[dict[str, Any]]) -> str:
    if not failed_rules:
        return (
            "The task is not complete yet. "
            "Please verify the required deliverables and try again."
        )
    lines = [
        "The task is not complete yet.",
        "Before finishing, please address the following issues:",
    ]
    for item in failed_rules[:8]:
        if not isinstance(item, dict):
            continue
        rule_type = str(item.get("type") or "").strip()
        detail = str(item.get("detail") or "").strip()
        lines.append(f"- {_humanize_rule_failure(rule_type, detail)}")
    return "\n".join(lines)


def make_report_done_failed_arguments(summary: str) -> str:
    return json.dumps({"status": "failed", "summary": summary[:4000]}, ensure_ascii=False)


def _humanize_rule_failure(rule_type: str, detail: str) -> str:
    if rule_type == "file_exists":
        return f"A required file is missing. {detail}".strip()
    if rule_type == "json_parseable":
        return f"A required JSON file is invalid or unreadable. {detail}".strip()
    if rule_type == "json_schema":
        return f"A JSON output does not match the expected structure. {detail}".strip()
    if rule_type == "command_exit_code":
        return f"A required command did not succeed. {detail}".strip()
    if rule_type == "text_contains":
        return f"A required output is missing expected content. {detail}".strip()
    if rule_type == "text_not_contains":
        return f"An output contains forbidden content. {detail}".strip()
    if detail:
        return detail
    return "A required validation check failed."
