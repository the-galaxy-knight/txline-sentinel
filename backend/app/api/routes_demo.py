from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.demo import reset_demo_data

router = APIRouter(prefix="/api/demo", tags=["Demo"])


@router.post("/reset")
def reset_demo(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if settings.app_env.lower() != "local":
        raise HTTPException(status_code=403, detail="Demo reset is only enabled in local env.")
    reset_demo_data(db)
    return {"status": "ok", "message": "Demo data reset."}
