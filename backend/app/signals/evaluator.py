"""Predictiveness tracking for emitted signals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Signal, SignalEvaluation
from app.ingestion.normalizer import NormalizedOddsEvent
from app.market.state import MarketState, market_key_for_event

EVALUATION_HORIZONS_MINUTES = (5, 10, 15)


def create_pending_evaluations(db: Session, signal: Signal) -> list[SignalEvaluation]:
    """Create the standard 5, 10, and 15 minute follow-through checks."""

    evaluations = [
        SignalEvaluation(
            signal_id=signal.id,
            horizon_minutes=horizon,
            probability_at_signal=signal.probability_after,
            result="pending",
        )
        for horizon in EVALUATION_HORIZONS_MINUTES
    ]
    db.add_all(evaluations)
    return evaluations


def evaluate_pending_for_event(
    db: Session,
    event: NormalizedOddsEvent,
    market_state: MarketState,
) -> list[SignalEvaluation]:
    """Update due signal evaluations when a matching odds event reaches a horizon."""

    if event.implied_probability is None:
        return []
    event_ts = _as_utc(event.tx_ts or datetime.now(UTC))
    market_key = market_key_for_event(event)
    statement = (
        select(SignalEvaluation, Signal)
        .join(Signal, Signal.id == SignalEvaluation.signal_id)
        .where(SignalEvaluation.result == "pending")
        .where(Signal.fixture_id == event.fixture_id)
        .where(Signal.market_key == market_key)
        .where(Signal.outcome_name == (event.outcome_name or "unknown"))
    )
    updated: list[SignalEvaluation] = []
    for evaluation, signal in db.execute(statement).all():
        if signal.tx_end_ts is None:
            continue
        signal_ts = _as_utc(signal.tx_end_ts)
        horizon_ts = signal_ts + timedelta(minutes=evaluation.horizon_minutes)
        if event_ts < horizon_ts:
            continue
        delta = event.implied_probability - evaluation.probability_at_signal
        evaluation.evaluated_at = event_ts
        evaluation.probability_at_horizon = event.implied_probability
        evaluation.delta_after_signal = delta
        evaluation.continued_direction = (
            delta >= 0 if signal.direction == "up" else delta <= 0
        )
        evaluation.result = _result_for_delta(delta, signal.direction)
        favorable, adverse = market_state.max_excursions(
            signal.market_key,
            signal_ts,
            evaluation.probability_at_signal,
            signal.direction,
        )
        evaluation.max_favorable_excursion = favorable
        evaluation.max_adverse_excursion = adverse
        updated.append(evaluation)

    for evaluation in updated:
        signal = db.get(Signal, evaluation.signal_id)
        if signal:
            _update_signal_status(db, signal)
    return updated


def _result_for_delta(delta: float, direction: str) -> str:
    if abs(delta) < 0.005:
        return "neutral"
    if direction == "up":
        return "confirmed" if delta > 0 else "failed"
    return "confirmed" if delta < 0 else "failed"


def _update_signal_status(db: Session, signal: Signal) -> None:
    evaluations = list(signal.evaluations)
    if not evaluations:
        return
    if all(evaluation.result != "pending" for evaluation in evaluations):
        signal.status = "evaluated"
    elif any(evaluation.result != "pending" for evaluation in evaluations):
        signal.status = "evaluating"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
