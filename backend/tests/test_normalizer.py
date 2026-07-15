from app.ingestion.normalizer import normalize_odds_payload, normalize_score_payload


def test_odds_payload_with_pct_is_normalized() -> None:
    raw = {
        "FixtureId": "fixture-1",
        "MessageId": "msg-1",
        "Ts": "2026-07-09T12:00:00Z",
        "Bookmaker": "DemoBook",
        "PriceNames": ["Team A", "Team B"],
        "Prices": [1.91, 2.1],
        "Pct": [52.1, 47.9],
        "InRunning": True,
    }

    events = normalize_odds_payload(raw, source_mode="snapshot")

    assert len(events) == 2
    assert events[0].fixture_id == "fixture-1"
    assert events[0].outcome_name == "Team A"
    assert events[0].implied_probability == 0.521
    assert events[0].source_mode == "snapshot"


def test_odds_participant_aliases_are_resolved_from_fixture_metadata() -> None:
    raw = {
        "FixtureId": "18209181",
        "fixture": {
            "Participant1": "France",
            "Participant2": "Morocco",
        },
        "PriceNames": ["part1", "draw", "part2"],
        "Prices": [1.8, 4.0, 5.0],
        "Pct": ["55.556", "25.000", "20.000"],
    }

    events = normalize_odds_payload(raw, source_mode="replay")

    assert [event.outcome_name for event in events] == ["France", "Draw", "Morocco"]


def test_odds_payload_with_decimal_price_is_normalized() -> None:
    raw = {
        "FixtureId": "fixture-2",
        "Prices": {"Draw": 2.0},
    }

    events = normalize_odds_payload(raw, source_mode="live")

    assert len(events) == 1
    assert events[0].outcome_name == "Draw"
    assert events[0].price == 2.0
    assert events[0].implied_probability == 0.5


def test_score_payload_is_normalized() -> None:
    raw = {
        "FixtureId": "fixture-3",
        "Seq": 12,
        "Action": "goal",
        "Clock": "12:34",
        "Participant1Score": 1,
        "Participant2Score": 0,
    }

    events = normalize_score_payload(raw, source_mode="replay")

    assert len(events) == 1
    assert events[0].fixture_id == "fixture-3"
    assert events[0].seq == 12
    assert events[0].clock_seconds == 754
    assert events[0].participant_1_score == 1
    assert events[0].participant_2_score == 0


def test_historical_score_payload_with_nested_totals_is_normalized() -> None:
    raw = {
        "fixtureId": 18143850,
        "seq": 42,
        "ts": 1783598400,
        "gameState": "1H",
        "data": {"Action": "goal_brazil", "Clock": {"seconds": 1830}},
        "score": {
            "Participant1": {"Total": {"Score": 1}},
            "Participant2": {"Total": {"Score": 0}},
        },
    }

    events = normalize_score_payload(raw, source_mode="replay")

    assert len(events) == 1
    assert events[0].fixture_id == "18143850"
    assert events[0].seq == 42
    assert events[0].action == "goal_brazil"
    assert events[0].clock_seconds == 1830
    assert events[0].participant_1_score == 1
    assert events[0].participant_2_score == 0


def test_soccer_score_payload_with_goal_totals_is_normalized() -> None:
    raw = {
        "FixtureId": 18209181,
        "Type": "Soccer",
        "Action": "goal",
        "Ts": 1783630178066,
        "Score": {
            "Participant1": {"Total": {"Corners": 3}},
            "Participant2": {"Total": {"Goals": 1, "Corners": 1}},
        },
    }

    events = normalize_score_payload(raw, source_mode="replay")

    assert len(events) == 1
    assert events[0].participant_1_score == 0
    assert events[0].participant_2_score == 1


def test_missing_fields_do_not_crash_normalizer() -> None:
    odds_events = normalize_odds_payload({}, source_mode="synthetic")
    score_events = normalize_score_payload({}, source_mode="synthetic")

    assert len(odds_events) == 1
    assert odds_events[0].fixture_id == "unknown"
    assert len(score_events) == 1
    assert score_events[0].fixture_id == "unknown"
