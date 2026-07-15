from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.market.state import MarketSnapshot, ScoreContext

SignalDirection = Literal["up", "down"]
SignalStatus = Literal["new", "alerted", "evaluating", "evaluated"]
ExplanationSource = Literal["template", "llm", "fallback"]
SignalType = Literal[
    "sharp_movement",
    "fast_velocity_movement",
    "no_score_market_pressure",
    "post_event_reaction",
    "bookmaker_divergence",
]


@dataclass(frozen=True)
class SignalCandidate:
    source_mode: str
    fixture_id: str
    market_key: str
    consensus_key: str
    outcome_name: str
    signal_type: SignalType
    direction: SignalDirection
    probability_before: float
    probability_after: float
    delta_probability: float
    window_seconds: int
    tx_start_ts: datetime | None
    tx_end_ts: datetime | None
    snapshot: MarketSnapshot
    score_context: ScoreContext | None = None
    raw_features: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredSignal:
    candidate: SignalCandidate
    confidence_score: float
    magnitude_score: float
    velocity_score: float
    consistency_score: float
    context_score: float
    freshness_score: float
    cleanliness_score: float
    volatility_penalty: float

    @property
    def raw_features(self) -> dict[str, Any]:
        features = dict(self.candidate.raw_features)
        features.update(
            {
                "consistency_score": self.consistency_score,
                "cleanliness_score": self.cleanliness_score,
                "volatility_penalty": self.volatility_penalty,
                "rolling_volatility": self.candidate.snapshot.rolling_volatility,
                "bookmaker_count": self.candidate.snapshot.bookmaker_count,
                "bookmakers_moving_same_direction": (
                    self.candidate.snapshot.bookmakers_moving_same_direction
                ),
                "bookmaker_dispersion": self.candidate.snapshot.bookmaker_dispersion,
                "consensus_probability": self.candidate.snapshot.consensus_probability,
            }
        )
        return features
