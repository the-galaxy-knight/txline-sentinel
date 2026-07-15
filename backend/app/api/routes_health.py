from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion.status import ingestion_status
from app.txline.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        app=settings.app_name,
        env=settings.app_env,
        database=database_status,
        txline_configured=settings.txline_configured,
        llm_configured=settings.llm_configured,
        telegram_configured=settings.telegram_configured,
        ingestion_mode=settings.ingestion_mode,
        snapshot_status=ingestion_status.snapshot.state,
    )
