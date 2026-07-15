from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_probability(value: Any) -> float | None:
    number = _to_float(value)
    if number is None or number < 0:
        return None
    if number <= 1:
        return number
    if number <= 100:
        return number / 100
    return None


def probability_from_decimal_odds(price: Any) -> float | None:
    number = _to_float(price)
    if number is None or number <= 0:
        return None
    probability = 1 / number
    return probability if 0 <= probability <= 1 else None
