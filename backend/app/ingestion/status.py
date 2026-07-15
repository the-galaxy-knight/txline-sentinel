from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class StreamStatus:
    name: str
    state: str = "idle"
    last_event_id: str | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    reconnect_attempts: int = 0
    events_received: int = 0


@dataclass
class SnapshotStatus:
    state: str = "idle"
    last_poll_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    fixtures_processed: int = 0
    odds_events_processed: int = 0
    score_events_processed: int = 0


@dataclass
class IngestionRuntimeStatus:
    live_streams: dict[str, StreamStatus] = field(
        default_factory=lambda: {
            "odds": StreamStatus("odds"),
            "scores": StreamStatus("scores"),
        }
    )
    snapshot: SnapshotStatus = field(default_factory=SnapshotStatus)

    def mark_stream_state(
        self,
        stream_name: str,
        state: str,
        *,
        event_id: str | None = None,
        event_at: datetime | None = None,
        event_received: bool = False,
        error: str | None = None,
    ) -> None:
        stream = self.live_streams.setdefault(stream_name, StreamStatus(stream_name))
        stream.state = state
        if event_received:
            stream.events_received += 1
            stream.last_event_at = event_at or datetime.now(UTC)
        if event_id is not None:
            stream.last_event_id = event_id
        if error is not None:
            stream.last_error = error
            stream.reconnect_attempts += 1
        elif state == "running":
            stream.last_error = None

    def mark_snapshot_poll(
        self,
        *,
        state: str,
        fixtures_processed: int = 0,
        odds_events_processed: int = 0,
        score_events_processed: int = 0,
        error: str | None = None,
    ) -> None:
        self.snapshot.state = state
        self.snapshot.last_poll_at = datetime.now(UTC)
        self.snapshot.fixtures_processed = fixtures_processed
        self.snapshot.odds_events_processed = odds_events_processed
        self.snapshot.score_events_processed = score_events_processed
        if error:
            self.snapshot.last_error = error
        elif state == "ok":
            self.snapshot.last_success_at = datetime.now(UTC)


ingestion_status = IngestionRuntimeStatus()
