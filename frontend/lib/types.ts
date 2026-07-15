export type SourceMode = "live" | "snapshot" | "replay" | "disabled" | string;

export type HealthResponse = {
  status?: string;
  app?: string;
  env?: string;
  database?: string;
  txline_configured?: boolean;
  llm_configured?: boolean;
  telegram_configured?: boolean;
  ingestion_mode?: SourceMode;
  snapshot_status?: string | null;
};

export type RuntimeSettings = {
  app_env?: string;
  ingestion_mode?: SourceMode;
  txline_configured?: boolean;
  llm_enabled?: boolean;
  llm_configured?: boolean;
  telegram_enabled?: boolean;
  telegram_configured?: boolean;
  database?: string;
  replay_scenarios_dir?: string;
  replay_scenarios_count?: number;
  snapshot_status?: string;
  live_streams?: Record<string, LiveStreamStatus>;
};

export type LiveStreamStatus = {
  name?: string;
  state?: string;
  last_event_id?: string | null;
  last_event_at?: string | null;
  last_error?: string | null;
  reconnect_attempts?: number;
  events_received?: number;
};

export type ReplayScenario = {
  name: string;
  path?: string;
  description?: string | null;
  events_total?: number;
  fixture_id?: string | null;
  display_name?: string | null;
};

export type ReplayRun = {
  id?: number;
  name?: string;
  scenario_name?: string;
  started_at?: string | null;
  stopped_at?: string | null;
  speed_multiplier?: number;
  status?: string;
  cursor_position?: number;
  events_total?: number;
  events_processed?: number;
  created_at?: string;
  updated_at?: string;
};

export type ReplayStatus = {
  status?: string;
  active_run?: ReplayRun | null;
  scenarios_available?: number;
};

export type ReplayStartRequest = {
  scenario_name: string;
  speed_multiplier: number;
  reset_database: boolean;
};

export type HistoricalReplayBuildRequest = {
  start: string;
  end: string;
  fixture_id?: string;
  scenario_name?: string;
  display_name?: string;
  description?: string;
};

export type HistoricalReplayBuildStatus = "queued" | "running" | "completed" | "failed";

export type HistoricalReplayBuildJob = {
  job_id: string;
  status: HistoricalReplayBuildStatus;
  start?: string;
  end?: string;
  fixture_id?: string | null;
  scenario_name?: string | null;
  display_name?: string | null;
  created_at?: string;
  started_at?: string | null;
  updated_at?: string;
  completed_at?: string | null;
  intervals_requested?: number;
  intervals_completed?: number;
  odds_events?: number;
  score_events?: number;
  events_total?: number;
  current_epoch_day?: number | null;
  current_hour_of_day?: number | null;
  current_interval?: number | null;
  current_interval_start?: string | null;
  path?: string | null;
  error?: string | null;
};

export type SignalEvaluation = {
  id?: number;
  signal_id?: number;
  horizon_minutes?: number;
  evaluated_at?: string | null;
  probability_at_signal?: number;
  probability_at_horizon?: number | null;
  delta_after_signal?: number | null;
  continued_direction?: boolean | null;
  max_favorable_excursion?: number | null;
  max_adverse_excursion?: number | null;
  result?: string;
};

export type Signal = {
  id: number;
  source_mode?: SourceMode;
  fixture_id?: string;
  market_key?: string;
  outcome_name?: string;
  signal_type?: string;
  direction?: string;
  probability_before?: number;
  probability_after?: number;
  delta_probability?: number;
  window_seconds?: number;
  confidence_score?: number;
  magnitude_score?: number | null;
  velocity_score?: number | null;
  volatility_score?: number | null;
  freshness_score?: number | null;
  context_score?: number | null;
  trade_relevance_score?: number | null;
  score_context?: Record<string, unknown> | null;
  explanation?: string | null;
  explanation_source?: string | null;
  status?: string;
  created_at?: string;
  tx_start_ts?: string | null;
  tx_end_ts?: string | null;
  raw_features?: Record<string, unknown> | null;
  evaluations?: SignalEvaluation[];
};

export type Fixture = {
  id?: number;
  fixture_id?: string;
  competition_id?: string | null;
  participant_1?: string;
  participant_2?: string;
  participant_1_is_home?: boolean | null;
  start_time?: string | null;
  sport_id?: string | null;
  status?: string | null;
  created_at?: string;
  updated_at?: string;
  raw_payload?: unknown;
};

export type OddsEvent = {
  id?: number;
  source_mode?: SourceMode;
  fixture_id?: string;
  message_id?: string | null;
  tx_ts?: string | null;
  received_at?: string;
  bookmaker?: string | null;
  bookmaker_id?: string | null;
  odds_type?: string | null;
  market_period?: string | null;
  market_parameters?: string | null;
  game_state?: string | null;
  in_running?: boolean | null;
  outcome_name?: string | null;
  price?: number | null;
  implied_probability?: number | null;
};

export type ScoreEvent = {
  id?: number;
  source_mode?: SourceMode;
  fixture_id?: string;
  tx_ts?: string | null;
  received_at?: string;
  seq?: number | null;
  game_state?: string | null;
  action?: string | null;
  clock_seconds?: number | null;
  participant_1_score?: number | null;
  participant_2_score?: number | null;
};

export type ScoreState = {
  fixture_id?: string;
  participant_1_score?: number | null;
  participant_2_score?: number | null;
  game_state?: string | null;
  clock_seconds?: number | null;
  last_action?: string | null;
  last_goal_like_action?: string | null;
  last_card_like_action?: string | null;
};

export type MarketState = {
  market_key?: string;
  consensus_key?: string;
  outcome_name?: string | null;
  p_now?: number | null;
  delta_60s?: number | null;
  delta_180s?: number | null;
  delta_300s?: number | null;
  rolling_volatility?: number;
  bookmaker_count?: number;
  bookmaker_dispersion?: number;
};

export type MatchState = {
  fixture_id?: string;
  score?: ScoreState | null;
  markets?: MarketState[];
  latest_odds?: OddsEvent[];
  latest_signals?: Signal[];
};

export type DashboardStreamEvent = {
  type?: string;
  created_at?: string;
  payload?: Record<string, unknown>;
};
