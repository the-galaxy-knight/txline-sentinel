"""Database models and session wiring for the backend.

The MVP uses SQLAlchemy models directly without Alembic migrations. `init_db`
creates missing tables and applies the small SQLite compatibility patches needed
for local demo databases that predate the idempotency fields.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.config import get_settings


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp for SQLAlchemy defaults."""

    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs: dict[str, Any] = {"connect_args": connect_args, "future": True}
if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
    engine_kwargs["poolclass"] = StaticPool
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fixture_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    competition_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    participant_1: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    participant_2: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    participant_1_is_home: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sport_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class OddsEvent(Base):
    __tablename__ = "odds_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    fixture_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    event_hash: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    tx_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    bookmaker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bookmaker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    odds_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    market_period: Mapped[str | None] = mapped_column(String(128), nullable=True)
    market_parameters: Mapped[str | None] = mapped_column(String(255), nullable=True)
    game_state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    in_running: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    implied_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ScoreEvent(Base):
    __tablename__ = "score_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    fixture_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_hash: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    tx_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clock_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participant_1_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participant_2_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    fixture_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    market_key: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    probability_before: Mapped[float] = mapped_column(Float, nullable=False)
    probability_after: Mapped[float] = mapped_column(Float, nullable=False)
    delta_probability: Mapped[float] = mapped_column(Float, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    magnitude_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    velocity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    freshness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    tx_start_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tx_end_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_features: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    evaluations: Mapped[list[SignalEvaluation]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[TelegramAlert]] = relationship(back_populates="signal")


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), index=True, nullable=False)
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    probability_at_signal: Mapped[float] = mapped_column(Float, nullable=False)
    probability_at_horizon: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_after_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    continued_direction: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    max_favorable_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_adverse_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")

    signal: Mapped[Signal] = relationship(back_populates="evaluations")


class TelegramAlert(Base):
    __tablename__ = "telegram_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("signals.id"), index=True, nullable=True
    )
    chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    signal: Mapped[Signal | None] = relationship(back_populates="alerts")


class ReplayRun(Base):
    __tablename__ = "replay_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    speed_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="idle")
    cursor_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class IngestionOffset(Base):
    __tablename__ = "ingestion_offsets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stream_name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    last_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_tx_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


def init_db() -> None:
    """Create tables and apply migration-free MVP schema fixes."""

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_mvp_columns()


def _ensure_sqlite_mvp_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    with engine.begin() as connection:
        if "odds_events" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("odds_events")}
            if "event_hash" not in columns:
                connection.execute(
                    text("ALTER TABLE odds_events ADD COLUMN event_hash VARCHAR(128)")
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_odds_events_event_hash ON odds_events(event_hash)"
                )
            )
        if "score_events" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("score_events")}
            if "event_hash" not in columns:
                connection.execute(
                    text("ALTER TABLE score_events ADD COLUMN event_hash VARCHAR(128)")
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_score_events_event_hash ON score_events(event_hash)"
                )
            )


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session for FastAPI dependencies."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
