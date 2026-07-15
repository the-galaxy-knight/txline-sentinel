"""Normalize TxLINE, replay, and snapshot payloads into stable event models.

TxLINE payloads can vary by endpoint and demo scenario, so the normalizer accepts
multiple common key spellings and emits one event per outcome. Downstream signal
logic should depend on these normalized models rather than raw payload shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.market.implied_probability import normalize_probability, probability_from_decimal_odds


class NormalizedOddsEvent(BaseModel):
    """Canonical odds event consumed by storage, market state, and detectors."""

    source_mode: str
    fixture_id: str
    message_id: str | None = None
    tx_ts: datetime | None = None
    bookmaker: str | None = None
    bookmaker_id: str | None = None
    odds_type: str | None = None
    market_period: str | None = None
    market_parameters: str | None = None
    game_state: str | None = None
    in_running: bool | None = None
    outcome_name: str | None = None
    price: float | None = None
    implied_probability: float | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedScoreEvent(BaseModel):
    """Canonical score/event update consumed by score state and streaming APIs."""

    source_mode: str
    fixture_id: str
    tx_ts: datetime | None = None
    seq: int | None = None
    game_state: str | None = None
    action: str | None = None
    clock_seconds: int | None = None
    participant_1_score: int | None = None
    participant_2_score: int | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


def normalize_odds_payload(raw: dict[str, Any], source_mode: str) -> list[NormalizedOddsEvent]:
    """Convert a raw odds payload into normalized outcome-level odds events."""

    events: list[NormalizedOddsEvent] = []
    for payload in _payload_records(raw):
        events.extend(_normalize_single_odds_payload(payload, source_mode))
    return events


def normalize_score_payload(raw: dict[str, Any], source_mode: str) -> list[NormalizedScoreEvent]:
    """Convert a raw score payload into normalized fixture score events."""

    events: list[NormalizedScoreEvent] = []
    for payload in _payload_records(raw):
        fixture_id = _as_str(
            _get(payload, "FixtureId", "fixture_id", "fixtureId", "EventId", "GameId")
        )
        data_payload = _get(payload, "Data", "data")
        data_payload = data_payload if isinstance(data_payload, dict) else {}
        participant_1_score, participant_2_score = _participant_score_totals(payload)
        events.append(
            NormalizedScoreEvent(
                source_mode=source_mode,
                fixture_id=fixture_id or "unknown",
                tx_ts=_parse_datetime(_get(payload, "Ts", "Timestamp", "tx_ts", "timestamp")),
                seq=_as_int(_get(payload, "Seq", "seq")),
                game_state=_as_str(_get(payload, "GameState", "game_state", "Status", "status")),
                action=_as_str(
                    _coalesce(
                        _get(payload, "Action", "action", "Type", "type"),
                        _get(data_payload, "Action", "action", "Type", "type"),
                    )
                ),
                clock_seconds=_parse_clock(
                    _coalesce(
                        _get(payload, "Clock", "clock", "ClockSeconds"),
                        _get(data_payload, "Clock", "clock", "ClockSeconds"),
                    )
                ),
                participant_1_score=participant_1_score,
                participant_2_score=participant_2_score,
                raw_payload=payload,
            )
        )
    return events


def _normalize_single_odds_payload(
    payload: dict[str, Any], source_mode: str
) -> list[NormalizedOddsEvent]:
    fixture_id = _as_str(_get(payload, "FixtureId", "fixture_id", "fixtureId", "EventId", "GameId"))
    outcome_aliases = _outcome_aliases(payload)
    base = {
        "source_mode": source_mode,
        "fixture_id": fixture_id or "unknown",
        "message_id": _as_str(_get(payload, "MessageId", "message_id", "Id", "id")),
        "tx_ts": _parse_datetime(_get(payload, "Ts", "Timestamp", "tx_ts", "timestamp")),
        "bookmaker": _as_str(_get(payload, "Bookmaker", "bookmaker", "BookmakerName")),
        "bookmaker_id": _as_str(_get(payload, "BookmakerId", "bookmaker_id")),
        "odds_type": _as_str(_get(payload, "SuperOddsType", "OddsType", "odds_type")),
        "market_period": _as_str(_get(payload, "MarketPeriod", "Period", "market_period")),
        "market_parameters": _as_str(
            _get(payload, "MarketParameters", "Parameters", "market_parameters")
        ),
        "game_state": _as_str(_get(payload, "GameState", "game_state", "Status", "status")),
        "in_running": _as_bool(_get(payload, "InRunning", "in_running", "IsLive")),
    }

    outcome_rows = _extract_outcome_rows(payload)
    if not outcome_rows:
        outcome_rows = [
            {
                "outcome_name": _as_str(
                    _get(payload, "OutcomeName", "PriceName", "SelectionName", "Name")
                ),
                "price": _get(payload, "Price", "price", "DecimalOdds", "Odds"),
                "pct": _get(payload, "Pct", "pct", "Probability", "ImpliedProbability"),
                "raw_payload": payload,
            }
        ]

    events: list[NormalizedOddsEvent] = []
    for row in outcome_rows:
        price = _as_float(row.get("price"))
        implied_probability = normalize_probability(row.get("pct"))
        if implied_probability is None:
            implied_probability = probability_from_decimal_odds(price)
        raw_payload = row.get("raw_payload")

        events.append(
            NormalizedOddsEvent(
                **base,
                outcome_name=_resolve_outcome_name(
                    _as_str(row.get("outcome_name")),
                    outcome_aliases,
                ),
                price=price,
                implied_probability=implied_probability,
                raw_payload=raw_payload if isinstance(raw_payload, dict) else payload,
            )
        )
    return events


def _extract_outcome_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    price_names = _get(payload, "PriceNames", "price_names", "OutcomeNames")
    prices = _get(payload, "Prices", "prices")
    pct = _get(payload, "Pct", "pct", "Probabilities", "probabilities")

    if isinstance(prices, list):
        rows = []
        for index, price_item in enumerate(prices):
            if isinstance(price_item, dict):
                rows.append(
                    {
                        "outcome_name": _get(
                            price_item, "OutcomeName", "PriceName", "Name", "SelectionName"
                        )
                        or _item_at(price_names, index),
                        "price": _get(price_item, "Price", "price", "DecimalOdds", "Odds")
                        or _get(price_item, "Value", "value"),
                        "pct": _get(price_item, "Pct", "pct", "Probability", "ImpliedProbability")
                        or _item_at(pct, index),
                        "raw_payload": {**payload, "selected_price": price_item},
                    }
                )
            else:
                rows.append(
                    {
                        "outcome_name": _item_at(price_names, index),
                        "price": price_item,
                        "pct": _item_at(pct, index),
                        "raw_payload": payload,
                    }
                )
        return rows

    if isinstance(prices, dict):
        rows = []
        for outcome_name, value in prices.items():
            if isinstance(value, dict):
                rows.append(
                    {
                        "outcome_name": _get(value, "OutcomeName", "PriceName", "Name")
                        or outcome_name,
                        "price": _get(value, "Price", "price", "DecimalOdds", "Odds", "Value")
                        or value.get("value"),
                        "pct": _get(value, "Pct", "pct", "Probability", "ImpliedProbability")
                        or _item_at(pct, outcome_name),
                        "raw_payload": {**payload, "selected_price": value},
                    }
                )
            else:
                rows.append(
                    {
                        "outcome_name": outcome_name,
                        "price": value,
                        "pct": _item_at(pct, outcome_name),
                        "raw_payload": payload,
                    }
                )
        return rows

    if isinstance(price_names, list):
        return [
            {
                "outcome_name": name,
                "price": _item_at(prices, index),
                "pct": _item_at(pct, index),
                "raw_payload": payload,
            }
            for index, name in enumerate(price_names)
        ]

    return []


def _payload_records(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    if _looks_like_event_payload(raw):
        return [raw]

    for key in ("Data", "data", "Items", "items", "Events", "events", "Results", "results"):
        nested = raw.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return _payload_records(nested)
    return [raw]


def _looks_like_event_payload(raw: dict[str, Any]) -> bool:
    event_keys = {
        "fixtureid",
        "fixture_id",
        "eventid",
        "gameid",
        "messageid",
        "prices",
        "pricenames",
        "score",
        "action",
        "seq",
        "ts",
        "timestamp",
    }
    return bool(event_keys & {str(key).lower() for key in raw})


def _get(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    lowered = {str(key).lower(): value for key, value in data.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _participant_score_totals(data: dict[str, Any]) -> tuple[int | None, int | None]:
    participant_1_score = _as_int(
        _coalesce(
            _get(data, "Participant1Score", "participant_1_score", "HomeScore"),
            _score_total(data, "Participant1"),
        )
    )
    participant_2_score = _as_int(
        _coalesce(
            _get(data, "Participant2Score", "participant_2_score", "AwayScore"),
            _score_total(data, "Participant2"),
        )
    )
    score = _get(data, "Score", "score")
    if isinstance(score, dict) and participant_1_score is not None and participant_2_score is None:
        participant_2_score = 0
    if isinstance(score, dict) and participant_2_score is not None and participant_1_score is None:
        participant_1_score = 0
    return participant_1_score, participant_2_score


def _score_total(data: dict[str, Any], participant_key: str) -> Any:
    score = _get(data, "Score", "score")
    if not isinstance(score, dict):
        return None
    participant = _get(score, participant_key, participant_key.lower())
    if not isinstance(participant, dict):
        return None
    total = _get(participant, "Total", "total")
    if isinstance(total, dict):
        return _get(total, "Score", "score", "Goals", "goals")
    return _get(participant, "Score", "score", "Goals", "goals")


def _outcome_aliases(payload: dict[str, Any]) -> dict[str, str]:
    participant_1 = _participant_name(payload, 1)
    participant_2 = _participant_name(payload, 2)
    aliases = {"draw": "Draw", "tie": "Draw"}
    if participant_1:
        aliases.update(
            {"part1": participant_1, "participant1": participant_1, "home": participant_1}
        )
    if participant_2:
        aliases.update(
            {"part2": participant_2, "participant2": participant_2, "away": participant_2}
        )
    return aliases


def _participant_name(payload: dict[str, Any], participant_number: int) -> str | None:
    keys = (
        (
            f"Participant{participant_number}",
            f"participant{participant_number}",
            f"participant_{participant_number}",
        )
        if participant_number in {1, 2}
        else ()
    )
    for container in _fixture_metadata_containers(payload):
        value = _as_str(_get(container, *keys))
        if value:
            return value
    return None


def _fixture_metadata_containers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    containers = [payload]
    for key in ("Fixture", "fixture", "fixture_metadata", "metadata"):
        nested = _get(payload, key)
        if isinstance(nested, dict):
            containers.append(nested)
    return containers


def _resolve_outcome_name(value: str | None, aliases: dict[str, str]) -> str | None:
    if value is None:
        return None
    return aliases.get(value.strip().lower(), value)


def _item_at(value: Any, key: int | str) -> Any:
    if isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
        return value[key]
    if isinstance(value, dict):
        return value.get(key) or value.get(str(key))
    if isinstance(key, int) and key == 0:
        return value
    return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, int | float):
        return bool(value)
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return _parse_datetime(int(text))
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_clock(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _as_int(_get(value, "Seconds", "seconds", "ClockSeconds", "clock_seconds"))
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
        parts = text.split(":")
        if all(part.isdigit() for part in parts):
            numbers = [int(part) for part in parts]
            if len(numbers) == 2:
                return numbers[0] * 60 + numbers[1]
            if len(numbers) == 3:
                return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    return None
