"""Build local replay scenarios from TxLINE historical interval data."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from inspect import isawaitable
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.txline.client import TxLineClient

INTERVAL_SECONDS = 5 * 60
HistoricalReplayProgressCallback = Callable[["HistoricalReplayProgress"], Awaitable[None] | None]


@dataclass(frozen=True)
class HistoricalInterval:
    """A TxLINE historical 5-minute interval coordinate."""

    epoch_day: int
    hour_of_day: int
    interval: int
    starts_at: datetime


@dataclass(frozen=True)
class HistoricalReplayBuildResult:
    """Summary of a generated TxLINE historical replay file."""

    path: Path
    scenario_name: str
    intervals_requested: int
    odds_events: int
    score_events: int
    events_total: int


@dataclass(frozen=True)
class HistoricalReplayProgress:
    """Incremental progress for a TxLINE historical replay build."""

    intervals_requested: int
    intervals_completed: int
    odds_events: int
    score_events: int
    current_interval: HistoricalInterval | None = None


@dataclass(frozen=True)
class _RawReplayEvent:
    event_type: str
    event_ts: datetime
    payload: dict[str, Any]


async def build_historical_replay(
    *,
    start: datetime,
    end: datetime,
    fixture_id: int | str | None = None,
    scenario_name: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    output_dir: Path | str | None = None,
    settings: Settings | None = None,
    progress_callback: HistoricalReplayProgressCallback | None = None,
) -> HistoricalReplayBuildResult:
    """Fetch TxLINE historical intervals and save them as a replay scenario."""

    settings = settings or get_settings()
    async with TxLineClient(settings) as client:
        builder = HistoricalReplayBuilder(client=client, settings=settings)
        return await builder.build(
            start=start,
            end=end,
            fixture_id=fixture_id,
            scenario_name=scenario_name,
            display_name=display_name,
            description=description,
            output_dir=output_dir,
            progress_callback=progress_callback,
        )


class HistoricalReplayBuilder:
    """Convert TxLINE historical odds and score intervals into replay JSON."""

    def __init__(self, client: TxLineClient, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    async def build(
        self,
        *,
        start: datetime,
        end: datetime,
        fixture_id: int | str | None = None,
        scenario_name: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
        output_dir: Path | str | None = None,
        progress_callback: HistoricalReplayProgressCallback | None = None,
    ) -> HistoricalReplayBuildResult:
        """Fetch intervals in `[start, end)` and write a scenario file."""

        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        if end_utc <= start_utc:
            raise ValueError("Historical replay end time must be after start time.")

        intervals = intervals_between(start_utc, end_utc)
        fixture_metadata = await self._fixture_metadata(start_utc, fixture_id)
        raw_events: list[_RawReplayEvent] = []
        odds_events_total = 0
        score_events_total = 0

        await _notify_progress(
            progress_callback,
            HistoricalReplayProgress(
                intervals_requested=len(intervals),
                intervals_completed=0,
                odds_events=0,
                score_events=0,
                current_interval=intervals[0] if intervals else None,
            ),
        )

        for interval_index, interval in enumerate(intervals, start=1):
            odds_payload = await self.client.fetch_historical_odds_interval(
                interval.epoch_day,
                interval.hour_of_day,
                interval.interval,
                fixture_id=fixture_id,
            )
            score_payload = await self.client.fetch_historical_scores_interval(
                interval.epoch_day,
                interval.hour_of_day,
                interval.interval,
                fixture_id=fixture_id,
            )
            odds_events = _events_from_payload(
                odds_payload,
                event_type="odds",
                interval_start=interval.starts_at,
                start=start_utc,
                end=end_utc,
            )
            score_events = _events_from_payload(
                score_payload,
                event_type="score",
                interval_start=interval.starts_at,
                start=start_utc,
                end=end_utc,
            )
            raw_events.extend(odds_events)
            raw_events.extend(score_events)
            odds_events_total += len(odds_events)
            score_events_total += len(score_events)
            await _notify_progress(
                progress_callback,
                HistoricalReplayProgress(
                    intervals_requested=len(intervals),
                    intervals_completed=interval_index,
                    odds_events=odds_events_total,
                    score_events=score_events_total,
                    current_interval=interval,
                ),
            )

        raw_events.sort(key=lambda event: (event.event_ts, 0 if event.event_type == "score" else 1))
        scenario_start = raw_events[0].event_ts if raw_events else start_utc
        replay_events = [
            {
                "offset_ms": max(
                    0,
                    int((event.event_ts - scenario_start).total_seconds() * 1000),
                ),
                "event_type": event.event_type,
                "payload": event.payload,
            }
            for event in raw_events
        ]

        stem = scenario_name or _default_scenario_name(start_utc, end_utc, fixture_id)
        output_path = (
            Path(output_dir or self.settings.replay_scenarios_dir) / f"{_slugify(stem)}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        replay_fixture_id = (
            str(fixture_id) if fixture_id is not None else _first_fixture_id(raw_events)
        )
        payload = {
            "name": display_name or stem.replace("_", " ").title(),
            "description": description
            or _default_description(start_utc, end_utc, fixture_id),
            "fixture_id": replay_fixture_id,
            "fixture": fixture_metadata,
            "source": "txline_historical",
            "source_range": {
                "start": start_utc.isoformat(),
                "end": end_utc.isoformat(),
                "intervals_requested": len(intervals),
            },
            "events": replay_events,
        }
        with output_path.open("w", encoding="utf-8") as scenario_file:
            json.dump(payload, scenario_file, indent=2)
            scenario_file.write("\n")

        return HistoricalReplayBuildResult(
            path=output_path,
            scenario_name=output_path.stem,
            intervals_requested=len(intervals),
            odds_events=odds_events_total,
            score_events=score_events_total,
            events_total=len(raw_events),
        )

    async def _fixture_metadata(
        self,
        start: datetime,
        fixture_id: int | str | None,
    ) -> dict[str, Any]:
        if fixture_id is None:
            return {}
        try:
            fixtures = await self.client.fetch_fixtures_snapshot(
                start_epoch_day=int(start.timestamp() // 86400)
            )
        except Exception:
            return {"FixtureId": str(fixture_id)}

        fixture_id_text = str(fixture_id)
        for record in _payload_records(fixtures):
            if str(_get(record, "FixtureId", "fixtureId", "fixture_id")) != fixture_id_text:
                continue
            return {
                key: value
                for key, value in {
                    "FixtureId": fixture_id_text,
                    "CompetitionId": _get(record, "CompetitionId", "competition_id"),
                    "Participant1": _get(record, "Participant1", "participant_1"),
                    "Participant2": _get(record, "Participant2", "participant_2"),
                    "Participant1IsHome": _get(
                        record,
                        "Participant1IsHome",
                        "participant_1_is_home",
                    ),
                    "StartTime": _get(record, "StartTime", "start_time"),
                    "SportId": _get(record, "SportId", "sport_id"),
                    "Status": _get(record, "Status", "status", "GameState"),
                }.items()
                if value is not None
            }
        return {"FixtureId": fixture_id_text}


def intervals_between(start: datetime, end: datetime) -> list[HistoricalInterval]:
    """Return all TxLINE 5-minute intervals intersecting `[start, end)`."""

    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    if end_utc <= start_utc:
        return []

    current = _floor_to_interval(start_utc)
    intervals: list[HistoricalInterval] = []
    while current < end_utc:
        intervals.append(_interval_for_start(current))
        current += timedelta(seconds=INTERVAL_SECONDS)
    return intervals


async def _notify_progress(
    callback: HistoricalReplayProgressCallback | None,
    progress: HistoricalReplayProgress,
) -> None:
    if callback is None:
        return
    result = callback(progress)
    if isawaitable(result):
        await result


def _events_from_payload(
    payload: dict | list,
    *,
    event_type: str,
    interval_start: datetime,
    start: datetime,
    end: datetime,
) -> list[_RawReplayEvent]:
    events: list[_RawReplayEvent] = []
    for index, record in enumerate(_payload_records(payload)):
        event_ts = _timestamp_from_payload(record) or interval_start + timedelta(milliseconds=index)
        if start <= event_ts < end:
            events.append(_RawReplayEvent(event_type=event_type, event_ts=event_ts, payload=record))
    return events


def _payload_records(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    if _looks_like_event_payload(raw):
        return [raw]
    for key in ("Data", "data", "Items", "items", "Events", "events", "Results", "results"):
        nested = raw.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return _payload_records(nested)
    return [raw]


def _looks_like_event_payload(raw: dict[str, Any]) -> bool:
    event_keys = {
        "fixtureid",
        "fixture_id",
        "eventid",
        "gameid",
        "messageid",
        "prices",
        "pricenames",
        "score",
        "action",
        "seq",
        "ts",
        "timestamp",
    }
    return bool(event_keys & {str(key).lower() for key in raw})


def _timestamp_from_payload(payload: dict[str, Any]) -> datetime | None:
    return _parse_datetime(_get(payload, "Ts", "ts", "Timestamp", "timestamp", "tx_ts"))


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return _parse_datetime(int(text))
        try:
            return _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _interval_for_start(value: datetime) -> HistoricalInterval:
    value_utc = _as_utc(value)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = value_utc - epoch
    epoch_day = delta.days
    hour_of_day = value_utc.hour
    interval = value_utc.minute // 5
    return HistoricalInterval(
        epoch_day=epoch_day,
        hour_of_day=hour_of_day,
        interval=interval,
        starts_at=value_utc,
    )


def _floor_to_interval(value: datetime) -> datetime:
    value_utc = _as_utc(value)
    minute = value_utc.minute - (value_utc.minute % 5)
    return value_utc.replace(minute=minute, second=0, microsecond=0)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _get(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    lowered = {str(key).lower(): value for key, value in data.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return None


def _first_fixture_id(events: list[_RawReplayEvent]) -> str | None:
    for event in events:
        fixture_id = _get(event.payload, "FixtureId", "fixtureId", "fixture_id")
        if fixture_id is not None:
            return str(fixture_id)
    return None


def _default_scenario_name(
    start: datetime,
    end: datetime,
    fixture_id: int | str | None,
) -> str:
    fixture_part = f"fixture_{fixture_id}" if fixture_id is not None else "all_fixtures"
    return (
        f"txline_historical_{fixture_part}_"
        f"{start.strftime('%Y%m%dT%H%M')}_{end.strftime('%Y%m%dT%H%M')}"
    )


def _default_description(
    start: datetime,
    end: datetime,
    fixture_id: int | str | None,
) -> str:
    fixture_part = f"fixture {fixture_id}" if fixture_id is not None else "all fixtures"
    return (
        "TxLINE historical replay generated from odds and score interval endpoints for "
        f"{fixture_part} from {start.isoformat()} to {end.isoformat()}."
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "txline_historical_replay"
