from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    database: str
    txline_configured: bool
    llm_configured: bool
    telegram_configured: bool
    ingestion_mode: str
    snapshot_status: str | None = None


class FixtureRead(OrmSchema):
    id: int
    fixture_id: str
    competition_id: str | None = None
    participant_1: str
    participant_2: str
    participant_1_is_home: bool | None = None
    start_time: datetime | None = None
    sport_id: str | None = None
    status: str | None = None
    created_at: datetime
    updated_at: datetime
    raw_payload: Any = None


class OddsEventRead(OrmSchema):
    id: int
    source_mode: str
    fixture_id: str
    message_id: str | None = None
    event_hash: str | None = None
    tx_ts: datetime | None = None
    received_at: datetime
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
    raw_payload: Any = None


class ScoreEventRead(OrmSchema):
    id: int
    source_mode: str
    fixture_id: str
    event_hash: str | None = None
    tx_ts: datetime | None = None
    received_at: datetime
    seq: int | None = None
    game_state: str | None = None
    action: str | None = None
    clock_seconds: int | None = None
    participant_1_score: int | None = None
    participant_2_score: int | None = None
    raw_payload: Any = None


class SignalEvaluationRead(OrmSchema):
    id: int
    signal_id: int
    horizon_minutes: int
    evaluated_at: datetime | None = None
    probability_at_signal: float
    probability_at_horizon: float | None = None
    delta_after_signal: float | None = None
    continued_direction: bool | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    result: str


class SignalRead(OrmSchema):
    id: int
    source_mode: str
    fixture_id: str
    market_key: str
    outcome_name: str
    signal_type: str
    direction: str
    probability_before: float
    probability_after: float
    delta_probability: float
    window_seconds: int
    confidence_score: float
    magnitude_score: float | None = None
    velocity_score: float | None = None
    volatility_score: float | None = None
    freshness_score: float | None = None
    context_score: float | None = None
    trade_relevance_score: float | None = None
    score_context: Any = None
    explanation: str | None = None
    explanation_source: str | None = None
    status: str
    created_at: datetime
    tx_start_ts: datetime | None = None
    tx_end_ts: datetime | None = None
    raw_features: Any = None
    evaluations: list[SignalEvaluationRead] = []


class ReplayRunRead(OrmSchema):
    id: int
    name: str
    scenario_name: str
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    speed_multiplier: float
    status: str
    cursor_position: int
    events_total: int
    events_processed: int
    created_at: datetime
    updated_at: datetime


class ReplayScenario(BaseModel):
    name: str
    path: str
    description: str | None = None
    events_total: int = 0
    fixture_id: str | None = None
    display_name: str | None = None


class ReplayStatus(BaseModel):
    status: str
    active_run: ReplayRunRead | None = None
    scenarios_available: int


class ReplayStartRequest(BaseModel):
    scenario_name: str
    speed_multiplier: float = 30.0
    reset_database: bool = False


class HistoricalReplayBuildRequest(BaseModel):
    start: datetime
    end: datetime
    fixture_id: str | None = None
    scenario_name: str | None = None
    display_name: str | None = None
    description: str | None = None


class HistoricalReplayBuildJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    start: datetime
    end: datetime
    fixture_id: str | None = None
    scenario_name: str | None = None
    display_name: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None
    intervals_requested: int = 0
    intervals_completed: int = 0
    odds_events: int = 0
    score_events: int = 0
    events_total: int = 0
    current_epoch_day: int | None = None
    current_hour_of_day: int | None = None
    current_interval: int | None = None
    current_interval_start: datetime | None = None
    path: str | None = None
    error: str | None = None


class ReplayActionResponse(BaseModel):
    status: str
    message: str
    active_run: ReplayRunRead | None = None


class SettingsResponse(BaseModel):
    app: str
    env: str
    ingestion_mode: str
    txline_configured: bool
    llm_enabled: bool
    llm_configured: bool
    llm_model: str
    telegram_enabled: bool
    telegram_configured: bool
    telegram_min_confidence: float


class LiveStreamStatusRead(BaseModel):
    name: str
    state: str
    last_event_id: str | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    reconnect_attempts: int = 0
    events_received: int = 0


class RuntimeSettingsResponse(BaseModel):
    app_env: str
    ingestion_mode: str
    txline_configured: bool
    llm_enabled: bool
    llm_configured: bool
    telegram_enabled: bool
    telegram_configured: bool
    database: str
    replay_scenarios_dir: str
    replay_scenarios_count: int
    snapshot_status: str
    live_streams: dict[str, LiveStreamStatusRead]


class DashboardEvent(BaseModel):
    type: str
    created_at: datetime
    payload: dict[str, Any]


class ScoreStateRead(BaseModel):
    fixture_id: str
    participant_1_score: int | None = None
    participant_2_score: int | None = None
    game_state: str | None = None
    clock_seconds: int | None = None
    last_action: str | None = None
    last_goal_like_action: str | None = None
    last_card_like_action: str | None = None


class MarketStateRead(BaseModel):
    market_key: str
    consensus_key: str
    outcome_name: str | None = None
    p_now: float | None = None
    delta_60s: float | None = None
    delta_180s: float | None = None
    delta_300s: float | None = None
    rolling_volatility: float = 0.0
    bookmaker_count: int = 0
    bookmaker_dispersion: float = 0.0


class MatchStateResponse(BaseModel):
    fixture_id: str
    score: ScoreStateRead | None = None
    markets: list[MarketStateRead]
    latest_odds: list[OddsEventRead] = []
    latest_signals: list[SignalRead]


class SignalStatusFilter(BaseModel):
    status: Literal["new", "alerted", "evaluating", "evaluated"] | None = None
