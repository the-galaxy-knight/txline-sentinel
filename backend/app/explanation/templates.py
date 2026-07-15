from __future__ import annotations

from app.signals.models import ScoredSignal

SIGNAL_LABELS = {
    "sharp_movement": "sharp movement",
    "fast_velocity_movement": "fast velocity movement",
    "no_score_market_pressure": "sharp no-score movement",
    "post_event_reaction": "post-event reaction",
    "bookmaker_divergence": "bookmaker divergence",
}


def template_explanation(scored: ScoredSignal) -> str:
    candidate = scored.candidate
    score = candidate.score_context.score_label() if candidate.score_context else "unknown"
    before = _percent(candidate.probability_before)
    after = _percent(candidate.probability_after)
    window = _window_label(candidate.window_seconds)
    label = SIGNAL_LABELS.get(candidate.signal_type, candidate.signal_type.replace("_", " "))
    context_phrase = _context_phrase(candidate.signal_type, score)
    return (
        f"{candidate.outcome_name} implied probability moved from {before} to {after} "
        f"over {window} while the score was {score}. This {label} {context_phrase}. "
        "Follow-through will be checked after 5, 10, and 15 minutes."
    )


def _context_phrase(signal_type: str, score: str) -> str:
    if signal_type == "no_score_market_pressure":
        return "may indicate sustained market pressure without a visible scoring event"
    if signal_type == "post_event_reaction":
        return "may indicate the market is repricing after a recent match event"
    if signal_type == "bookmaker_divergence":
        return "may indicate one bookmaker has moved away from current consensus"
    return "may indicate sustained market pressure"


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _window_label(seconds: int) -> str:
    if seconds <= 0:
        return "the current consensus check"
    minutes = seconds / 60
    if minutes.is_integer():
        return f"{int(minutes)} minutes"
    return f"{minutes:.1f} minutes"
