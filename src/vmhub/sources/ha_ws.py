"""Home Assistant WebSocket source.

Streams vacuum entity states out of HA. Each yielded payload is the HA state object
enriched with a top-level ``platform`` key resolved from the entity registry — that is
what adapters match on, since ``state_changed`` events carry no integration identity.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from itertools import count
from typing import Any

import websockets

log = logging.getLogger(__name__)


class HomeAssistantWSError(Exception):
    pass


class HomeAssistantWS:
    def __init__(self, url: str, token: str, domain: str = "vacuum") -> None:
        self.url = url
        self.token = token
        self.domain = domain
        self._ids = count(1)
        self._ws: Any = None
        self._platforms: dict[str, str] = {}

    async def _send(self, message: dict[str, Any]) -> dict[str, Any]:
        message_id = next(self._ids)
        await self._ws.send(json.dumps({"id": message_id, **message}))
        while True:
            reply: dict[str, Any] = json.loads(await self._ws.recv())
            if reply.get("id") == message_id:
                if not reply.get("success", True):
                    raise HomeAssistantWSError(f"{message['type']} failed: {reply.get('error')}")
                return reply

    async def _authenticate(self) -> None:
        greeting = json.loads(await self._ws.recv())
        if greeting.get("type") != "auth_required":
            raise HomeAssistantWSError(f"unexpected greeting: {greeting.get('type')}")
        await self._ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        result = json.loads(await self._ws.recv())
        if result.get("type") != "auth_ok":
            raise HomeAssistantWSError(f"authentication rejected: {result.get('message')}")

    async def _load_entity_registry(self) -> None:
        reply = await self._send({"type": "config/entity_registry/list"})
        self._platforms = {e["entity_id"]: e["platform"] for e in reply["result"]}

    def _enrich(self, state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "platform": self._platforms.get(state["entity_id"])}

    def _is_target(self, entity_id: str) -> bool:
        return entity_id.startswith(f"{self.domain}.")

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        """Yield an initial snapshot of every vacuum entity, then every state change."""
        async with websockets.connect(self.url, max_size=None) as ws:
            self._ws = ws
            await self._authenticate()
            await self._load_entity_registry()

            snapshot = await self._send({"type": "get_states"})
            for state in snapshot["result"]:
                if self._is_target(state["entity_id"]):
                    yield self._enrich(state)

            subscription = await self._send(
                {"type": "subscribe_events", "event_type": "state_changed"}
            )
            log.info("subscribed to state_changed (id=%s)", subscription["id"])

            async for raw in ws:
                message = json.loads(raw)
                if message.get("type") != "event":
                    continue
                new_state = message["event"]["data"].get("new_state")
                if new_state and self._is_target(new_state["entity_id"]):
                    yield self._enrich(new_state)
