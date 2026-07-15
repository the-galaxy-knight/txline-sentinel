from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.alerts.dispatcher import AlertDispatcher
from app.config import Settings
from app.db import Base, OddsEvent, ScoreEvent
from app.ingestion.event_processor import EventProcessor
from app.ingestion.live_runner import LiveRunner
from app.ingestion.normalizer import NormalizedOddsEvent, NormalizedScoreEvent
from app.ingestion.snapshot_runner import SnapshotRunner
from app.market.state import MarketState, ScoreState


def test_runtime_settings_endpoint() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["txline_configured"], bool)
    assert payload["database"] == "sqlite"
    assert payload["replay_scenarios_count"] >= 3
    assert set(payload["live_streams"]) >= {"odds", "scores"}
    assert {"state", "last_event_id", "last_event_at", "events_received"} <= set(
        payload["live_streams"]["odds"]
    )


def test_replay_start_status_and_signal_filtering() -> None:
    from app.main import app

    with TestClient(app) as client:
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
        response = client.post(
            "/api/replay/start",
            json={
                "scenario_name": "argentina_france_no_score_sharp_move",
                "speed_multiplier": 1_000_000,
                "reset_database": True,
            },
        )
        assert response.status_code == 200
        status = _wait_for_replay(client)
        assert status["status"] in {"running", "completed"}

        signals = client.get("/api/signals", params={"signal_type": "sharp_movement"}).json()
        high_confidence = client.get("/api/signals/high-confidence").json()
        latest = client.get("/api/signals/latest").json()

    assert any(signal["signal_type"] == "sharp_movement" for signal in signals)
    assert any(signal["confidence_score"] >= 80 for signal in high_confidence)
    assert latest


def test_match_state_endpoint() -> None:
    from app.main import app

    with TestClient(app) as client:
        client.post(
            "/api/replay/start",
            json={
                "scenario_name": "argentina_france_no_score_sharp_move",
                "speed_multiplier": 1_000_000,
                "reset_database": True,
            },
        )
        _wait_for_replay(client)
        response = client.get("/api/matches/demo-arg-fra-001/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture_id"] == "demo-arg-fra-001"
    assert payload["latest_odds"]
    assert payload["latest_signals"]


def test_event_idempotency_skips_duplicate_odds_and_scores() -> None:
    session_factory = _session_factory()
    processor = EventProcessor(
        session_factory=session_factory,
        markets=MarketState(),
        scores=ScoreState(),
    )
    odds = NormalizedOddsEvent(
        source_mode="replay",
        fixture_id="fixture-idempotent",
        message_id="duplicate-message",
        outcome_name="Argentina",
        odds_type="match_winner",
        implied_probability=0.5,
        raw_payload={},
    )
    score = NormalizedScoreEvent(
        source_mode="replay",
        fixture_id="fixture-idempotent",
        seq=1,
        action="match_started",
        raw_payload={},
    )

    async def run() -> None:
        await processor.process_odds_event(odds)
        await processor.process_odds_event(odds)
        await processor.process_score_event(score)
        await processor.process_score_event(score)

    asyncio.run(run())

    with session_factory() as db:
        assert db.query(OddsEvent).count() == 1
        assert db.query(ScoreEvent).count() == 1


def test_telegram_disabled_noops() -> None:
    dispatcher = AlertDispatcher(settings=Settings(telegram_enabled=False))

    asyncio.run(dispatcher.dispatch_signal(999_999))


def test_live_runner_missing_config_returns() -> None:
    runner = LiveRunner(settings=_settings_without_txline(ingestion_mode="live"))

    asyncio.run(runner.run_forever())


def test_snapshot_runner_missing_config_returns() -> None:
    runner = SnapshotRunner(settings=_settings_without_txline(ingestion_mode="snapshot"))

    asyncio.run(runner.run_forever())


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _settings_without_txline(ingestion_mode: str) -> Settings:
    return Settings(
        ingestion_mode=ingestion_mode,
        txline_base_url=None,
        txline_guest_jwt=None,
        txline_api_token=None,
        txline_fixtures_snapshot_path=None,
        txline_odds_snapshot_path=None,
        txline_scores_snapshot_path=None,
        txline_odds_stream_path=None,
        txline_scores_stream_path=None,
    )


def _wait_for_replay(client: TestClient) -> dict:
    status = client.get("/api/replay/status").json()
    for _ in range(20):
        if status["status"] != "running":
            return status
        time.sleep(0.05)
        status = client.get("/api/replay/status").json()
    return status
