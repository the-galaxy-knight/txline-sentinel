from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ReplayRun


def get_latest_replay_run(db: Session) -> ReplayRun | None:
    statement = select(ReplayRun).order_by(ReplayRun.id.desc()).limit(1)
    return db.scalar(statement)
