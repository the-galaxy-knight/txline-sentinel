from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.ingestion.dashboard_stream import dashboard_broker, encode_sse

router = APIRouter(prefix="/api", tags=["Stream"])


@router.get("/stream")
async def stream_events() -> StreamingResponse:
    async def event_iterator() -> AsyncIterator[str]:
        async for event in dashboard_broker.subscribe():
            yield encode_sse(event)

    return StreamingResponse(event_iterator(), media_type="text/event-stream")
