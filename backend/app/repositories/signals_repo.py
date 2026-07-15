from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import Signal


def list_signals(
    db: Session,
    fixture_id: str | None = None,
    signal_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Signal]:
    statement = select(Signal).options(selectinload(Signal.evaluations)).order_by(Signal.id.desc())
    if fixture_id:
        statement = statement.where(Signal.fixture_id == fixture_id)
    if signal_type:
        statement = statement.where(Signal.signal_type == signal_type)
    if status:
        statement = statement.where(Signal.status == status)
    if min_confidence is not None:
        statement = statement.where(Signal.confidence_score >= min_confidence)
    statement = statement.limit(limit).offset(offset)
    return list(db.scalars(statement))


def get_signal(db: Session, signal_id: int) -> Signal | None:
    statement = (
        select(Signal)
        .options(selectinload(Signal.evaluations))
        .where(Signal.id == signal_id)
    )
    return db.scalar(statement)
