"""Replay scenario loader and background runner.

Replay mode feeds timestamped scenario events through the same EventProcessor as
live ingestion. This keeps demo behavior representative while avoiding external
TxLINE credentials during judging.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import (
    OddsEvent,
    ReplayRun,
    ScoreEvent,
    SessionLocal,
    Signal,
    SignalEvaluation,
    TelegramAlert,
)
from app.ingestion.dashboard_stream import dashboard_broker
from app.ingestion.event_processor import EventProcessor, event_processor
from app.repositories.fixtures_repo import upsert_fixtures_from_payload
from app.txline.schemas import ReplayScenario

logger = logging.getLogger(__name__)


class ReplayError(RuntimeError):
    """Base exception for replay control failures."""

    pass


class ReplayAlreadyRunningError(ReplayError):
    pass


class ReplayScenarioNotFoundError(ReplayError):
    pass


@dataclass(frozen=True)
class ReplayEvent:
    """One timestamped event from a replay scenario file."""

    offset_ms: int
    event_type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ReplayScenarioData:
    """Parsed scenario metadata and sorted replay events."""

    name: str
    display_name: str
    description: str | None
    fixture_id: str | None
    fixture_metadata: dict[str, Any]
    path: Path
    events: list[ReplayEvent]


def list_replay_scenarios(settings: Settings | None = None) -> list[ReplayScenario]:
    """Return metadata for all JSON replay scenarios in the configured directory."""

    settings = settings or get_settings()
    scenarios_dir = Path(settings.replay_scenarios_dir)
    if not scenarios_dir.exists():
        return []

    scenarios: list[ReplayScenario] = []
    for path in sorted(scenarios_dir.glob("*.json")):
        scenarios.append(_scenario_from_file(path))
    return scenarios


def load_replay_scenario(
    scenario_name: str,
    settings: Settings | None = None,
) -> ReplayScenarioData:
    """Load a scenario by file stem or display name."""

    settings = settings or get_settings()
    scenarios_dir = Path(settings.replay_scenarios_dir)
    for path in sorted(scenarios_dir.glob("*.json")):
        scenario = _load_scenario_data(path)
        if scenario.name == scenario_name or scenario.display_name == scenario_name:
            return scenario
    raise ReplayScenarioNotFoundError(f"Replay scenario '{scenario_name}' was not found.")


class ReplayManager:
    """Own the single active replay task and its persisted run state."""

    def __init__(
        self,
        settings: Settings | None = None,
        processor: EventProcessor = event_processor,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self.settings = settings or get_settings()
        self.processor = processor
        self.session_factory = session_factory
        self.current_task: asyncio.Task[None] | None = None
        self.current_run_id: int | None = None
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.stop_requested = False
        self.lock = asyncio.Lock()

    async def start(
        self,
        scenario_name: str,
        speed_multiplier: float = 30.0,
        reset_database: bool = False,
    ) -> ReplayRun:
        """Start a scenario in the background and return its persisted run row."""

        async with self.lock:
            if self.current_task and not self.current_task.done():
                raise ReplayAlreadyRunningError("A replay run is already active.")
            if reset_database:
                self.reset_database()
                self.processor.clear_state()

            scenario = load_replay_scenario(scenario_name, self.settings)
            speed = max(speed_multiplier, 0.01)
            with self.session_factory() as db:
                _seed_fixture_metadata(db, scenario)
                run = ReplayRun(
                    name=scenario.display_name,
                    scenario_name=scenario.name,
                    started_at=datetime.now(UTC),
                    speed_multiplier=speed,
                    status="running",
                    cursor_position=0,
                    events_total=len(scenario.events),
                    events_processed=0,
                )
                db.add(run)
                db.commit()
                db.refresh(run)

            self.current_run_id = run.id
            self.stop_requested = False
            self.pause_event.set()
            self.current_task = asyncio.create_task(self._run(run.id, scenario, speed))
            await self._publish_status("running", run.id)
            return run

    async def pause(self) -> ReplayRun | None:
        self.pause_event.clear()
        run = self._update_current_run(status="paused")
        await self._publish_status("paused", run.id if run else None)
        return run

    async def resume(self) -> ReplayRun | None:
        self.pause_event.set()
        run = self._update_current_run(status="running")
        await self._publish_status("running", run.id if run else None)
        return run

    async def stop(self) -> ReplayRun | None:
        self.stop_requested = True
        self.pause_event.set()
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        run = self._update_current_run(status="stopped", stopped_at=datetime.now(UTC))
        await self._publish_status("stopped", run.id if run else None)
        return run

    async def reset(self) -> None:
        await self.stop()
        self.reset_database()
        self.processor.clear_state()
        self.current_run_id = None
        self.current_task = None
        await self._publish_status("idle", None)

    def reset_database(self) -> None:
        with self.session_factory() as db:
            for model in (
                SignalEvaluation,
                TelegramAlert,
                Signal,
                OddsEvent,
                ScoreEvent,
                ReplayRun,
            ):
                db.execute(delete(model))
            db.commit()

    async def _run(
        self,
        run_id: int,
        scenario: ReplayScenarioData,
        speed_multiplier: float,
    ) -> None:
        previous_offset = 0
        try:
            for position, event in enumerate(scenario.events, start=1):
                if self.stop_requested:
                    self._update_run(run_id, status="stopped", stopped_at=datetime.now(UTC))
                    return

                while not self.pause_event.is_set():
                    await asyncio.sleep(0.1)

                delay_ms = max(event.offset_ms - previous_offset, 0)
                if delay_ms:
                    await asyncio.sleep(delay_ms / 1000 / speed_multiplier)
                previous_offset = event.offset_ms

                if event.event_type == "odds":
                    await self.processor.process_raw_odds_payload(
                        _payload_with_fixture_metadata(event.payload, scenario),
                        source_mode="replay",
                    )
                elif event.event_type == "score":
                    await self.processor.process_raw_score_payload(
                        _payload_with_fixture_metadata(event.payload, scenario),
                        source_mode="replay",
                    )
                else:
                    logger.warning("Skipping unknown replay event type: %s", event.event_type)

                self._update_run(
                    run_id,
                    cursor_position=position,
                    events_processed=position,
                    status="running",
                )

            self._update_run(run_id, status="completed", stopped_at=datetime.now(UTC))
            await self._publish_status("completed", run_id)
        except asyncio.CancelledError:
            self._update_run(run_id, status="stopped", stopped_at=datetime.now(UTC))
            raise
        except Exception:
            logger.exception("Replay run failed.")
            self._update_run(run_id, status="failed", stopped_at=datetime.now(UTC))
            await self._publish_status("failed", run_id)

    def _update_current_run(self, **values: Any) -> ReplayRun | None:
        if self.current_run_id is None:
            return None
        return self._update_run(self.current_run_id, **values)

    def _update_run(self, run_id: int, **values: Any) -> ReplayRun | None:
        with self.session_factory() as db:
            run = db.get(ReplayRun, run_id)
            if run is None:
                return None
            for key, value in values.items():
                setattr(run, key, value)
            run.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(run)
            return run

    async def _publish_status(self, status: str, run_id: int | None) -> None:
        await dashboard_broker.publish(
            "replay_status_changed", {"status": status, "run_id": run_id}
        )


def _scenario_from_file(path: Path) -> ReplayScenario:
    scenario = _load_scenario_data(path)
    return ReplayScenario(
        name=scenario.name,
        path=str(path),
        description=scenario.description,
        events_total=len(scenario.events),
        fixture_id=scenario.fixture_id,
        display_name=scenario.display_name,
    )


def _load_scenario_data(path: Path) -> ReplayScenarioData:
    metadata: dict[str, Any] = {}
    try:
        with path.open("r", encoding="utf-8") as scenario_file:
            loaded = json.load(scenario_file)
            if isinstance(loaded, dict):
                metadata = loaded
    except (OSError, json.JSONDecodeError):
        metadata = {}

    raw_events = metadata.get("events", [])
    events = [
        ReplayEvent(
            offset_ms=int(raw_event.get("offset_ms") or 0),
            event_type=str(raw_event.get("event_type") or ""),
            payload=raw_event.get("payload") if isinstance(raw_event.get("payload"), dict) else {},
        )
        for raw_event in raw_events
        if isinstance(raw_event, dict)
    ]
    events.sort(key=lambda event: event.offset_ms)
    return ReplayScenarioData(
        name=path.stem,
        display_name=str(metadata.get("name") or path.stem),
        description=metadata.get("description"),
        fixture_id=metadata.get("fixture_id"),
        fixture_metadata=_scenario_fixture_metadata(metadata),
        path=path,
        events=events,
    )


def _scenario_fixture_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    fixture = metadata.get("fixture")
    fixture = fixture if isinstance(fixture, dict) else {}
    fixture_id = metadata.get("fixture_id") or fixture.get("FixtureId") or fixture.get("fixtureId")
    return {
        key: value
        for key, value in {
            "FixtureId": fixture_id,
            "CompetitionId": fixture.get("CompetitionId") or fixture.get("competition_id"),
            "Participant1": fixture.get("Participant1") or fixture.get("participant_1"),
            "Participant2": fixture.get("Participant2") or fixture.get("participant_2"),
            "Participant1IsHome": fixture.get("Participant1IsHome")
            if "Participant1IsHome" in fixture
            else fixture.get("participant_1_is_home"),
            "StartTime": fixture.get("StartTime") or fixture.get("start_time"),
            "SportId": fixture.get("SportId") or fixture.get("sport_id"),
            "Status": fixture.get("Status") or fixture.get("status"),
        }.items()
        if value is not None
    }


def _payload_with_fixture_metadata(
    payload: dict[str, Any],
    scenario: ReplayScenarioData,
) -> dict[str, Any]:
    if not scenario.fixture_metadata:
        return payload
    enriched = dict(payload)
    existing_fixture = enriched.get("fixture")
    existing_fixture = existing_fixture if isinstance(existing_fixture, dict) else {}
    enriched["fixture"] = {**scenario.fixture_metadata, **existing_fixture}
    for key, value in scenario.fixture_metadata.items():
        enriched.setdefault(key, value)
    return enriched


def _seed_fixture_metadata(db: Session, scenario: ReplayScenarioData) -> None:
    if not scenario.fixture_metadata:
        return
    upsert_fixtures_from_payload(db, scenario.fixture_metadata)


replay_manager = ReplayManager()
