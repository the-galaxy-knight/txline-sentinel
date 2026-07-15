from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import OddsEvent, ScoreEvent
from app.ingestion.normalizer import NormalizedOddsEvent, NormalizedScoreEvent


def create_odds_events(db: Session, events: list[NormalizedOddsEvent]) -> list[OddsEvent]:
    rows: list[OddsEvent] = []
    for event in events:
        event_hash = odds_event_hash(event)
        duplicate_conditions = [OddsEvent.event_hash == event_hash]
        if event.message_id:
            duplicate_conditions.append(OddsEvent.message_id == event.message_id)
        exists_statement = select(OddsEvent.id).where(or_(*duplicate_conditions)).limit(1)
        if db.scalar(exists_statement):
            continue

        row = OddsEvent(
            source_mode=event.source_mode,
            fixture_id=event.fixture_id,
            message_id=event.message_id,
            event_hash=event_hash,
            tx_ts=event.tx_ts,
            bookmaker=event.bookmaker,
            bookmaker_id=event.bookmaker_id,
            odds_type=event.odds_type,
            market_period=event.market_period,
            market_parameters=event.market_parameters,
            game_state=event.game_state,
            in_running=event.in_running,
            outcome_name=event.outcome_name,
            price=event.price,
            implied_probability=event.implied_probability,
            raw_payload=event.raw_payload,
        )
        db.add(row)
        rows.append(row)
    return rows


def create_score_events(db: Session, events: list[NormalizedScoreEvent]) -> list[ScoreEvent]:
    rows: list[ScoreEvent] = []
    for event in events:
        event_hash = score_event_hash(event)
        exists_statement = select(ScoreEvent.id).where(ScoreEvent.event_hash == event_hash).limit(1)
        if db.scalar(exists_statement):
            continue

        row = ScoreEvent(
            source_mode=event.source_mode,
            fixture_id=event.fixture_id,
            event_hash=event_hash,
            tx_ts=event.tx_ts,
            seq=event.seq,
            game_state=event.game_state,
            action=event.action,
            clock_seconds=event.clock_seconds,
            participant_1_score=event.participant_1_score,
            participant_2_score=event.participant_2_score,
            raw_payload=event.raw_payload,
        )
        db.add(row)
        rows.append(row)
    return rows


def odds_event_hash(event: NormalizedOddsEvent) -> str:
    if event.message_id:
        return f"odds-message:{event.message_id}"
    return "odds:" + _hash_payload(
        {
            "fixture_id": event.fixture_id,
            "tx_ts": _dt(event.tx_ts),
            "bookmaker_id": event.bookmaker_id,
            "odds_type": event.odds_type,
            "market_period": event.market_period,
            "market_parameters": event.market_parameters,
            "outcome_name": event.outcome_name,
            "price": event.price,
            "implied_probability": event.implied_probability,
        }
    )


def score_event_hash(event: NormalizedScoreEvent) -> str:
    return "score:" + _hash_payload(
        {
            "fixture_id": event.fixture_id,
            "tx_ts": _dt(event.tx_ts),
            "seq": event.seq,
            "action": event.action,
            "participant_1_score": event.participant_1_score,
            "participant_2_score": event.participant_2_score,
        }
    )


def list_odds_events(
    db: Session,
    fixture_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[OddsEvent]:
    statement = select(OddsEvent).order_by(OddsEvent.id.desc())
    if fixture_id:
        statement = statement.where(OddsEvent.fixture_id == fixture_id)
    statement = statement.limit(limit).offset(offset)
    return list(db.scalars(statement))


def list_score_events(
    db: Session,
    fixture_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ScoreEvent]:
    statement = select(ScoreEvent).order_by(ScoreEvent.id.desc())
    if fixture_id:
        statement = statement.where(ScoreEvent.fixture_id == fixture_id)
    statement = statement.limit(limit).offset(offset)
    return list(db.scalars(statement))


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
