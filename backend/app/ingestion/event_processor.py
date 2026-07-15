"""Central ingestion pipeline shared by live, snapshot, and replay modes.

The processor persists normalized events, updates in-memory state, runs the
deterministic signal engine, creates evaluations, publishes dashboard events,
and dispatches optional alerts. Keeping those side effects here ensures replay
exercises the same backend path as real ingestion.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.alerts.dispatcher import AlertDispatcher
from app.db import SessionLocal, Signal
from app.explanation.generator import ExplanationGenerator
from app.ingestion.dashboard_stream import dashboard_broker
from app.ingestion.normalizer import (
    NormalizedOddsEvent,
    NormalizedScoreEvent,
    normalize_odds_payload,
    normalize_score_payload,
)
from app.market.state import MarketState, ScoreState, market_state, score_state
from app.repositories.events_repo import create_odds_events, create_score_events
from app.signals.deduplication import SignalDeduplicator
from app.signals.detector import SignalDetector
from app.signals.evaluator import create_pending_evaluations, evaluate_pending_for_event
from app.signals.models import ScoredSignal
from app.signals.scoring import score_signal

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Counts and identifiers produced while processing one or more events."""

    odds_events_processed: int = 0
    score_events_processed: int = 0
    signals_created: list[int] = field(default_factory=list)
    evaluations_updated: list[int] = field(default_factory=list)


class EventProcessor:
    """Coordinate storage, state updates, signal generation, and fanout."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        markets: MarketState = market_state,
        scores: ScoreState = score_state,
        detector: SignalDetector | None = None,
        deduplicator: SignalDeduplicator | None = None,
        explanation_generator: ExplanationGenerator | None = None,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.market_state = markets
        self.score_state = scores
        self.detector = detector or SignalDetector()
        self.deduplicator = deduplicator or SignalDeduplicator()
        self.explanation_generator = explanation_generator or ExplanationGenerator()
        self.alert_dispatcher = alert_dispatcher or AlertDispatcher(
            session_factory=session_factory
        )

    def clear_state(self) -> None:
        self.market_state.clear()
        self.score_state.clear()
        self.deduplicator.clear()

    async def process_raw_odds_payload(self, raw: dict, source_mode: str) -> ProcessingResult:
        return await self.process_odds_events(normalize_odds_payload(raw, source_mode))

    async def process_raw_score_payload(self, raw: dict, source_mode: str) -> ProcessingResult:
        return await self.process_score_events(normalize_score_payload(raw, source_mode))

    async def process_odds_events(
        self, events: list[NormalizedOddsEvent]
    ) -> ProcessingResult:
        result = ProcessingResult()
        for event in events:
            single = await self.process_odds_event(event)
            result.odds_events_processed += single.odds_events_processed
            result.signals_created.extend(single.signals_created)
            result.evaluations_updated.extend(single.evaluations_updated)
        return result

    async def process_score_events(
        self, events: list[NormalizedScoreEvent]
    ) -> ProcessingResult:
        result = ProcessingResult()
        for event in events:
            single = await self.process_score_event(event)
            result.score_events_processed += single.score_events_processed
        return result

    async def process_score_event(self, event: NormalizedScoreEvent) -> ProcessingResult:
        """Persist and publish a single normalized score event."""

        with self.session_factory() as db:
            rows = create_score_events(db, [event])
            if not rows:
                db.commit()
                return ProcessingResult()
            db.commit()
        context = self.score_state.update_score(event)
        await dashboard_broker.publish("score_processed", context.to_dict())
        return ProcessingResult(score_events_processed=1)

    async def process_odds_event(self, event: NormalizedOddsEvent) -> ProcessingResult:
        """Persist one odds event and run the full signal pipeline for it."""

        result = ProcessingResult(odds_events_processed=1)
        created_signal_ids: list[int] = []
        updated_evaluation_ids: list[int] = []

        with self.session_factory() as db:
            rows = create_odds_events(db, [event])
            if not rows:
                db.commit()
                return ProcessingResult()
            snapshot = self.market_state.update_odds(event)
            updated_evaluations = evaluate_pending_for_event(db, event, self.market_state)
            updated_evaluation_ids = [evaluation.id for evaluation in updated_evaluations]

            if snapshot:
                score_context = self.score_state.get(event.fixture_id)
                candidates = self.detector.detect(event, snapshot, score_context)
                for candidate in candidates:
                    scored = score_signal(candidate)
                    if not self.deduplicator.should_emit(db, scored):
                        continue
                    generated = await self.explanation_generator.generate(scored)
                    signal = self._build_signal(scored, generated.text, generated.source)
                    db.add(signal)
                    db.flush()
                    create_pending_evaluations(db, signal)
                    db.flush()
                    self.deduplicator.remember(scored)
                    created_signal_ids.append(signal.id)

            db.commit()

        await dashboard_broker.publish(
            "odds_processed",
            {
                "fixture_id": event.fixture_id,
                "outcome_name": event.outcome_name,
                "implied_probability": event.implied_probability,
                "source_mode": event.source_mode,
            },
        )

        for evaluation_id in updated_evaluation_ids:
            await dashboard_broker.publish(
                "signal_evaluation_updated", {"evaluation_id": evaluation_id}
            )
        for signal_id in created_signal_ids:
            await dashboard_broker.publish("signal_created", {"signal_id": signal_id})
            await self.alert_dispatcher.dispatch_signal(signal_id)

        result.signals_created = created_signal_ids
        result.evaluations_updated = updated_evaluation_ids
        return result

    @staticmethod
    def _build_signal(
        scored: ScoredSignal,
        explanation: str,
        explanation_source: str,
    ) -> Signal:
        candidate = scored.candidate
        return Signal(
            source_mode=candidate.source_mode,
            fixture_id=candidate.fixture_id,
            market_key=candidate.market_key,
            outcome_name=candidate.outcome_name,
            signal_type=candidate.signal_type,
            direction=candidate.direction,
            probability_before=candidate.probability_before,
            probability_after=candidate.probability_after,
            delta_probability=candidate.delta_probability,
            window_seconds=candidate.window_seconds,
            confidence_score=scored.confidence_score,
            magnitude_score=scored.magnitude_score,
            velocity_score=scored.velocity_score,
            volatility_score=max(0.0, 1.0 - scored.volatility_penalty / 15),
            freshness_score=scored.freshness_score,
            context_score=scored.context_score,
            trade_relevance_score=scored.consistency_score,
            score_context=candidate.score_context.to_dict() if candidate.score_context else None,
            explanation=explanation,
            explanation_source=explanation_source,
            status="new",
            tx_start_ts=candidate.tx_start_ts,
            tx_end_ts=candidate.tx_end_ts,
            raw_features=scored.raw_features,
        )


event_processor = EventProcessor()
