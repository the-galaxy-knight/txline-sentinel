"""In-memory event fanout for the future dashboard SSE endpoint."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


class StreamEvent(BaseModel):
    """JSON-serializable event envelope emitted over server-sent events."""

    type: str
    created_at: datetime
    payload: dict[str, Any]


class DashboardEventBroker:
    """Small process-local publish/subscribe broker for dashboard updates."""

    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[StreamEvent]] = set()

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = StreamEvent(type=event_type, created_at=datetime.now(UTC), payload=payload)
        stale: list[asyncio.Queue[StreamEvent]] = []
        for subscriber in self.subscribers:
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(subscriber)
        for subscriber in stale:
            self.subscribers.discard(subscriber)

    async def subscribe(self) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=100)
        self.subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self.subscribers.discard(queue)


def encode_sse(event: StreamEvent) -> str:
    """Encode a dashboard event as an SSE frame."""

    payload = event.model_dump(mode="json")
    return f"event: {event.type}\ndata: {json.dumps(payload)}\n\n"


dashboard_broker = DashboardEventBroker()
