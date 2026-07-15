from app.market.implied_probability import normalize_probability, probability_from_decimal_odds


def test_normalize_probability_percent_number() -> None:
    assert normalize_probability(52.1) == 0.521


def test_normalize_probability_percent_string() -> None:
    assert normalize_probability("52.1") == 0.521


def test_normalize_probability_decimal_number() -> None:
    assert normalize_probability(0.521) == 0.521


def test_normalize_probability_decimal_string() -> None:
    assert normalize_probability("0.521") == 0.521


def test_probability_from_decimal_odds() -> None:
    assert probability_from_decimal_odds(2.0) == 0.5


def test_invalid_values_return_none() -> None:
    assert normalize_probability("not-a-number") is None
    assert normalize_probability(-1) is None
    assert probability_from_decimal_odds(0) is None
    assert probability_from_decimal_odds("bad") is None
