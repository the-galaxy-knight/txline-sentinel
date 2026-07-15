from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.events_repo import list_odds_events, list_score_events
from app.txline.schemas import OddsEventRead, ScoreEventRead

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("/odds", response_model=list[OddsEventRead])
def get_odds_events(
    fixture_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[OddsEventRead]:
    return list_odds_events(db, fixture_id=fixture_id, limit=limit, offset=offset)


@router.get("/scores", response_model=list[ScoreEventRead])
def get_score_events(
    fixture_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ScoreEventRead]:
    return list_score_events(db, fixture_id=fixture_id, limit=limit, offset=offset)
