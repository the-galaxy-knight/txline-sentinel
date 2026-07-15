from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.market.state import market_state, score_state
from app.repositories.events_repo import list_odds_events
from app.repositories.fixtures_repo import get_fixture, list_fixtures
from app.repositories.signals_repo import list_signals
from app.txline.schemas import (
    FixtureRead,
    MarketStateRead,
    MatchStateResponse,
    ScoreStateRead,
    SignalRead,
)

router = APIRouter(prefix="/api/matches", tags=["Matches"])


@router.get("", response_model=list[FixtureRead])
def get_matches(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FixtureRead]:
    return list_fixtures(db, limit=limit, offset=offset)


@router.get("/{fixture_id}", response_model=FixtureRead)
def get_match(fixture_id: str, db: Session = Depends(get_db)) -> FixtureRead:
    fixture = get_fixture(db, fixture_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Match not found.")
    return fixture


@router.get("/{fixture_id}/signals", response_model=list[SignalRead])
def get_match_signals(
    fixture_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    return list_signals(db, fixture_id=fixture_id, limit=limit)


@router.get("/{fixture_id}/state", response_model=MatchStateResponse)
def get_match_state(fixture_id: str, db: Session = Depends(get_db)) -> MatchStateResponse:
    score_context = score_state.get(fixture_id)
    markets = [
        MarketStateRead(
            market_key=snapshot.market_key,
            consensus_key=snapshot.consensus_key,
            outcome_name=snapshot.outcome_name,
            p_now=snapshot.p_now,
            delta_60s=snapshot.delta_60s,
            delta_180s=snapshot.delta_180s,
            delta_300s=snapshot.delta_300s,
            rolling_volatility=snapshot.rolling_volatility,
            bookmaker_count=snapshot.bookmaker_count,
            bookmaker_dispersion=snapshot.bookmaker_dispersion,
        )
        for snapshot in market_state.snapshots_for_fixture(fixture_id)
    ]
    score = ScoreStateRead(**score_context.to_dict()) if score_context else None
    return MatchStateResponse(
        fixture_id=fixture_id,
        score=score,
        markets=markets,
        latest_odds=list_odds_events(db, fixture_id=fixture_id, limit=20),
        latest_signals=list_signals(db, fixture_id=fixture_id, limit=10),
    )
