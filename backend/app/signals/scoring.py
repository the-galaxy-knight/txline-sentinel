"""Confidence scoring for deterministic signal candidates."""

from __future__ import annotations

from app.signals.models import ScoredSignal, SignalCandidate


def score_signal(candidate: SignalCandidate) -> ScoredSignal:
    """Score a signal candidate on a 0-100 confidence scale.

    The score combines magnitude, velocity, bookmaker consistency, context,
    freshness, data cleanliness, and a high-volatility penalty.
    """

    snapshot = candidate.snapshot
    delta_300 = snapshot.delta_300s
    if candidate.signal_type == "bookmaker_divergence":
        delta_300 = candidate.delta_probability
    magnitude_score = min(abs(delta_300 or candidate.delta_probability) / 0.08, 1.0)
    velocity_score = min(abs(snapshot.delta_60s or candidate.delta_probability) / 0.04, 1.0)
    consistency_score = _consistency_score(candidate)
    context_score = _context_score(candidate)
    freshness_score = 1.0
    cleanliness_score = _cleanliness_score(candidate)
    volatility_penalty = min(max((snapshot.rolling_volatility - 0.03) / 0.07, 0.0), 1.0) * 15

    confidence = (
        25 * magnitude_score
        + 20 * velocity_score
        + 20 * consistency_score
        + 15 * context_score
        + 10 * freshness_score
        + 10 * cleanliness_score
        - volatility_penalty
    )
    confidence = max(0.0, min(100.0, confidence))

    return ScoredSignal(
        candidate=candidate,
        confidence_score=round(confidence, 2),
        magnitude_score=round(magnitude_score, 4),
        velocity_score=round(velocity_score, 4),
        consistency_score=round(consistency_score, 4),
        context_score=round(context_score, 4),
        freshness_score=freshness_score,
        cleanliness_score=round(cleanliness_score, 4),
        volatility_penalty=round(volatility_penalty, 4),
    )


def _consistency_score(candidate: SignalCandidate) -> float:
    snapshot = candidate.snapshot
    if snapshot.bookmaker_count <= 1:
        return 0.6
    return min(snapshot.bookmakers_moving_same_direction / snapshot.bookmaker_count, 1.0)


def _context_score(candidate: SignalCandidate) -> float:
    if candidate.signal_type == "post_event_reaction":
        return 1.0
    if candidate.signal_type == "no_score_market_pressure":
        return 0.85
    if candidate.signal_type == "sharp_movement":
        return 0.65
    if candidate.signal_type == "bookmaker_divergence":
        return 0.45
    return 0.5


def _cleanliness_score(candidate: SignalCandidate) -> float:
    checks = [
        bool(candidate.fixture_id and candidate.fixture_id != "unknown"),
        bool(candidate.outcome_name and candidate.outcome_name != "unknown"),
        candidate.probability_after is not None,
        candidate.tx_end_ts is not None,
    ]
    return sum(1 for check in checks if check) / len(checks)
