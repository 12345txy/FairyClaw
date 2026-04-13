# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
import asyncio
from unittest.mock import MagicMock

from fairyclaw.bridge.user_gateway import UserGateway


def test_user_gateway_sub_session_file_outbound_uses_child_session_id(monkeypatch) -> None:
    async def scenario() -> None:
        bus = MagicMock()
        gateway = UserGateway(bus=bus)
        published: list[tuple[str, dict[str, str]]] = []

        async def fake_push_outbound(message) -> None:
            published.append((message.session_id, dict(message.content)))

        class FakeSessionLocal:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

        class FakeRouteRepo:
            def __init__(self, db) -> None:
                self.db = db

            async def get_parent_session_id(self, session_id: str) -> str | None:
                assert session_id == "main_sess_sub_abc123"
                return "sess_main"

        monkeypatch.setattr("fairyclaw.bridge.user_gateway.AsyncSessionLocal", FakeSessionLocal)
        monkeypatch.setattr("fairyclaw.bridge.user_gateway.GatewaySessionRouteRepository", FakeRouteRepo)
        gateway.push_outbound = fake_push_outbound  # type: ignore[method-assign]

        # Sub-session ids contain SUB_SESSION_MARKER ``_sub_`` (see session_role).
        await gateway.emit_file("main_sess_sub_abc123", "file_sub")

        assert published == [("main_sess_sub_abc123", {"file_id": "file_sub"})]

    asyncio.run(scenario())
