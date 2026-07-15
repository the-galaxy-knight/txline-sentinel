from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.txline.client import TxLineClient
from app.txline.historical_jobs import HistoricalReplayBuildJob
from app.txline.historical_replay import (
    HistoricalReplayBuilder,
    intervals_between,
)


def test_historical_interval_client_paths_and_fixture_filter() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, str(request.url.query, "utf-8")))
        return httpx.Response(200, json=[])

    async def run_client() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TxLineClient(
                settings=Settings(
                    txline_base_url="https://txline-dev.txodds.com",
                    txline_guest_jwt="guest",
                    txline_api_token="api-token",
                ),
                client=http_client,
            )
            await client.fetch_historical_odds_interval(20643, 12, 3, fixture_id=18143850)
            await client.fetch_historical_scores_interval(20643, 12, 3, fixture_id=18143850)

    asyncio.run(run_client())

    assert requests == [
        ("/api/odds/updates/20643/12/3", "fixtureId=18143850"),
        ("/api/scores/updates/20643/12/3", "fixtureId=18143850"),
    ]


def test_intervals_between_floors_start_and_covers_range() -> None:
    intervals = intervals_between(
        datetime(2026, 7, 9, 12, 1, tzinfo=UTC),
        datetime(2026, 7, 9, 12, 11, tzinfo=UTC),
    )

    assert [(item.hour_of_day, item.interval) for item in intervals] == [(12, 0), (12, 1), (12, 2)]


def test_historical_replay_builder_writes_sorted_replay_json(tmp_path) -> None:
    client = _FakeHistoricalClient()
    builder = HistoricalReplayBuilder(
        client=client,  # type: ignore[arg-type]
        settings=Settings(replay_scenarios_dir=str(tmp_path)),
    )
    progress: list[tuple[int, int, int, int]] = []

    async def run_builder() -> None:
        result = await builder.build(
            start=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
            end=datetime(2026, 7, 9, 12, 10, tzinfo=UTC),
            fixture_id=18143850,
            scenario_name="txline-real-fixture",
            display_name="TxLINE real fixture replay",
            progress_callback=lambda update: progress.append(
                (
                    update.intervals_requested,
                    update.intervals_completed,
                    update.odds_events,
                    update.score_events,
                )
            ),
        )

        assert result.scenario_name == "txline-real-fixture"
        assert result.intervals_requested == 2
        assert result.odds_events == 2
        assert result.score_events == 1
        assert result.events_total == 3

        loaded = json.loads(result.path.read_text(encoding="utf-8"))
        assert loaded["source"] == "txline_historical"
        assert loaded["fixture_id"] == "18143850"
        assert loaded["fixture"]["FixtureId"] == "18143850"
        assert [event["event_type"] for event in loaded["events"]] == ["score", "odds", "odds"]
        assert [event["offset_ms"] for event in loaded["events"]] == [0, 1000, 301000]
        assert loaded["events"][1]["payload"]["MessageId"] == "odds-1"

    asyncio.run(run_builder())

    assert client.calls == [
        ("odds", 20643, 12, 0, 18143850),
        ("scores", 20643, 12, 0, 18143850),
        ("odds", 20643, 12, 1, 18143850),
        ("scores", 20643, 12, 1, 18143850),
    ]
    assert progress == [(2, 0, 0, 0), (2, 1, 1, 1), (2, 2, 2, 1)]


def test_historical_replay_build_endpoint_starts_progress_job(monkeypatch) -> None:
    from app.main import app

    captured: dict = {}

    class FakeHistoricalReplayBuildJobs:
        async def start(self, request):
            captured["fixture_id"] = request.fixture_id
            captured["scenario_name"] = request.scenario_name
            captured["display_name"] = request.display_name
            return HistoricalReplayBuildJob(
                job_id="job-1",
                status="queued",
                start=request.start,
                end=request.end,
                fixture_id=request.fixture_id,
                scenario_name=request.scenario_name,
                display_name=request.display_name,
                description=request.description,
                intervals_requested=2,
                intervals_completed=0,
            )

    monkeypatch.setattr(
        "app.api.routes_replay.historical_replay_build_jobs",
        FakeHistoricalReplayBuildJobs(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/replay/historical/build",
            json={
                "start": "2026-07-09T12:00:00Z",
                "end": "2026-07-09T12:10:00Z",
                "fixture_id": "18143850",
                "scenario_name": "txline-history",
                "display_name": "TxLINE History",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] == "job-1"
    assert payload["status"] == "queued"
    assert payload["scenario_name"] == "txline-history"
    assert payload["fixture_id"] == "18143850"
    assert payload["intervals_requested"] == 2
    assert payload["intervals_completed"] == 0
    assert captured["fixture_id"] == "18143850"
    assert captured["scenario_name"] == "txline-history"
    assert captured["display_name"] == "TxLINE History"


def test_historical_replay_build_status_endpoint(monkeypatch) -> None:
    from app.main import app

    class FakeHistoricalReplayBuildJobs:
        def get(self, job_id):
            assert job_id == "job-1"
            return HistoricalReplayBuildJob(
                job_id="job-1",
                status="completed",
                start=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
                end=datetime(2026, 7, 9, 12, 10, tzinfo=UTC),
                fixture_id="18143850",
                scenario_name="txline-history",
                display_name="TxLINE History",
                description=None,
                intervals_requested=2,
                intervals_completed=2,
                odds_events=3,
                score_events=1,
                events_total=4,
                path="app/data/replay_scenarios/txline-history.json",
            )

    monkeypatch.setattr(
        "app.api.routes_replay.historical_replay_build_jobs",
        FakeHistoricalReplayBuildJobs(),
    )

    with TestClient(app) as client:
        response = client.get("/api/replay/historical/build/job-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-1"
    assert payload["status"] == "completed"
    assert payload["scenario_name"] == "txline-history"
    assert payload["path"] == "app/data/replay_scenarios/txline-history.json"
    assert payload["events_total"] == 4


class _FakeHistoricalClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int, int, int | str | None]] = []

    async def fetch_historical_odds_interval(
        self,
        epoch_day: int,
        hour_of_day: int,
        interval: int,
        fixture_id: int | str | None = None,
    ) -> list[dict]:
        self.calls.append(("odds", epoch_day, hour_of_day, interval, fixture_id))
        if interval == 0:
            return [
                {
                    "FixtureId": 18143850,
                    "MessageId": "odds-1",
                    "Ts": 1783598401,
                    "PriceNames": ["Brazil"],
                    "Prices": [2.0],
                    "Pct": ["50.000"],
                }
            ]
        return [
            {
                "FixtureId": 18143850,
                "MessageId": "odds-2",
                "Ts": 1783598701,
                "PriceNames": ["Brazil"],
                "Prices": [1.83],
                "Pct": ["54.500"],
            }
        ]

    async def fetch_historical_scores_interval(
        self,
        epoch_day: int,
        hour_of_day: int,
        interval: int,
        fixture_id: int | str | None = None,
    ) -> list[dict]:
        self.calls.append(("scores", epoch_day, hour_of_day, interval, fixture_id))
        if interval == 0:
            return [{"fixtureId": 18143850, "ts": 1783598400, "action": "match_started"}]
        return []
