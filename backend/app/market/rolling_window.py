"""Bounded rolling probability windows used by the signal engine.

The market state layer keeps one window per market/outcome and prunes points to
the last 15 minutes. These helpers intentionally stay storage-free so replay,
snapshot, and live ingestion can share the same in-memory calculations.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import pstdev


@dataclass(frozen=True)
class ProbabilityPoint:
    """A single implied-probability observation at a TxLINE event timestamp."""

    ts: datetime
    probability: float
    bookmaker_id: str | None = None


class RollingProbabilityWindow:
    """Maintain recent probability observations and derived movement features."""

    def __init__(self, max_age_seconds: int = 900) -> None:
        self.max_age = timedelta(seconds=max_age_seconds)
        self.points: deque[ProbabilityPoint] = deque()

    def add(self, point: ProbabilityPoint) -> None:
        self.points.append(point)
        self.prune(point.ts)

    def clear(self) -> None:
        self.points.clear()

    def latest(self) -> ProbabilityPoint | None:
        return self.points[-1] if self.points else None

    def probability_seconds_ago(self, now: datetime, seconds: int) -> float | None:
        """Return the latest probability at or before the requested lookback."""

        if not self.points:
            return None
        target = now - timedelta(seconds=seconds)
        selected: ProbabilityPoint | None = None
        for point in self.points:
            if point.ts <= target:
                selected = point
            else:
                break
        return selected.probability if selected else None

    def volatility(self) -> float:
        """Return population standard deviation of adjacent probability changes."""

        if len(self.points) < 3:
            return 0.0
        deltas = [
            self.points[index].probability - self.points[index - 1].probability
            for index in range(1, len(self.points))
        ]
        return pstdev(deltas) if len(deltas) > 1 else 0.0

    def max_excursions(self, start_ts: datetime, base_probability: float) -> tuple[float, float]:
        """Return max favorable and adverse raw deltas since `start_ts`."""

        favorable = 0.0
        adverse = 0.0
        for point in self.points:
            if point.ts < start_ts:
                continue
            delta = point.probability - base_probability
            favorable = max(favorable, delta)
            adverse = min(adverse, delta)
        return favorable, adverse

    def prune(self, now: datetime) -> None:
        cutoff = now - self.max_age
        while self.points and self.points[0].ts < cutoff:
            self.points.popleft()
