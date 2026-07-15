"""Signal deduplication across memory and persisted history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Signal
from app.signals.models import ScoredSignal


@dataclass
class DedupedSignal:
    """Minimal remembered signal metadata for in-process duplicate checks."""

    confidence_score: float
    event_ts_key: object


class SignalDeduplicator:
    """Suppress near-duplicate signals unless confidence improves materially."""

    def __init__(self, window_seconds: int = 180, min_confidence_improvement: float = 10.0) -> None:
        self.window = timedelta(seconds=window_seconds)
        self.min_confidence_improvement = min_confidence_improvement
        self.recent: dict[tuple[str, str, str, str, str], tuple[object, float]] = {}

    def clear(self) -> None:
        self.recent.clear()

    def should_emit(self, db: Session, scored: ScoredSignal) -> bool:
        """Return whether a scored signal should be persisted and streamed."""

        candidate = scored.candidate
        key = self._key(scored)
        event_ts = candidate.tx_end_ts
        if event_ts is None:
            return True

        remembered = self.recent.get(key)
        if remembered:
            previous_ts, previous_confidence = remembered
            if (
                hasattr(previous_ts, "__sub__")
                and event_ts - previous_ts <= self.window
                and scored.confidence_score < previous_confidence + self.min_confidence_improvement
            ):
                return False

        since = event_ts - self.window
        statement = (
            select(Signal)
            .where(Signal.fixture_id == candidate.fixture_id)
            .where(Signal.market_key == candidate.market_key)
            .where(Signal.outcome_name == candidate.outcome_name)
            .where(Signal.signal_type == candidate.signal_type)
            .where(Signal.direction == candidate.direction)
            .where(Signal.tx_end_ts.is_not(None))
            .where(Signal.tx_end_ts >= since)
            .order_by(Signal.confidence_score.desc())
        )
        existing = db.scalar(statement)
        if existing:
            minimum_confidence = existing.confidence_score + self.min_confidence_improvement
            if scored.confidence_score < minimum_confidence:
                return False
        return True

    def remember(self, scored: ScoredSignal) -> None:
        event_ts = scored.candidate.tx_end_ts
        if event_ts is None:
            return
        self.recent[self._key(scored)] = (event_ts, scored.confidence_score)

    @staticmethod
    def _key(scored: ScoredSignal) -> tuple[str, str, str, str, str]:
        candidate = scored.candidate
        return (
            candidate.fixture_id,
            candidate.market_key,
            candidate.outcome_name,
            candidate.signal_type,
            candidate.direction,
        )
