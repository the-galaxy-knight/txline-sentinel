from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, Signal
from app.ingestion.event_processor import EventProcessor
from app.ingestion.replay_runner import ReplayManager, list_replay_scenarios
from app.market.state import MarketState, ScoreState


def test_replay_scenario_loading() -> None:
    settings = Settings(replay_scenarios_dir="app/data/replay_scenarios")

    scenarios = list_replay_scenarios(settings)

    names = {scenario.name for scenario in scenarios}
    assert "argentina_france_no_score_sharp_move" in names
    assert "brazil_germany_post_goal_reaction" in names
    assert "spain_portugal_bookmaker_divergence" in names


def test_replay_scenario_emits_at_least_one_signal() -> None:
    session_factory = _session_factory()
    processor = EventProcessor(
        session_factory=session_factory,
        markets=MarketState(),
        scores=ScoreState(),
    )
    manager = ReplayManager(
        settings=Settings(replay_scenarios_dir="app/data/replay_scenarios"),
        processor=processor,
        session_factory=session_factory,
    )

    async def run_replay() -> None:
        await manager.start(
            "argentina_france_no_score_sharp_move",
            speed_multiplier=1_000_000,
            reset_database=True,
        )
        assert manager.current_task is not None
        await manager.current_task

    asyncio.run(run_replay())

    with session_factory() as db:
        signals = db.query(Signal).all()
        signal_types = {signal.signal_type for signal in signals}
        assert signals
        assert "no_score_market_pressure" in signal_types
        assert "sharp_movement" in signal_types


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
