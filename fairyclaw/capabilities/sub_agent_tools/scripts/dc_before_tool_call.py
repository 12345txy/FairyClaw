from __future__ import annotations

from dataclasses import replace

from fairyclaw.sdk.hooks import (
    BeforeToolCallHookPayload,
    HookStageInput,
    HookStageOutput,
    HookStatus,
)
from fairyclaw.sdk.runtime import publish_runtime_event
from fairyclaw.core.events.bus import EventType

from .dc_meta import (
    load_done_when_and_state,
    make_report_done_failed_arguments,
    save_dc_state,
    to_failed_summary,
)
from .dc_validator import evaluate_done_when

_THRESHOLD = 3


async def execute_hook(
    hook_input: HookStageInput[BeforeToolCallHookPayload],
) -> HookStageOutput[BeforeToolCallHookPayload]:
    payload = hook_input.payload
    if not hook_input.context.is_sub_session:
        return HookStageOutput(status=HookStatus.SKIP, patched_payload=payload)
    if payload.request.name != "report_subtask_done":
        return HookStageOutput(status=HookStatus.SKIP, patched_payload=payload)

    done_when, dc_state = await load_done_when_and_state(payload.session_id)
    if not done_when:
        return HookStageOutput(status=HookStatus.SKIP, patched_payload=payload)

    result = await evaluate_done_when(session_id=payload.session_id, done_when=done_when)
    if result.get("status") == "pass":
        dc_state["last_status"] = "pass"
        dc_state["last_failed_rules"] = []
        dc_state["last_checked_at_ms"] = int(result.get("checked_at_ms", 0))
        await save_dc_state(payload.session_id, dc_state)
        return HookStageOutput(status=HookStatus.SKIP, patched_payload=payload)

    dc_state["false_finish_count"] = int(dc_state.get("false_finish_count", 0)) + 1
    dc_state["last_status"] = "fail"
    dc_state["last_failed_rules"] = list(result.get("failed_rules", []))
    dc_state["last_checked_at_ms"] = int(result.get("checked_at_ms", 0))
    await save_dc_state(payload.session_id, dc_state)

    summary = to_failed_summary(dc_state["last_failed_rules"])
    if int(dc_state["false_finish_count"]) >= _THRESHOLD:
        forced_request = replace(
            payload.request,
            arguments_json=make_report_done_failed_arguments(summary),
        )
        return HookStageOutput(
            status=HookStatus.OK,
            patched_payload=replace(payload, request=forced_request),
        )

    await publish_runtime_event(
        EventType.USER_MESSAGE_RECEIVED,
        payload.session_id,
        payload={
            "trigger_turn": True,
            "task_type": hook_input.context.task_type or "general",
            "enabled_groups": list(payload.enabled_groups or []),
            "internal_user_text": summary,
        },
        source="sub_agent_tools_deliverable_contract",
    )
    patched = replace(
        payload,
        force_finish=True,
        force_finish_reason="deliverable_contract_not_satisfied",
    )
    return HookStageOutput(status=HookStatus.OK, patched_payload=patched)
