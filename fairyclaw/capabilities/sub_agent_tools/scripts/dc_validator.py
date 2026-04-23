from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from fairyclaw.core.runtime.session_runtime_store import get_session_runtime_store


async def evaluate_done_when(*, session_id: str, done_when: list[dict[str, Any]]) -> dict[str, Any]:
    workspace_root = await _resolve_workspace_root(session_id)
    failed_rules: list[dict[str, Any]] = []
    for idx, rule in enumerate(done_when):
        rule_type = str(rule.get("type") or "")
        args = rule.get("args", {})
        ok, detail = await _eval_rule(
            workspace_root=workspace_root,
            rule_type=rule_type,
            args=args if isinstance(args, dict) else {},
        )
        if not ok:
            failed_rules.append({"index": idx, "type": rule_type, "detail": detail})
    return {
        "status": "pass" if not failed_rules else "fail",
        "failed_rules": failed_rules,
        "checked_at_ms": int(time.time() * 1000),
    }


async def _resolve_workspace_root(session_id: str) -> str:
    try:
        runtime = await get_session_runtime_store().get(session_id)
        if runtime.workspace_root:
            return str(runtime.workspace_root).strip()
    except Exception:
        pass
    return os.getcwd()


def _resolve_path(workspace_root: str, path_value: Any) -> Path:
    raw = str(path_value or "").strip()
    if not raw:
        return Path(workspace_root)
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (Path(workspace_root) / p).resolve()


async def _eval_rule(*, workspace_root: str, rule_type: str, args: dict[str, Any]) -> tuple[bool, str]:
    if rule_type == "file_exists":
        target = _resolve_path(workspace_root, args.get("path"))
        return target.exists(), f"{target} does not exist."
    if rule_type == "json_parseable":
        target = _resolve_path(workspace_root, args.get("path"))
        if not target.is_file():
            return False, f"{target} is not a readable file."
        try:
            json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"{target} is not valid JSON: {exc}"
        return True, "ok"
    if rule_type == "json_schema":
        target = _resolve_path(workspace_root, args.get("path"))
        if not target.is_file():
            return False, f"{target} is not a readable file."
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"{target} is not valid JSON: {exc}"
        schema_obj = args.get("schema")
        if not isinstance(schema_obj, dict):
            schema_path = _resolve_path(workspace_root, args.get("schema_path"))
            if not schema_path.is_file():
                return False, f"schema_path {schema_path} does not exist."
            try:
                schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
            except Exception as exc:
                return False, f"schema_path {schema_path} invalid JSON: {exc}"
        valid, reason = _validate_schema_minimal(payload=payload, schema=schema_obj)
        return valid, reason
    if rule_type == "command_exit_code":
        command = str(args.get("command") or "").strip()
        wanted = int(args.get("exit_code", 0))
        rc = await _run_command_exit_code(command=command, cwd=workspace_root)
        return rc == wanted, f"command exit_code={rc}, expected={wanted}"
    if rule_type in {"text_contains", "text_not_contains"}:
        target = _resolve_path(workspace_root, args.get("path"))
        if not target.is_file():
            return False, f"{target} is not a readable file."
        content = target.read_text(encoding="utf-8", errors="replace")
        terms = [str(t) for t in args.get("terms", [])]
        if rule_type == "text_contains":
            missed = [t for t in terms if t not in content]
            return (not missed), (f"missing terms: {missed}" if missed else "ok")
        present = [t for t in terms if t in content]
        return (not present), (f"forbidden terms present: {present}" if present else "ok")
    return False, f"unsupported rule type: {rule_type}"


async def _run_command_exit_code(*, command: str, cwd: str) -> int:
    if not command:
        return 127
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await proc.wait()


def _validate_schema_minimal(*, payload: Any, schema: dict[str, Any]) -> tuple[bool, str]:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(payload, dict):
            return False, "payload is not object"
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in payload:
                    return False, f"missing required key: {key}"
        return True, "ok"
    if schema_type == "array":
        return isinstance(payload, list), "payload is not array"
    if schema_type == "string":
        return isinstance(payload, str), "payload is not string"
    if schema_type == "number":
        return isinstance(payload, (int, float)), "payload is not number"
    if schema_type == "boolean":
        return isinstance(payload, bool), "payload is not boolean"
    return True, "ok"
