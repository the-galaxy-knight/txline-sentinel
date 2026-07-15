from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.fixtures_repo import get_fixture, list_fixtures
from app.txline.schemas import FixtureRead

router = APIRouter(prefix="/api/fixtures", tags=["Fixtures"])


@router.get("", response_model=list[FixtureRead])
def get_fixtures(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FixtureRead]:
    return list_fixtures(db, limit=limit, offset=offset)


@router.get("/{fixture_id}", response_model=FixtureRead)
def get_fixture_by_id(fixture_id: str, db: Session = Depends(get_db)) -> FixtureRead:
    fixture = get_fixture(db, fixture_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Fixture not found.")
    return fixture
