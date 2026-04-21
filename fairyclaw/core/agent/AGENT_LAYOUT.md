# Agent Package Layout

`fairyclaw/core/agent` owns single-step orchestration, context construction, session-state policy, and capability routing.  
The package is split into composable sublayers to reduce coupling.

| Path | Responsibility | Notes |
| --- | --- | --- |
| `planning/` | Single-step turn orchestration, main/sub policy split, subtask coordination | `Planner` keeps shared orchestration; `turn_policy.py` handles main/sub differences |
| `context/` | History IR, system prompts, message assembly | No longer performs system-facing raw `dict -> IR` conversion |
| `session/` | Session role policy, session lock, memory IO | Coupled to persistence; avoids reverse dependency into planning |
| `routing/` | Capability-group selection and routing policy | `ToolRouter` depends on capability profiles only |
| `hooks/` | Hook protocol, runtime executor, stage scheduler | Turn hooks use typed payloads end-to-end |
| `executors/` | Context/tool execution pipelines | Composes hooks + planning, no global mutable state |
| `interfaces/` | Lightweight exports | e.g. `CompactionSnapshot`; canonical persistence remains `PersistentMemory` in `session/memory.py` |
| root (`constants.py`, `types.py`) | Cross-layer constants and light types | Root keeps shared contracts only; implementations live in subpackages |

## SDK Dependency Direction

`fairyclaw.sdk` sits **between** capability scripts and `fairyclaw.core`:

- `fairyclaw/capabilities/<group>/scripts/*.py` -> `fairyclaw.sdk.*`
- `fairyclaw.sdk.*` -> `fairyclaw.core.*`
- `fairyclaw.sdk` must not import `fairyclaw.capabilities`

`CapabilityRegistry` loads group config models from `<group>/config.py` (via `runtime_config_model`) and calls `fairyclaw.sdk.group_runtime.load_group_runtime_config` at startup. The frozen snapshot is stored on `CapabilityGroup.runtime_config` and injected into `ToolContext.group_runtime_config` by `fairyclaw.tools.runtime.ToolRuntime`.

## Dependency Direction

- `planning -> context/hooks/executors/session/routing`
- `executors -> hooks/interfaces`
- `context -> types/domain`
- `session -> infrastructure + domain`
- `routing -> capabilities + llm factory`
- `hooks -> capabilities registry + hook runtime`

Additional boundaries:

- `session/memory.py -> context/history_ir.py`
- `session/memory.py` exposes typed `ChatHistoryItem` IR directly
- `context/llm_message_assembler.py` only performs `IR -> LlmChatMessage`

Forbidden directions:

- `hooks` depending on `SessionEventBus`
- `context` directly depending on `main.py` or FastAPI layers
- `routing` depending on session runtime state
- `context` reintroducing system-facing raw-history parsing

## Context Layer

`context/` is structured into three roles:

- `history_ir.py`
  - Defines internal IR (`SessionMessageBlock`, `ToolCallRound`, `UserTurn`)
  - Primary history semantics consumed by hooks
- `llm_message_assembler.py`
  - Assembles IR into `LlmChatMessage`
  - `LlmChatMessage` is an LLM-boundary object, not business IR
- `turn_context_builder.py`
  - Separates prior history from current user turn
  - Extracts current user input explicitly as `user_turn`
  - Prevents the same user message from appearing in both `history_items` and `user_turn`

Removed:

- `history_mapper.py` (raw `dict -> IR` conversion moved into `session/memory.py`)

## Hook Contract

Core turn semantics in `hooks/protocol.py`:

- `LlmTurnContext.history_items`: authoritative typed history IR
- `LlmTurnContext.user_turn`: current planner-cycle user input IR
- `LlmTurnContext.llm_messages`: provider-facing messages derived from IR

Turn-hook stages:

- `tools_prepared`
- `before_llm_call`
- `after_llm_response`
- `before_tool_call`
- `after_tool_call`

Constraints:

- `HookStageInput.payload` / `HookStageOutput.patched_payload` must be strongly typed objects
- Within one stage, each hook receives the previous hook's patched payload directly
- `HookRuntime` no longer supports `dict.update(...)` payload merges

## Planning Layer

`planning/` avoids scattered `_is_sub_session(...)` branching by splitting responsibilities:

- `Planner`: shared orchestration (history, turn context, hooks, LLM call, tool execution)
- `turn_policy.py`: `MainSessionTurnPolicy` / `SubSessionTurnPolicy` for role-specific behavior
- `subtask_coordinator.py`: subtask terminal states, immediate failure notification, barrier aggregation

## Session / Memory Boundary

`PersistentMemory` provides planner persistence:

- `get_history(session_id) -> list[ChatHistoryItem]`
- `add_session_event(session_id, message: SessionMessageBlock)`
- `add_operation_event(session_id, tool_round: ToolCallRound)`

Notes:

- `query_memory` is removed
- `PersistentMemory` maps DB rows into IR
- planner/context no longer consume raw history dicts
- User-facing outbound (`assistant` text/file and `tool_call`/`tool_result`) is emitted by `fairyclaw.bridge.user_gateway.UserGateway`

## Runtime Boundary

- Event consumption and session scheduling are owned by `fairyclaw/core/events/`
- Planner handles one turn per wakeup
- Hook execution is owned by `fairyclaw/core/agent/hooks/` (`HookStageRunner` for stage orchestration)
- Runtime event plugin dispatch and turn hook pipeline remain separate boundaries:
  - runtime events for `event:*`
  - turn hooks for the five turn stages
