"""Async TxLINE HTTP and SSE client wrapper."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.txline.auth import TxLineConfigurationError, build_auth_headers
from app.txline.sse import SseEvent, iter_sse_events

logger = logging.getLogger(__name__)


class TxLineClient:
    """Fetch configured TxLINE snapshots and stream SSE events."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def __aenter__(self) -> TxLineClient:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        if self._owns_client:
            await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def start_guest_session(self) -> str:
        """Start an anonymous TxLINE guest session and return its JWT."""

        response = await self._client.post(self._url("/auth/guest/start", "guest session"))
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token") if isinstance(payload, dict) else payload
        if not isinstance(token, str) or not token:
            raise TxLineConfigurationError("TxLINE guest session response did not include a token.")
        return token

    async def fetch_fixtures_snapshot(
        self,
        start_epoch_day: int | None = None,
        competition_id: int | None = None,
    ) -> dict | list:
        params = {
            key: value
            for key, value in {
                "startEpochDay": start_epoch_day,
                "competitionId": competition_id,
            }.items()
            if value is not None
        }
        return await self._get_json(
            self.settings.txline_fixtures_snapshot_path,
            "fixtures snapshot",
            params=params or None,
        )

    async def fetch_odds_snapshot(self) -> dict | list:
        return await self._get_json(self.settings.txline_odds_snapshot_path, "odds snapshot")

    async def fetch_odds_snapshot_for_fixture(
        self, fixture_id: int | str, as_of: int | None = None
    ) -> dict | list:
        params = {"asOf": as_of} if as_of is not None else None
        return await self._get_json(
            f"/api/odds/snapshot/{fixture_id}",
            "fixture odds snapshot",
            params=params,
        )

    async def fetch_scores_snapshot(self) -> dict | list:
        return await self._get_json(self.settings.txline_scores_snapshot_path, "scores snapshot")

    async def fetch_scores_snapshot_for_fixture(
        self, fixture_id: int | str, as_of: int | None = None
    ) -> dict | list:
        params = {"asOf": as_of} if as_of is not None else None
        return await self._get_json(
            f"/api/scores/snapshot/{fixture_id}",
            "fixture scores snapshot",
            params=params,
        )

    async def fetch_historical_odds_interval(
        self,
        epoch_day: int,
        hour_of_day: int,
        interval: int,
        fixture_id: int | str | None = None,
    ) -> dict | list:
        """Fetch odds updates for one historical 5-minute interval."""

        params = {"fixtureId": fixture_id} if fixture_id is not None else None
        return await self._get_json(
            f"/api/odds/updates/{epoch_day}/{hour_of_day}/{interval}",
            "historical odds interval",
            params=params,
        )

    async def fetch_historical_scores_interval(
        self,
        epoch_day: int,
        hour_of_day: int,
        interval: int,
        fixture_id: int | str | None = None,
    ) -> dict | list:
        """Fetch score updates for one historical 5-minute interval."""

        params = {"fixtureId": fixture_id} if fixture_id is not None else None
        return await self._get_json(
            f"/api/scores/updates/{epoch_day}/{hour_of_day}/{interval}",
            "historical scores interval",
            params=params,
        )

    async def stream_odds(
        self,
        last_event_id: str | None = None,
        fixture_id: int | str | None = None,
    ) -> AsyncIterator[SseEvent]:
        params = {"fixtureId": fixture_id} if fixture_id is not None else None
        async for event in self._stream(
            self.settings.txline_odds_stream_path,
            "odds stream",
            last_event_id,
            params=params,
        ):
            yield event

    async def stream_scores(
        self,
        last_event_id: str | None = None,
        fixture_id: int | str | None = None,
    ) -> AsyncIterator[SseEvent]:
        params = {"fixtureId": fixture_id} if fixture_id is not None else None
        async for event in self._stream(
            self.settings.txline_scores_stream_path,
            "scores stream",
            last_event_id,
            params=params,
        ):
            yield event

    def _url(self, path: str | None, label: str) -> str:
        if not self.settings.txline_base_url:
            raise TxLineConfigurationError("TXLINE_BASE_URL is not configured.")
        if not path:
            raise TxLineConfigurationError(f"TxLINE {label} path is not configured.")
        return str(httpx.URL(self.settings.txline_base_url).join(path))

    async def _get_json(
        self,
        path: str | None,
        label: str,
        params: dict[str, Any] | None = None,
    ) -> dict | list:
        """Fetch a configured JSON snapshot endpoint."""

        url = self._url(path, label)
        headers = build_auth_headers(self.settings)
        logger.debug("Fetching TxLINE %s from %s", label, url)
        response = await self._client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _stream(
        self,
        path: str | None,
        label: str,
        last_event_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[SseEvent]:
        """Yield parsed SSE events from a configured TxLINE stream."""

        url = self._url(path, label)
        headers = build_auth_headers(self.settings)
        headers["Accept"] = "text/event-stream"
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        logger.info("Connecting to TxLINE %s at %s", label, url)
        async with self._client.stream("GET", url, headers=headers, params=params) as response:
            response.raise_for_status()
            async for event in iter_sse_events(response.aiter_lines()):
                yield event
