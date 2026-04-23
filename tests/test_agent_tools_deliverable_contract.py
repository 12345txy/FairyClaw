# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fairyclaw.capabilities.agent_tools.scripts.dc_contract import validate_done_when
from fairyclaw.capabilities.sub_agent_tools.scripts.dc_validator import evaluate_done_when


def test_validate_done_when_accepts_minimal_rule() -> None:
    result = validate_done_when(
        [
            {
                "type": "command_exit_code",
                "args": {"command": "python -c \"print('ok')\""},
            }
        ]
    )
    assert result.ok is True
    assert isinstance(result.done_when, list)
    assert result.done_when[0]["type"] == "command_exit_code"


def test_validate_done_when_rejects_unknown_type() -> None:
    result = validate_done_when([{"type": "unknown", "args": {}}])
    assert result.ok is False
    assert "must be one of" in str(result.error)


def test_command_exit_code_defaults_to_zero(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    target.write_text(json.dumps({"ok": True}), encoding="utf-8")

    async def run_check() -> dict:
        return await evaluate_done_when(
            session_id="sess_dc_test",
            done_when=[
                {"type": "file_exists", "args": {"path": str(target)}},
                {"type": "command_exit_code", "args": {"command": "python -c \"print('x')\""}},
            ],
        )

    result = asyncio.run(run_check())
    assert result["status"] == "pass"
    assert result["failed_rules"] == []
