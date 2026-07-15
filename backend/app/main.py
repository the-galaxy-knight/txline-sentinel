"""FastAPI application entry point and background ingestion lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_demo import router as demo_router
from app.api.routes_events import router as events_router
from app.api.routes_fixtures import router as fixtures_router
from app.api.routes_health import router as health_router
from app.api.routes_matches import router as matches_router
from app.api.routes_replay import router as replay_router
from app.api.routes_settings import router as settings_router
from app.api.routes_signals import router as signals_router
from app.api.routes_stream import router as stream_router
from app.config import get_settings
from app.db import init_db
from app.ingestion.live_runner import LiveRunner
from app.ingestion.snapshot_runner import SnapshotRunner
from app.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize storage and manage the selected ingestion runner."""

    init_db()
    ingestion_task = _start_ingestion_task()
    try:
        yield
    finally:
        if ingestion_task:
            ingestion_task.cancel()
            try:
                await ingestion_task
            except asyncio.CancelledError:
                logger.info("Background ingestion task cancelled.")


def _start_ingestion_task() -> asyncio.Task[None] | None:
    """Start the configured ingestion mode, if it should run on boot."""

    mode = settings.ingestion_mode.lower()
    if mode == "disabled":
        logger.info("Ingestion mode disabled.")
        return None
    if mode == "snapshot":
        logger.info("Starting snapshot ingestion.")
        return asyncio.create_task(SnapshotRunner(settings).run_forever())
    if mode == "live":
        logger.info("Starting live ingestion.")
        return asyncio.create_task(LiveRunner(settings).run_forever())
    if mode == "replay":
        logger.info("Replay mode selected; use /api/replay/start to run a scenario.")
        return None

    logger.warning("Unknown INGESTION_MODE=%s; ingestion will not start.", settings.ingestion_mode)
    return None


app = FastAPI(
    title="TxLINE Sentinel API",
    description="Backend API for autonomous World Cup odds intelligence signals.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(fixtures_router)
app.include_router(events_router)
app.include_router(signals_router)
app.include_router(replay_router)
app.include_router(stream_router)
app.include_router(settings_router)
app.include_router(matches_router)
app.include_router(demo_router)
