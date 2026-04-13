# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Web gateway delivers sub-session outbound to parent-bound sockets."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from fairyclaw.core.gateway_protocol.models import GatewayOutboundMessage
from fairyclaw.gateway.adapters.web_gateway_adapter import WebGatewayAdapter


def test_sub_session_text_routes_to_parent_when_child_unbound(monkeypatch) -> None:
    async def scenario() -> None:
        adapter = WebGatewayAdapter()
        adapter.runtime = MagicMock()
        ws_parent = MagicMock()
        ws_parent.send_json = AsyncMock()
        child_id = "main_sess_sub_child99"
        parent_id = "sess_main"
        async with adapter._lock:
            adapter._session_sockets[parent_id].add(ws_parent)

        async def fake_parent(sid: str) -> str | None:
            assert sid == child_id
            return parent_id

        monkeypatch.setattr(adapter, "_parent_session_id_for_push_routing", fake_parent)

        await adapter.send(GatewayOutboundMessage.text(session_id=child_id, text="hello"))

        ws_parent.send_json.assert_awaited_once()
        env = ws_parent.send_json.await_args[0][0]
        assert env["op"] == "push"
        assert env["body"]["session_id"] == child_id
        assert env["body"]["kind"] == "text"
        assert env["body"]["meta"]["fc_parent_session_id"] == parent_id

    asyncio.run(scenario())


def test_sub_session_push_skips_parent_fallback_when_child_bound(monkeypatch) -> None:
    async def scenario() -> None:
        adapter = WebGatewayAdapter()
        adapter.runtime = MagicMock()
        child_id = "x_sub_y"
        ws_child = MagicMock()
        ws_child.send_json = AsyncMock()
        spy = AsyncMock(return_value="should_not_run")
        monkeypatch.setattr(adapter, "_parent_session_id_for_push_routing", spy)

        async with adapter._lock:
            adapter._session_sockets[child_id].add(ws_child)

        await adapter.send(GatewayOutboundMessage.text(session_id=child_id, text="hi"))

        ws_child.send_json.assert_awaited_once()
        env = ws_child.send_json.await_args[0][0]
        assert env["body"]["session_id"] == child_id
        assert "fc_parent_session_id" not in env["body"].get("meta", {})
        spy.assert_not_called()

    asyncio.run(scenario())
