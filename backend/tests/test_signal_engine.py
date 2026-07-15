from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, Signal, SignalEvaluation
from app.explanation.generator import ExplanationGenerator
from app.ingestion.event_processor import EventProcessor
from app.ingestion.normalizer import NormalizedOddsEvent, NormalizedScoreEvent
from app.market.state import MarketState, ScoreState
from app.signals.deduplication import SignalDeduplicator
from app.signals.detector import SignalDetector
from app.signals.scoring import score_signal


def test_rolling_market_state_tracks_deltas() -> None:
    state = MarketState()
    start = _dt("2026-07-09T12:00:00+00:00")
    state.update_odds(_odds("fixture-1", "Argentina", 0.521, start))
    snapshot = state.update_odds(
        _odds("fixture-1", "Argentina", 0.614, start + timedelta(minutes=5))
    )

    assert snapshot is not None
    assert snapshot.p_now == 0.614
    assert round(snapshot.delta_300s or 0, 3) == 0.093
    assert snapshot.bookmaker_count == 1


def test_detector_finds_sharp_and_no_score_movement() -> None:
    market = MarketState()
    scores = ScoreState()
    detector = SignalDetector()
    start = _dt("2026-07-09T12:00:00+00:00")
    scores.update_score(_score("fixture-1", "match_started", start, 0, 0))
    market.update_odds(_odds("fixture-1", "Argentina", 0.521, start))
    event = _odds("fixture-1", "Argentina", 0.614, start + timedelta(minutes=5))
    snapshot = market.update_odds(event)

    signals = detector.detect(event, snapshot, scores.get("fixture-1"))  # type: ignore[arg-type]
    signal_types = {signal.signal_type for signal in signals}

    assert "sharp_movement" in signal_types
    assert "no_score_market_pressure" in signal_types


def test_detector_finds_post_event_reaction() -> None:
    market = MarketState()
    scores = ScoreState()
    detector = SignalDetector()
    start = _dt("2026-07-09T13:00:00+00:00")
    market.update_odds(_odds("fixture-2", "Brazil", 0.45, start + timedelta(seconds=5)))
    scores.update_score(_score("fixture-2", "goal_brazil", start + timedelta(minutes=2), 1, 0))
    event = _odds("fixture-2", "Brazil", 0.535, start + timedelta(minutes=3, seconds=50))
    snapshot = market.update_odds(event)

    signals = detector.detect(event, snapshot, scores.get("fixture-2"))  # type: ignore[arg-type]

    assert "post_event_reaction" in {signal.signal_type for signal in signals}


def test_goal_kick_is_not_goal_like_context() -> None:
    market = MarketState()
    scores = ScoreState()
    detector = SignalDetector()
    start = _dt("2026-07-09T13:00:00+00:00")
    market.update_odds(_odds("fixture-2", "Brazil", 0.45, start + timedelta(seconds=5)))
    scores.update_score(_score("fixture-2", "goal_kick", start + timedelta(minutes=2), 0, 0))
    event = _odds("fixture-2", "Brazil", 0.535, start + timedelta(minutes=3, seconds=50))
    snapshot = market.update_odds(event)

    signals = detector.detect(event, snapshot, scores.get("fixture-2"))  # type: ignore[arg-type]

    assert "post_event_reaction" not in {signal.signal_type for signal in signals}


def test_detector_finds_bookmaker_divergence() -> None:
    market = MarketState()
    detector = SignalDetector()
    start = _dt("2026-07-09T14:00:00+00:00")
    market.update_odds(_odds("fixture-3", "Spain", 0.5, start, bookmaker_id="book-a"))
    market.update_odds(_odds("fixture-3", "Spain", 0.5, start, bookmaker_id="book-b"))
    event = _odds("fixture-3", "Spain", 0.58, start + timedelta(minutes=1), "book-a")
    snapshot = market.update_odds(event)

    signals = detector.detect(event, snapshot, None)  # type: ignore[arg-type]

    assert "bookmaker_divergence" in {signal.signal_type for signal in signals}


def test_signal_scoring_returns_high_confidence_for_no_score_pressure() -> None:
    market = MarketState()
    scores = ScoreState()
    detector = SignalDetector()
    start = _dt("2026-07-09T12:00:00+00:00")
    scores.update_score(_score("fixture-1", "match_started", start, 0, 0))
    market.update_odds(_odds("fixture-1", "Argentina", 0.521, start))
    event = _odds("fixture-1", "Argentina", 0.614, start + timedelta(minutes=5))
    snapshot = market.update_odds(event)
    candidate = next(
        signal
        for signal in detector.detect(event, snapshot, scores.get("fixture-1"))  # type: ignore[arg-type]
        if signal.signal_type == "no_score_market_pressure"
    )

    scored = score_signal(candidate)

    assert scored.confidence_score >= 80
    assert scored.magnitude_score == 1.0


