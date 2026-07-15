from __future__ import annotations

import asyncio

import httpx

from app.config import Settings
from app.txline.performance import TxLinePerformanceProbe, first_fixture_id


def test_first_fixture_id_handles_txline_fixture_shape() -> None:
    assert first_fixture_id([{"FixtureId": 17271370}]) == "17271370"
    assert first_fixture_id({"Data": [{"fixtureId": "abc"}]}) == "abc"
    assert first_fixture_id({"items": [{"fixture_id": 42}]}) == "42"


def test_txline_probe_measures_guest_and_configured_snapshots() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/auth/guest/start":
            return httpx.Response(200, json={"token": "guest-jwt"})
        if request.url.path == "/api/fixtures/snapshot":
            assert request.headers["authorization"] == "Bearer guest-jwt"
            assert request.headers["x-api-token"] == "api-token"
            return httpx.Response(200, json=[{"FixtureId": 17271370}])
        if request.url.path == "/api/odds/snapshot/17271370":
            return httpx.Response(
                200,
                json=[
                    {
                        "FixtureId": 17271370,
                        "OutcomeName": "Argentina",
                        "Price": 2.0,
                    }
                ],
            )
        if request.url.path == "/api/scores/snapshot/17271370":
            return httpx.Response(
                200,
                json=[{"FixtureId": 17271370, "Action": "kickoff", "Seq": 1}],
            )
        return httpx.Response(404)

    async def run_probe() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            probe = TxLinePerformanceProbe(
                settings=Settings(
                    txline_base_url="https://txline-dev.txodds.com",
                    txline_guest_jwt=None,
                    txline_api_token="api-token",
                ),
                client=client,
            )
            result = await probe.run()

        assert result.guest_jwt_source == "fresh"
        assert result.api_token_configured is True
        assert result.fixture_id == "17271370"
        assert [step.name for step in result.steps] == [
            "guest_session",
            "fixtures_snapshot",
            "odds_snapshot",
            "scores_snapshot",
        ]
        assert result.steps[2].normalized_count == 1
        assert result.steps[3].normalized_count == 1
        assert requests == [
            ("POST", "/auth/guest/start"),
            ("GET", "/api/fixtures/snapshot"),
            ("GET", "/api/odds/snapshot/17271370"),
            ("GET", "/api/scores/snapshot/17271370"),
        ]

    asyncio.run(run_probe())


def test_txline_probe_skips_data_without_api_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/guest/start"
        return httpx.Response(200, json={"token": "guest-jwt"})

    async def run_probe() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            probe = TxLinePerformanceProbe(
                settings=Settings(
                    txline_base_url="https://txline-dev.txodds.com",
                    txline_guest_jwt=None,
                    txline_api_token=None,
                ),
                client=client,
            )
            result = await probe.run()

        assert result.api_token_configured is False
        assert result.steps[0].name == "guest_session"
        assert result.steps[1].skipped_reason == "TXLINE_API_TOKEN is not configured."

    asyncio.run(run_probe())
