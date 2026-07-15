"""Live TxLINE SSE ingestion runner with reconnect and offset handling."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import IngestionOffset, SessionLocal
from app.ingestion.event_processor import EventProcessor, event_processor
from app.ingestion.normalizer import normalize_odds_payload, normalize_score_payload
from app.ingestion.status import ingestion_status
from app.txline.auth import TxLineConfigurationError
from app.txline.client import TxLineClient
from app.txline.sse import SseEvent

logger = logging.getLogger(__name__)


class LiveRunner:
    """Consume configured TxLINE odds and score SSE streams independently."""

    def __init__(
        self,
        settings: Settings | None = None,
        processor: EventProcessor = event_processor,
    ) -> None:
        self.settings = settings or get_settings()
        self.processor = processor

    async def run_forever(self) -> None:
        """Run live ingestion until cancelled or configuration is unavailable."""

        if not self.settings.live_streams_configured:
            logger.info("Live ingestion is disabled because TxLINE streams are not configured.")
            return

        async with TxLineClient(self.settings) as client:
            tasks: list[asyncio.Task[None]] = []
            if self.settings.txline_odds_stream_path:
                tasks.append(
                    asyncio.create_task(
                        self._consume_stream("odds", client.stream_odds, self._persist_odds_event)
                    )
                )
            if self.settings.txline_scores_stream_path:
                tasks.append(
                    asyncio.create_task(
                        self._consume_stream(
                            "scores", client.stream_scores, self._persist_score_event
                        )
                    )
                )

            if not tasks:
                logger.info("Live ingestion has no configured stream paths.")
                return

            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    task.cancel()

    async def _consume_stream(
        self,
        stream_name: str,
        stream_factory: Callable[[str | None], AsyncIterator[SseEvent]],
        persist_event: Callable[[dict], Awaitable[datetime | None]],
    ) -> None:
        """Consume one SSE stream with persisted offsets and exponential backoff."""

        backoff_seconds = self.settings.live_reconnect_initial_seconds
        while True:
            last_event_id = self._load_offset(stream_name)
            try:
                logger.info(
                    "Starting TxLINE %s stream from offset %s.",
                    stream_name,
                    last_event_id or "<none>",
                )
                ingestion_status.mark_stream_state(stream_name, "connecting")
                events = self._with_heartbeat_timeout(stream_factory(last_event_id))
                ingestion_status.mark_stream_state(stream_name, "running")
                async for event in events:
                    payload = self._decode_event_payload(event)
                    tx_ts = await persist_event(payload)
                    self._store_offset(stream_name, event.id, tx_ts)
                    ingestion_status.mark_stream_state(
                        stream_name,
                        "running",
                        event_id=event.id,
                        event_at=tx_ts,
                        event_received=True,
                    )
                backoff_seconds = self.settings.live_reconnect_initial_seconds
            except asyncio.CancelledError:
                ingestion_status.mark_stream_state(stream_name, "stopped")
                raise
            except TxLineConfigurationError as exc:
                logger.warning("Live ingestion stopped for %s: %s", stream_name, exc)
                ingestion_status.mark_stream_state(stream_name, "disabled", error=str(exc))
                return
            except TimeoutError as exc:
                logger.warning(
                    "TxLINE %s stream heartbeat timed out; reconnecting in %s seconds.",
                    stream_name,
                    backoff_seconds,
                )
                ingestion_status.mark_stream_state(stream_name, "degraded", error=str(exc))
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, self.settings.live_reconnect_max_seconds)
            except Exception:
                logger.exception(
                    "Live ingestion stream %s failed; reconnecting in %s seconds.",
                    stream_name,
                    backoff_seconds,
                )
                ingestion_status.mark_stream_state(stream_name, "degraded", error="stream failure")
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, self.settings.live_reconnect_max_seconds)

    async def _with_heartbeat_timeout(
        self, events: AsyncIterator[SseEvent]
    ) -> AsyncIterator[SseEvent]:
        iterator = events.__aiter__()
        while True:
            try:
                yield await asyncio.wait_for(
                    anext(iterator),
                    timeout=self.settings.live_stream_heartbeat_timeout_seconds,
                )
            except StopAsyncIteration:
                return

    @staticmethod
    def _decode_event_payload(event: SseEvent) -> dict:
        try:
            decoded = json.loads(event.data)
        except json.JSONDecodeError:
            decoded = {"data": event.data}
        return decoded if isinstance(decoded, dict) else {"Data": decoded}

    async def _persist_odds_event(self, raw: dict) -> datetime | None:
        events = normalize_odds_payload(raw, source_mode="live")
        await self.processor.process_odds_events(events)
        return events[-1].tx_ts if events else None

    async def _persist_score_event(self, raw: dict) -> datetime | None:
        events = normalize_score_payload(raw, source_mode="live")
        await self.processor.process_score_events(events)
        return events[-1].tx_ts if events else None

    @staticmethod
    def _load_offset(stream_name: str) -> str | None:
        with SessionLocal() as db:
            statement = select(IngestionOffset).where(IngestionOffset.stream_name == stream_name)
            offset = db.scalar(statement)
            return offset.last_event_id if offset else None

    @staticmethod
    def _store_offset(
        stream_name: str,
        last_event_id: str | None,
        last_tx_ts: datetime | None,
    ) -> None:
        with SessionLocal() as db:
            statement = select(IngestionOffset).where(IngestionOffset.stream_name == stream_name)
            offset = db.scalar(statement)
            if offset is None:
                offset = IngestionOffset(stream_name=stream_name)
                db.add(offset)
            offset.last_event_id = last_event_id
            offset.last_tx_ts = last_tx_ts
            offset.updated_at = datetime.now(UTC)
            db.commit()