def test_deduplication_blocks_near_duplicate_signal() -> None:
    session_factory = _session_factory()
    market = MarketState()
    scores = ScoreState()
    detector = SignalDetector()
    dedupe = SignalDeduplicator()
    start = _dt("2026-07-09T12:00:00+00:00")
    scores.update_score(_score("fixture-1", "match_started", start, 0, 0))
    market.update_odds(_odds("fixture-1", "Argentina", 0.521, start))
    event = _odds("fixture-1", "Argentina", 0.614, start + timedelta(minutes=5))
    snapshot = market.update_odds(event)
    candidate = next(
        signal
        for signal in detector.detect(event, snapshot, scores.get("fixture-1"))  # type: ignore[arg-type]
        if signal.signal_type == "sharp_movement"
    )
    scored = score_signal(candidate)

    with session_factory() as db:
        assert dedupe.should_emit(db, scored)
        dedupe.remember(scored)
        assert not dedupe.should_emit(db, scored)


def test_explanation_generator_uses_fallback_when_llm_fails() -> None:
    class FailingGenerator(ExplanationGenerator):
        async def _generate_with_llm(self, scored):  # type: ignore[no-untyped-def]
            raise RuntimeError("forced failure")

    market = MarketState()
    scores = ScoreState()
    detector = SignalDetector()
    start = _dt("2026-07-09T12:00:00+00:00")
    scores.update_score(_score("fixture-1", "match_started", start, 0, 0))
    market.update_odds(_odds("fixture-1", "Argentina", 0.521, start))
    event = _odds("fixture-1", "Argentina", 0.614, start + timedelta(minutes=5))
    snapshot = market.update_odds(event)
    candidate = detector.detect(event, snapshot, scores.get("fixture-1"))[0]  # type: ignore[arg-type]
    scored = score_signal(candidate)
    generator = FailingGenerator(Settings(llm_enabled=True, openai_api_key="test-key"))

    generated = asyncio.run(generator.generate(scored))

    assert generated.source == "fallback"
    assert "Argentina implied probability moved" in generated.text


def test_predictiveness_evaluation_confirms_follow_through() -> None:
    session_factory = _session_factory()
    processor = EventProcessor(
        session_factory=session_factory,
        markets=MarketState(),
        scores=ScoreState(),
    )
    start = _dt("2026-07-09T12:00:00+00:00")

    async def run_events() -> None:
        await processor.process_score_event(_score("fixture-4", "match_started", start, 0, 0))
        await processor.process_odds_event(_odds("fixture-4", "Argentina", 0.521, start))
        await processor.process_odds_event(
            _odds("fixture-4", "Argentina", 0.614, start + timedelta(minutes=5))
        )
        await processor.process_odds_event(
            _odds("fixture-4", "Argentina", 0.62, start + timedelta(minutes=10))
        )

    asyncio.run(run_events())

    with session_factory() as db:
        signal = db.query(Signal).filter(Signal.fixture_id == "fixture-4").first()
        assert signal is not None
        evaluation = (
            db.query(SignalEvaluation)
            .filter(SignalEvaluation.signal_id == signal.id)
            .filter(SignalEvaluation.horizon_minutes == 5)
            .first()
        )
        assert evaluation is not None
        assert evaluation.result == "confirmed"


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _odds(
    fixture_id: str,
    outcome: str,
    probability: float,
    ts: datetime,
    bookmaker_id: str = "book-1",
) -> NormalizedOddsEvent:
    return NormalizedOddsEvent(
        source_mode="replay",
        fixture_id=fixture_id,
        message_id=f"{fixture_id}-{ts.isoformat()}-{bookmaker_id}",
        tx_ts=ts,
        bookmaker="DemoBook",
        bookmaker_id=bookmaker_id,
        odds_type="match_winner",
        market_period="full_time",
        outcome_name=outcome,
        implied_probability=probability,
        raw_payload={},
    )


def _score(
    fixture_id: str,
    action: str,
    ts: datetime,
    participant_1_score: int,
    participant_2_score: int,
) -> NormalizedScoreEvent:
    return NormalizedScoreEvent(
        source_mode="replay",
        fixture_id=fixture_id,
        tx_ts=ts,
        action=action,
        participant_1_score=participant_1_score,
        participant_2_score=participant_2_score,
        raw_payload={},
    )


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
