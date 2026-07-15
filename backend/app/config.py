"""Environment-backed runtime configuration for TxLINE Sentinel.

This module centralizes feature flags and integration readiness checks. The
derived properties intentionally expose only safe booleans so API responses and
logs can describe configuration state without leaking credentials.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env` files."""

    app_name: str = "TxLINE Sentinel"
    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./txline_sentinel.db"

    txline_base_url: str | None = None
    txline_guest_jwt: str | None = None
    txline_api_token: str | None = None

    txline_fixtures_snapshot_path: str | None = None
    txline_odds_snapshot_path: str | None = None
    txline_scores_snapshot_path: str | None = None
    txline_odds_stream_path: str | None = None
    txline_scores_stream_path: str | None = None

    ingestion_mode: str = "disabled"
    snapshot_poll_seconds: int = Field(default=30, ge=1)
    live_reconnect_initial_seconds: int = Field(default=1, ge=1)
    live_reconnect_max_seconds: int = Field(default=60, ge=1)
    live_stream_heartbeat_timeout_seconds: int = Field(default=90, ge=1)

    replay_scenarios_dir: str = "app/data/replay_scenarios"

    llm_enabled: bool = False
    openai_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: int = Field(default=8, ge=1)

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_min_confidence: float = Field(default=80, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def txline_configured(self) -> bool:
        return bool(self.txline_base_url and (self.txline_guest_jwt or self.txline_api_token))

    @property
    def live_streams_configured(self) -> bool:
        return bool(
            self.txline_configured
            and (self.txline_odds_stream_path or self.txline_scores_stream_path)
        )

    @property
    def snapshots_configured(self) -> bool:
        return bool(
            self.txline_configured
            and (
                self.txline_fixtures_snapshot_path
                or self.txline_odds_snapshot_path
                or self.txline_scores_snapshot_path
            )
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_enabled and self.openai_api_key)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_enabled and self.telegram_bot_token and self.telegram_chat_id)

    @property
    def database_driver(self) -> str:
        return self.database_url.split(":", 1)[0]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings object.

    Settings are cached so route handlers, runners, and repositories share a
    stable view of configuration for the life of the process.
    """

    return Settings()
