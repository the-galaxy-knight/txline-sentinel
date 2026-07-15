from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.ingestion.replay_runner import list_replay_scenarios
from app.ingestion.status import ingestion_status
from app.txline.schemas import LiveStreamStatusRead, RuntimeSettingsResponse, SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("", response_model=SettingsResponse)
def get_runtime_settings(settings: Settings = Depends(get_settings)) -> SettingsResponse:
    return SettingsResponse(
        app=settings.app_name,
        env=settings.app_env,
        ingestion_mode=settings.ingestion_mode,
        txline_configured=settings.txline_configured,
        llm_enabled=settings.llm_enabled,
        llm_configured=settings.llm_configured,
        llm_model=settings.llm_model,
        telegram_enabled=settings.telegram_enabled,
        telegram_configured=settings.telegram_configured,
        telegram_min_confidence=settings.telegram_min_confidence,
    )


@router.get("/runtime", response_model=RuntimeSettingsResponse)
def get_safe_runtime_settings(
    settings: Settings = Depends(get_settings),
) -> RuntimeSettingsResponse:
    return RuntimeSettingsResponse(
        app_env=settings.app_env,
        ingestion_mode=settings.ingestion_mode,
        txline_configured=settings.txline_configured,
        llm_enabled=settings.llm_enabled,
        llm_configured=settings.llm_configured,
        telegram_enabled=settings.telegram_enabled,
        telegram_configured=settings.telegram_configured,
        database=settings.database_driver,
        replay_scenarios_dir=settings.replay_scenarios_dir,
        replay_scenarios_count=len(list_replay_scenarios(settings)),
        snapshot_status=ingestion_status.snapshot.state,
        live_streams={
            name: LiveStreamStatusRead(
                name=stream.name,
                state=stream.state,
                last_event_id=stream.last_event_id,
                last_event_at=stream.last_event_at,
                last_error=stream.last_error,
                reconnect_attempts=stream.reconnect_attempts,
                events_received=stream.events_received,
            )
            for name, stream in ingestion_status.live_streams.items()
        },
    )
