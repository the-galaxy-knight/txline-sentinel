from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingestion.replay_runner import (
    ReplayAlreadyRunningError,
    ReplayScenarioNotFoundError,
    list_replay_scenarios,
    replay_manager,
)
from app.repositories.replay_repo import get_latest_replay_run
from app.txline.historical_jobs import (
    HistoricalReplayBuildAlreadyRunningError,
    HistoricalReplayBuildJob,
    HistoricalReplayBuildNotFoundError,
    historical_replay_build_jobs,
)
from app.txline.schemas import (
    HistoricalReplayBuildJobResponse,
    HistoricalReplayBuildRequest,
    ReplayActionResponse,
    ReplayScenario,
    ReplayStartRequest,
    ReplayStatus,
)

router = APIRouter(prefix="/api/replay", tags=["Replay"])


@router.get("/scenarios", response_model=list[ReplayScenario])
def get_replay_scenarios() -> list[ReplayScenario]:
    return list_replay_scenarios()


@router.get("/status", response_model=ReplayStatus)
def get_replay_status(db: Session = Depends(get_db)) -> ReplayStatus:
    scenarios = list_replay_scenarios()
    latest_run = get_latest_replay_run(db)
    return ReplayStatus(
        status=latest_run.status if latest_run else "idle",
        active_run=latest_run,
        scenarios_available=len(scenarios),
    )


@router.post("/start", response_model=ReplayActionResponse)
async def start_replay(request: ReplayStartRequest) -> ReplayActionResponse:
    try:
        run = await replay_manager.start(
            scenario_name=request.scenario_name,
            speed_multiplier=request.speed_multiplier,
            reset_database=request.reset_database,
        )
    except ReplayAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReplayScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReplayActionResponse(status=run.status, message="Replay started.", active_run=run)


@router.post(
    "/historical/build",
    response_model=HistoricalReplayBuildJobResponse,
    status_code=202,
)
async def build_historical_replay_scenario(
    request: HistoricalReplayBuildRequest,
) -> HistoricalReplayBuildJobResponse:
    try:
        job = await historical_replay_build_jobs.start(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HistoricalReplayBuildAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _historical_build_job_response(job)


@router.get("/historical/build/latest", response_model=HistoricalReplayBuildJobResponse)
def get_latest_historical_replay_build() -> HistoricalReplayBuildJobResponse:
    job = historical_replay_build_jobs.latest()
    if job is None:
        raise HTTPException(status_code=404, detail="No historical replay build jobs found.")
    return _historical_build_job_response(job)


@router.get("/historical/build/{job_id}", response_model=HistoricalReplayBuildJobResponse)
def get_historical_replay_build(job_id: str) -> HistoricalReplayBuildJobResponse:
    try:
        job = historical_replay_build_jobs.get(job_id)
    except HistoricalReplayBuildNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _historical_build_job_response(job)


@router.post("/pause", response_model=ReplayActionResponse)
async def pause_replay() -> ReplayActionResponse:
    run = await replay_manager.pause()
    return ReplayActionResponse(
        status=run.status if run else "idle",
        message="Replay paused.",
        active_run=run,
    )


@router.post("/resume", response_model=ReplayActionResponse)
async def resume_replay() -> ReplayActionResponse:
    run = await replay_manager.resume()
    return ReplayActionResponse(
        status=run.status if run else "idle", message="Replay resumed.", active_run=run
    )


@router.post("/stop", response_model=ReplayActionResponse)
async def stop_replay() -> ReplayActionResponse:
    run = await replay_manager.stop()
    return ReplayActionResponse(
        status=run.status if run else "idle",
        message="Replay stopped.",
        active_run=run,
    )


@router.post("/reset", response_model=ReplayActionResponse)
async def reset_replay() -> ReplayActionResponse:
    await replay_manager.reset()
    return ReplayActionResponse(status="idle", message="Replay state reset.", active_run=None)


def _historical_build_job_response(
    job: HistoricalReplayBuildJob,
) -> HistoricalReplayBuildJobResponse:
    return HistoricalReplayBuildJobResponse(
        job_id=job.job_id,
        status=job.status,  # type: ignore[arg-type]
        start=job.start,
        end=job.end,
        fixture_id=job.fixture_id,
        scenario_name=job.scenario_name,
        display_name=job.display_name,
        created_at=job.created_at,
        started_at=job.started_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        intervals_requested=job.intervals_requested,
        intervals_completed=job.intervals_completed,
        odds_events=job.odds_events,
        score_events=job.score_events,
        events_total=job.events_total,
        current_epoch_day=job.current_epoch_day,
        current_hour_of_day=job.current_hour_of_day,
        current_interval=job.current_interval,
        current_interval_start=job.current_interval_start,
        path=job.path,
        error=job.error,
    )
