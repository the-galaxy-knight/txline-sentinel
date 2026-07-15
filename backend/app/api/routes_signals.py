from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.signals_repo import get_signal, list_signals
from app.txline.schemas import SignalRead

router = APIRouter(prefix="/api/signals", tags=["Signals"])


@router.get("", response_model=list[SignalRead])
def get_signals(
    fixture_id: str | None = None,
    signal_type: str | None = None,
    status: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    return list_signals(
        db,
        fixture_id=fixture_id,
        signal_type=signal_type,
        status=status,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )


@router.get("/latest", response_model=list[SignalRead])
def get_latest_signals(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    return list_signals(db, limit=limit)


@router.get("/high-confidence", response_model=list[SignalRead])
def get_high_confidence_signals(
    threshold: float = Query(default=80, ge=0, le=100),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    return list_signals(db, min_confidence=threshold, limit=limit)


@router.get("/{signal_id}", response_model=SignalRead)
def get_signal_by_id(signal_id: int, db: Session = Depends(get_db)) -> SignalRead:
    signal = get_signal(db, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")
    return signal
