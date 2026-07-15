"""Deterministic signal detection rules.

The detector is the only component that decides whether a signal candidate
exists. Explanations and alerts consume its structured facts; they do not change
signal type, direction, thresholds, or confidence inputs.
"""

from __future__ import annotations

from app.ingestion.normalizer import NormalizedOddsEvent
from app.market.state import MarketSnapshot, ScoreContext
from app.signals.models import SignalCandidate, SignalDirection, SignalType


class SignalDetector:
    """Evaluate rolling market snapshots against v1 signal thresholds."""

    def detect(
        self,
        event: NormalizedOddsEvent,
        snapshot: MarketSnapshot,
        score_context: ScoreContext | None,
    ) -> list[SignalCandidate]:
        """Return all signal candidates triggered by the latest odds event."""

        if snapshot.p_now is None or not event.outcome_name:
            return []

        candidates: list[SignalCandidate] = []
        candidates.extend(self._movement_candidates(event, snapshot, score_context))
        divergence = self._bookmaker_divergence(event, snapshot, score_context)
        if divergence:
            candidates.append(divergence)
        return candidates

    def _movement_candidates(
        self,
        event: NormalizedOddsEvent,
        snapshot: MarketSnapshot,
        score_context: ScoreContext | None,
    ) -> list[SignalCandidate]:
        candidates: list[SignalCandidate] = []
        delta_300 = snapshot.delta_300s or 0.0
        delta_180 = snapshot.delta_180s or 0.0
        delta_60 = snapshot.delta_60s or 0.0
        z_score_delta = self._z_score_delta(snapshot)

        if abs(delta_300) >= 0.05 and snapshot.p_300s_ago is not None:
            candidates.append(
                self._candidate(
                    "sharp_movement",
                    event,
                    snapshot,
                    score_context,
                    snapshot.p_300s_ago,
                    snapshot.p_now,
                    300,
                )
            )

        if (abs(delta_60) >= 0.025 or z_score_delta >= 3.0) and snapshot.p_60s_ago is not None:
            candidates.append(
                self._candidate(
                    "fast_velocity_movement",
                    event,
                    snapshot,
                    score_context,
                    snapshot.p_60s_ago,
                    snapshot.p_now,
                    60,
                    {"z_score_delta": z_score_delta},
                )
            )

        no_recent_goal = not (
            score_context and score_context.recent_goal_like(snapshot.event_ts, seconds=120)
        )
        if abs(delta_300) >= 0.04 and no_recent_goal and snapshot.p_300s_ago is not None:
            candidates.append(
                self._candidate(
                    "no_score_market_pressure",
                    event,
                    snapshot,
                    score_context,
                    snapshot.p_300s_ago,
                    snapshot.p_now,
                    300,
                )
            )

        recent_major_event = bool(
            score_context
            and (
                score_context.recent_goal_like(snapshot.event_ts, seconds=120)
                or score_context.recent_card_like(snapshot.event_ts, seconds=120)
            )
        )
        if recent_major_event and abs(delta_180) >= 0.03 and snapshot.p_180s_ago is not None:
            candidates.append(
                self._candidate(
                    "post_event_reaction",
                    event,
                    snapshot,
                    score_context,
                    snapshot.p_180s_ago,
                    snapshot.p_now,
                    180,
                )
            )
        return candidates

    def _bookmaker_divergence(
        self,
        event: NormalizedOddsEvent,
        snapshot: MarketSnapshot,
        score_context: ScoreContext | None,
    ) -> SignalCandidate | None:
        deviation = snapshot.bookmaker_probability_deviation_from_consensus
        if snapshot.bookmaker_count < 2 or deviation is None or abs(deviation) < 0.035:
            return None
        return self._candidate(
            "bookmaker_divergence",
            event,
            snapshot,
            score_context,
            snapshot.consensus_probability,
            snapshot.p_now,
            0,
            {"bookmaker_deviation_from_consensus": deviation},
        )

    @staticmethod
    def _candidate(
        signal_type: SignalType,
        event: NormalizedOddsEvent,
        snapshot: MarketSnapshot,
        score_context: ScoreContext | None,
        probability_before: float | None,
        probability_after: float | None,
        window_seconds: int,
        raw_features: dict | None = None,
    ) -> SignalCandidate:
        before = probability_before if probability_before is not None else probability_after or 0.0
        after = probability_after if probability_after is not None else before
        delta = after - before
        direction: SignalDirection = "up" if delta >= 0 else "down"
        return SignalCandidate(
            source_mode=event.source_mode,
            fixture_id=event.fixture_id,
            market_key=snapshot.market_key,
            consensus_key=snapshot.consensus_key,
            outcome_name=event.outcome_name or snapshot.outcome_name or "unknown",
            signal_type=signal_type,
            direction=direction,
            probability_before=before,
            probability_after=after,
            delta_probability=delta,
            window_seconds=window_seconds,
            tx_start_ts=event.tx_ts,
            tx_end_ts=event.tx_ts,
            snapshot=snapshot,
            score_context=score_context,
            raw_features=raw_features or {},
        )

    @staticmethod
    def _z_score_delta(snapshot: MarketSnapshot) -> float:
        if snapshot.delta_60s is None or snapshot.rolling_volatility <= 0.001:
            return 0.0
        return abs(snapshot.delta_60s) / snapshot.rolling_volatility
