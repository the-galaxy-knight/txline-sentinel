"""TxLINE snapshot polling fallback ingestion mode."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.ingestion.event_processor import EventProcessor, event_processor
from app.ingestion.normalizer import normalize_odds_payload, normalize_score_payload
from app.ingestion.status import ingestion_status
from app.repositories.events_repo import create_odds_events, create_score_events
from app.repositories.fixtures_repo import upsert_fixtures_from_payload
from app.txline.auth import TxLineConfigurationError
from app.txline.client import TxLineClient

logger = logging.getLogger(__name__)


class SnapshotRunner:
    """Poll configured TxLINE snapshot endpoints and feed normalized events."""

    def __init__(
        self,
        settings: Settings | None = None,
        processor: EventProcessor = event_processor,
    ) -> None:
        self.settings = settings or get_settings()
        self.processor = processor

    async def run_forever(self) -> None:
        """Poll snapshots until cancelled, keeping the app alive on transient errors."""

        if not self.settings.snapshots_configured:
            logger.info(
                "Snapshot ingestion is disabled because TxLINE snapshots are not configured."
            )
            return

        async with TxLineClient(self.settings) as client:
            while True:
                try:
                    await self.run_once(client)
                except asyncio.CancelledError:
                    raise
                except TxLineConfigurationError as exc:
                    logger.warning("Snapshot ingestion stopped: %s", exc)
                    ingestion_status.mark_snapshot_poll(state="disabled", error=str(exc))
                    return
                except Exception as exc:
                    logger.exception("Snapshot ingestion poll failed.")
                    ingestion_status.mark_snapshot_poll(state="degraded", error=str(exc))

                await asyncio.sleep(self.settings.snapshot_poll_seconds)

    async def run_once(self, client: TxLineClient | None = None) -> None:
        """Execute one fixtures/odds/scores snapshot poll."""

        owns_client = client is None
        client = client or TxLineClient(self.settings)
        fixtures_processed = 0
        odds_events_processed = 0
        score_events_processed = 0
        try:
            if self.settings.txline_fixtures_snapshot_path:
                fixtures = await client.fetch_fixtures_snapshot()
                with SessionLocal() as db:
                    fixtures_processed = len(upsert_fixtures_from_payload(db, fixtures))
                    db.commit()

            if self.settings.txline_odds_snapshot_path:
                odds_payload = await client.fetch_odds_snapshot()
                odds_events_processed = await self._persist_odds_snapshot(odds_payload)

            if self.settings.txline_scores_snapshot_path:
                scores_payload = await client.fetch_scores_snapshot()
                score_events_processed = await self._persist_scores_snapshot(scores_payload)

            ingestion_status.mark_snapshot_poll(
                state="ok",
                fixtures_processed=fixtures_processed,
                odds_events_processed=odds_events_processed,
                score_events_processed=score_events_processed,
            )
            logger.info(
                "Snapshot poll complete: fixtures=%s odds=%s scores=%s",
                fixtures_processed,
                odds_events_processed,
                score_events_processed,
            )
        finally:
            if owns_client:
                await client.aclose()

    async def _persist_odds_snapshot(self, raw: dict | list) -> int:
        payload = raw if isinstance(raw, dict) else {"Data": raw}
        result = await self.processor.process_raw_odds_payload(payload, source_mode="snapshot")
        return result.odds_events_processed

    async def _persist_scores_snapshot(self, raw: dict | list) -> int:
        payload = raw if isinstance(raw, dict) else {"Data": raw}
        result = await self.processor.process_raw_score_payload(payload, source_mode="snapshot")
        return result.score_events_processed


def persist_odds_events(db: Session, raw: dict, source_mode: str = "snapshot") -> int:
    events = normalize_odds_payload(raw, source_mode=source_mode)
    create_odds_events(db, events)
    return len(events)


def persist_score_events(db: Session, raw: dict, source_mode: str = "snapshot") -> int:
    events = normalize_score_payload(raw, source_mode=source_mode)
    create_score_events(db, events)
    return len(events)
