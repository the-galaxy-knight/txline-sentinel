"""In-memory market and score context state for deterministic detection.

Market state converts normalized odds events into rolling snapshots keyed by
bookmaker and consensus market identity. Score state keeps lightweight fixture
context so movement detection can distinguish no-score pressure from reactions
after goals or cards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.ingestion.normalizer import NormalizedOddsEvent, NormalizedScoreEvent
from app.market.rolling_window import ProbabilityPoint, RollingProbabilityWindow


def market_key_for_event(event: NormalizedOddsEvent) -> str:
    """Build the bookmaker-specific market/outcome key for an odds event."""

    return "|".join(
        [
            event.fixture_id,
            event.bookmaker_id or event.bookmaker or "unknown_bookmaker",
            event.odds_type or "unknown_market",
            event.market_period or "full_time",
            event.market_parameters or "",
            event.outcome_name or "unknown_outcome",
        ]
    )


def consensus_key_for_event(event: NormalizedOddsEvent) -> str:
    """Build the consensus market/outcome key, excluding bookmaker identity."""

    return "|".join(
        [
            event.fixture_id,
            event.odds_type or "unknown_market",
            event.market_period or "full_time",
            event.market_parameters or "",
            event.outcome_name or "unknown_outcome",
        ]
    )


@dataclass
class MarketSnapshot:
    """Derived rolling market features for one bookmaker market/outcome."""

    market_key: str
    consensus_key: str
    fixture_id: str
    outcome_name: str | None
    p_now: float | None
    p_60s_ago: float | None
    p_180s_ago: float | None
    p_300s_ago: float | None
    p_600s_ago: float | None
    delta_60s: float | None
    delta_180s: float | None
    delta_300s: float | None
    delta_600s: float | None
    velocity_60s: float | None
    rolling_volatility: float
    bookmaker_count: int
    bookmakers_moving_same_direction: int
    bookmaker_dispersion: float
    consensus_probability: float | None
    bookmaker_probability_deviation_from_consensus: float | None
    event_ts: datetime
    raw: dict[str, Any] = field(default_factory=dict)


class MarketState:
    """Track rolling odds windows and consensus features for active markets."""

    def __init__(self, max_age_seconds: int = 900) -> None:
        self.max_age_seconds = max_age_seconds
        self.windows: dict[str, RollingProbabilityWindow] = {}
        self.market_to_consensus: dict[str, str] = {}
        self.market_metadata: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self.windows.clear()
        self.market_to_consensus.clear()
        self.market_metadata.clear()

    def update_odds(self, event: NormalizedOddsEvent) -> MarketSnapshot | None:
        """Add an odds event and return the updated snapshot for its market."""

        if event.implied_probability is None:
            return None
        event_ts = event.tx_ts or datetime.now(UTC)
        market_key = market_key_for_event(event)
        consensus_key = consensus_key_for_event(event)
        window = self.windows.setdefault(market_key, RollingProbabilityWindow(self.max_age_seconds))
        window.add(
            ProbabilityPoint(
                ts=event_ts,
                probability=event.implied_probability,
                bookmaker_id=event.bookmaker_id or event.bookmaker,
            )
        )
        self.market_to_consensus[market_key] = consensus_key
        self.market_metadata[market_key] = {
            "fixture_id": event.fixture_id,
            "outcome_name": event.outcome_name,
            "bookmaker_id": event.bookmaker_id,
            "bookmaker": event.bookmaker,
            "odds_type": event.odds_type,
            "market_period": event.market_period,
            "market_parameters": event.market_parameters,
            "game_state": event.game_state,
            "in_running": event.in_running,
        }
        return self.snapshot_for_market(market_key, event_ts)

    def snapshot_for_market(
        self, market_key: str, now: datetime | None = None
    ) -> MarketSnapshot | None:
        window = self.windows.get(market_key)
        if not window:
            return None
        latest = window.latest()
        if latest is None:
            return None
        now = now or latest.ts
        base = self._base_snapshot(market_key, now)
        if base is None:
            return None

        consensus_key = self.market_to_consensus.get(market_key, base.consensus_key)
        group_snapshots = [
            snapshot
            for key, key_consensus in self.market_to_consensus.items()
            if key_consensus == consensus_key
            for snapshot in [self._base_snapshot(key, now)]
            if snapshot and snapshot.p_now is not None
        ]
        probabilities = [
            snapshot.p_now for snapshot in group_snapshots if snapshot.p_now is not None
        ]
        consensus_probability = sum(probabilities) / len(probabilities) if probabilities else None
        dispersion = (
            max(abs(probability - consensus_probability) for probability in probabilities)
            if consensus_probability is not None and probabilities
            else 0.0
        )
        current_delta = base.delta_300s or base.delta_60s or 0.0
        direction = 1 if current_delta >= 0 else -1
        same_direction = sum(
            1
            for snapshot in group_snapshots
            if ((snapshot.delta_300s or snapshot.delta_60s or 0.0) * direction) > 0
        )
        deviation = (
            base.p_now - consensus_probability
            if base.p_now is not None and consensus_probability is not None
            else None
        )

        base.bookmaker_count = len(probabilities)
        base.bookmakers_moving_same_direction = same_direction
        base.bookmaker_dispersion = dispersion
        base.consensus_probability = consensus_probability
        base.bookmaker_probability_deviation_from_consensus = deviation
        return base

    def snapshots_for_fixture(self, fixture_id: str) -> list[MarketSnapshot]:
        """Return latest market snapshots known for a fixture."""

        snapshots = []
        for market_key, metadata in self.market_metadata.items():
            if metadata.get("fixture_id") != fixture_id:
                continue
            snapshot = self.snapshot_for_market(market_key)
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

    def max_excursions(
        self, market_key: str, start_ts: datetime, base_probability: float, direction: str
    ) -> tuple[float, float]:
        window = self.windows.get(market_key)
        if not window:
            return 0.0, 0.0
        favorable, adverse = window.max_excursions(start_ts, base_probability)
        if direction == "down":
            return abs(adverse), abs(favorable)
        return favorable, abs(adverse)

    def _base_snapshot(self, market_key: str, now: datetime) -> MarketSnapshot | None:
        window = self.windows.get(market_key)
        latest = window.latest() if window else None
        if not window or latest is None:
            return None
        metadata = self.market_metadata.get(market_key, {})
        p_now = latest.probability
        p_60 = window.probability_seconds_ago(now, 60)
        p_180 = window.probability_seconds_ago(now, 180)
        p_300 = window.probability_seconds_ago(now, 300)
        p_600 = window.probability_seconds_ago(now, 600)
        delta_60 = _delta(p_now, p_60)
        return MarketSnapshot(
            market_key=market_key,
            consensus_key=self.market_to_consensus.get(market_key, market_key),
            fixture_id=str(metadata.get("fixture_id") or market_key.split("|", 1)[0]),
            outcome_name=metadata.get("outcome_name"),
            p_now=p_now,
            p_60s_ago=p_60,
            p_180s_ago=p_180,
            p_300s_ago=p_300,
            p_600s_ago=p_600,
            delta_60s=delta_60,
            delta_180s=_delta(p_now, p_180),
            delta_300s=_delta(p_now, p_300),
            delta_600s=_delta(p_now, p_600),
            velocity_60s=delta_60 / 60 if delta_60 is not None else None,
            rolling_volatility=window.volatility(),
            bookmaker_count=1,
            bookmakers_moving_same_direction=1 if delta_60 else 0,
            bookmaker_dispersion=0.0,
            consensus_probability=p_now,
            bookmaker_probability_deviation_from_consensus=0.0,
            event_ts=now,
            raw=metadata,
        )


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


@dataclass
class ScoreContext:
    """Latest score and major-event context for a fixture."""

    fixture_id: str
    participant_1_score: int | None = None
    participant_2_score: int | None = None
    game_state: str | None = None
    clock_seconds: int | None = None
    last_event_ts: datetime | None = None
    last_action: str | None = None
    last_goal_like_ts: datetime | None = None
    last_goal_like_action: str | None = None
    last_card_like_ts: datetime | None = None
    last_card_like_action: str | None = None
    last_major_event_ts: datetime | None = None
    last_major_event_action: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def recent_goal_like(self, now: datetime, seconds: int = 120) -> bool:
        return _is_recent(self.last_goal_like_ts, now, seconds)

    def recent_card_like(self, now: datetime, seconds: int = 120) -> bool:
        return _is_recent(self.last_card_like_ts, now, seconds)

    def score_label(self) -> str:
        if self.participant_1_score is None or self.participant_2_score is None:
            pre_match_states = {"scheduled", "pre_match", "prematch"}
            if self.game_state and self.game_state.lower() in pre_match_states:
                return "pre-match"
            return "unknown"
        return f"{self.participant_1_score}-{self.participant_2_score}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "participant_1_score": self.participant_1_score,
            "participant_2_score": self.participant_2_score,
            "game_state": self.game_state,
            "clock_seconds": self.clock_seconds,
            "last_action": self.last_action,
            "last_goal_like_action": self.last_goal_like_action,
            "last_card_like_action": self.last_card_like_action,
            "last_major_event_action": self.last_major_event_action,
        }


class ScoreState:
    """Maintain the latest score context per fixture."""

    def __init__(self) -> None:
        self.fixtures: dict[str, ScoreContext] = {}

    def clear(self) -> None:
        self.fixtures.clear()

    def update_score(self, event: NormalizedScoreEvent) -> ScoreContext:
        """Apply a normalized score event using defensive action classification."""

        event_ts = event.tx_ts or datetime.now(UTC)
        context = self.fixtures.setdefault(event.fixture_id, ScoreContext(event.fixture_id))
        if event.participant_1_score is not None:
            context.participant_1_score = event.participant_1_score
        if event.participant_2_score is not None:
            context.participant_2_score = event.participant_2_score
        if _should_initialize_zero_score(event, context):
            context.participant_1_score = 0
            context.participant_2_score = 0
        if event.game_state is not None:
            context.game_state = event.game_state
        if event.clock_seconds is not None:
            context.clock_seconds = event.clock_seconds
        context.last_event_ts = event_ts
        context.last_action = event.action
        context.raw_payload = event.raw_payload

        action = (event.action or "").lower()
        if _is_goal_like_action(action):
            context.last_goal_like_ts = event_ts
            context.last_goal_like_action = event.action
            context.last_major_event_ts = event_ts
            context.last_major_event_action = event.action
        elif _is_card_like_action(action):
            context.last_card_like_ts = event_ts
            context.last_card_like_action = event.action
            context.last_major_event_ts = event_ts
            context.last_major_event_action = event.action
        return context

    def get(self, fixture_id: str) -> ScoreContext | None:
        return self.fixtures.get(fixture_id)


def _is_recent(ts: datetime | None, now: datetime, seconds: int) -> bool:
    if ts is None:
        return False
    return 0 <= (now - ts).total_seconds() <= seconds


def _should_initialize_zero_score(
    event: NormalizedScoreEvent,
    context: ScoreContext,
) -> bool:
    if context.participant_1_score is not None or context.participant_2_score is not None:
        return False
    if event.participant_1_score is not None or event.participant_2_score is not None:
        return False
    raw_type = str(event.raw_payload.get("Type") or event.raw_payload.get("type") or "").lower()
    sport_id = str(event.raw_payload.get("SportId") or event.raw_payload.get("sportId") or "")
    return raw_type == "soccer" or sport_id == "1"


def _is_goal_like_action(action: str) -> bool:
    normalized = action.replace("-", "_").replace(" ", "_")
    if normalized in {"goal_kick", "goalkeeper_save"}:
        return False
    if normalized.startswith("goal_"):
        return True
    return normalized in {
        "goal",
        "penalty_goal",
        "own_goal",
        "disallowed_goal",
        "var_goal",
    } or normalized.endswith("_goal")


def _is_card_like_action(action: str) -> bool:
    normalized = action.replace("-", "_").replace(" ", "_")
    return "card" in normalized or normalized in {"red", "yellow"}


market_state = MarketState()
score_state = ScoreState()
