from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Fixture


def list_fixtures(db: Session, limit: int = 100, offset: int = 0) -> list[Fixture]:
    statement = select(Fixture).order_by(Fixture.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))


def get_fixture(db: Session, fixture_id: str) -> Fixture | None:
    statement = select(Fixture).where(Fixture.fixture_id == fixture_id)
    return db.scalar(statement)


def upsert_fixtures_from_payload(db: Session, raw: dict | list) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for record in _payload_records(raw):
        fixture_id = _as_str(
            _get(record, "FixtureId", "fixture_id", "fixtureId", "EventId", "GameId")
        )
        if not fixture_id:
            continue

        fixture = get_fixture(db, fixture_id)
        if fixture is None:
            fixture = Fixture(fixture_id=fixture_id)
            db.add(fixture)

        fixture.competition_id = _as_str(
            _get(record, "CompetitionId", "competition_id", "LeagueId")
        )
        fixture.participant_1 = (
            _as_str(_get(record, "Participant1", "participant_1", "HomeTeam", "Team1")) or ""
        )
        fixture.participant_2 = (
            _as_str(_get(record, "Participant2", "participant_2", "AwayTeam", "Team2")) or ""
        )
        fixture.participant_1_is_home = _as_bool(
            _get(record, "Participant1IsHome", "participant_1_is_home", "IsHome")
        )
        fixture.start_time = _parse_datetime(
            _get(record, "StartTime", "start_time", "StartTs", "ScheduledStart")
        )
        fixture.sport_id = _as_str(_get(record, "SportId", "sport_id", "Sport"))
        fixture.status = _as_str(_get(record, "Status", "status", "GameState"))
        fixture.raw_payload = record
        fixtures.append(fixture)
    return fixtures


def _payload_records(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    for key in ("Data", "data", "Items", "items", "Fixtures", "fixtures", "Results", "results"):
        nested = raw.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return _payload_records(nested)
    return [raw]


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


def _as_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, int | float):
        return bool(value)
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
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
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
