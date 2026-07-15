from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import OddsEvent, ReplayRun, ScoreEvent, Signal, SignalEvaluation, TelegramAlert
from app.ingestion.event_processor import event_processor


def reset_demo_data(db: Session, keep_fixtures: bool = True) -> None:
    for model in (SignalEvaluation, TelegramAlert, Signal, OddsEvent, ScoreEvent, ReplayRun):
        db.execute(delete(model))
    db.commit()
    event_processor.clear_state()
