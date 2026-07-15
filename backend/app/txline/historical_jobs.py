"""Background job tracking for TxLINE historical replay builds."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.txline.auth import TxLineConfigurationError
from app.txline.historical_replay import (
    HistoricalInterval,
    HistoricalReplayProgress,
    build_historical_replay,
)
from app.txline.schemas import HistoricalReplayBuildRequest

ACTIVE_HISTORICAL_BUILD_STATUSES = {"queued", "running"}


class HistoricalReplayBuildAlreadyRunningError(RuntimeError):
    """Raised when a historical replay build is already active."""


class HistoricalReplayBuildNotFoundError(RuntimeError):
    """Raised when a historical replay build job cannot be found."""


@dataclass(slots=True)
class HistoricalReplayBuildJob:
    """In-memory status for a TxLINE historical replay build."""

    job_id: str
    status: str
    start: datetime
    end: datetime
    fixture_id: str | None
    scenario_name: str | None
    display_name: str | None
    description: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    intervals_requested: int = 0
    intervals_completed: int = 0
    odds_events: int = 0
    score_events: int = 0
    events_total: int = 0
    current_epoch_day: int | None = None
    current_hour_of_day: int | None = None
    current_interval: int | None = None
    current_interval_start: datetime | None = None
    path: str | None = None
    error: str | None = None


class HistoricalReplayBuildJobManager:
    """Run one historical replay build at a time and expose live progress."""

    def __init__(self) -> None:
        self._jobs: dict[str, HistoricalReplayBuildJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._active_job_id: str | None = None
        self._lock = asyncio.Lock()

    async def start(self, request: HistoricalReplayBuildRequest) -> HistoricalReplayBuildJob:
        """Create a build job and start it in the current event loop."""

        start = _as_utc(request.start)
        end = _as_utc(request.end)
        if end <= start:
            raise ValueError("Historical replay end time must be after start time.")

        async with self._lock:
            active_job = self._jobs.get(self._active_job_id or "")
            if active_job and active_job.status in ACTIVE_HISTORICAL_BUILD_STATUSES:
                raise HistoricalReplayBuildAlreadyRunningError(
                    f"Historical replay build {active_job.job_id} is already {active_job.status}."
                )

            job = HistoricalReplayBuildJob(
                job_id=uuid4().hex,
                status="queued",
                start=start,
                end=end,
                fixture_id=request.fixture_id,
                scenario_name=request.scenario_name,
                display_name=request.display_name,
                description=request.description,
            )
            self._jobs[job.job_id] = job
            self._active_job_id = job.job_id
            task = asyncio.create_task(
                self._run_job(job.job_id),
                name=f"historical-build-{job.job_id}",
            )
            self._tasks[job.job_id] = task
            task.add_done_callback(lambda _task: self._tasks.pop(job.job_id, None))
            return replace(job)

    def get(self, job_id: str) -> HistoricalReplayBuildJob:
        """Return a snapshot for a historical replay build job."""

        job = self._jobs.get(job_id)
        if job is None:
            raise HistoricalReplayBuildNotFoundError(f"Historical replay build {job_id} not found.")
        return replace(job)

    def latest(self) -> HistoricalReplayBuildJob | None:
        """Return the most recently created historical replay build job."""

        if not self._jobs:
            return None
        return replace(max(self._jobs.values(), key=lambda job: job.created_at))

    async def _run_job(self, job_id: str) -> None:
        await self._mark_running(job_id)
        job = self.get(job_id)

        async def update_progress(progress: HistoricalReplayProgress) -> None:
            await self._update_progress(job_id, progress)

        try:
            result = await build_historical_replay(
                start=job.start,
                end=job.end,
                fixture_id=job.fixture_id,
                scenario_name=job.scenario_name,
                display_name=job.display_name,
                description=job.description,
                progress_callback=update_progress,
            )
        except Exception as exc:
            await self._mark_failed(job_id, _error_message(exc))
            return

        await self._mark_completed(
            job_id,
            path=str(result.path),
            scenario_name=result.scenario_name,
            intervals_requested=result.intervals_requested,
            odds_events=result.odds_events,
            score_events=result.score_events,
            events_total=result.events_total,
        )

    async def _mark_running(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = datetime.now(UTC)
            job.status = "running"
            job.started_at = now
            job.updated_at = now

    async def _update_progress(
        self,
        job_id: str,
        progress: HistoricalReplayProgress,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = datetime.now(UTC)
            job.status = "running"
            job.updated_at = now
            job.intervals_requested = progress.intervals_requested
            job.intervals_completed = progress.intervals_completed
            job.odds_events = progress.odds_events
            job.score_events = progress.score_events
            job.events_total = progress.odds_events + progress.score_events
            _copy_interval(progress.current_interval, job)

    async def _mark_completed(
        self,
        job_id: str,
        *,
        path: str,
        scenario_name: str,
        intervals_requested: int,
        odds_events: int,
        score_events: int,
        events_total: int,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = datetime.now(UTC)
            job.status = "completed"
            job.completed_at = now
            job.updated_at = now
            job.path = path
            job.scenario_name = scenario_name
            job.intervals_requested = intervals_requested
            job.intervals_completed = intervals_requested
            job.odds_events = odds_events
            job.score_events = score_events
            job.events_total = events_total
            job.error = None
            if self._active_job_id == job_id:
                self._active_job_id = None

    async def _mark_failed(self, job_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = datetime.now(UTC)
            job.status = "failed"
            job.completed_at = now
            job.updated_at = now
            job.error = error
            if self._active_job_id == job_id:
                self._active_job_id = None


def _copy_interval(
    interval: HistoricalInterval | None,
    job: HistoricalReplayBuildJob,
) -> None:
    if interval is None:
        job.current_epoch_day = None
        job.current_hour_of_day = None
        job.current_interval = None
        job.current_interval_start = None
        return

    job.current_epoch_day = interval.epoch_day
    job.current_hour_of_day = interval.hour_of_day
    job.current_interval = interval.interval
    job.current_interval_start = interval.starts_at


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ValueError | TxLineConfigurationError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code if exc.response else "unknown"
        return f"TxLINE historical replay request failed with HTTP {status_code}."
    if isinstance(exc, httpx.HTTPError):
        return "TxLINE historical replay request failed."
    return f"Historical replay build failed: {exc}"


historical_replay_build_jobs = HistoricalReplayBuildJobManager()
