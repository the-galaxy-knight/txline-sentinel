from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class InternalEvent(BaseModel):
    event_type: Literal["odds", "score"]
    source_mode: str
    payload: dict
    received_at: datetime


class EventBus:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[InternalEvent] = asyncio.Queue()

    async def publish(self, event: InternalEvent) -> None:
        await self.queue.put(event)

    async def consume(self) -> InternalEvent:
        return await self.queue.get()


event_bus = EventBus()
