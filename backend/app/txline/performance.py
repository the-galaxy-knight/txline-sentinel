"""Small TxLINE integration performance probe.

The probe is intentionally read-only. It can always test guest-session latency,
and it tests fixture/odds/score data latency only when an activated API token is
configured.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.ingestion.normalizer import normalize_odds_payload, normalize_score_payload

DEFAULT_TXLINE_BASE_URL = "https://txline-dev.txodds.com"
DEFAULT_FIXTURES_SNAPSHOT_PATH = "/api/fixtures/snapshot"
DEFAULT_ODDS_STREAM_PATH = "/api/odds/stream"
DEFAULT_SCORES_STREAM_PATH = "/api/scores/stream"


@dataclass(frozen=True)
class TxLineProbeStep:
    """Result for one outbound TxLINE request or skipped probe step."""

    name: str
    method: str
    path: str
    duration_ms: float | None = None
    status_code: int | None = None
    item_count: int | None = None
    normalized_count: int | None = None
    fixture_id: str | None = None
    skipped_reason: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.skipped_reason is None and self.status_code is not None


@dataclass(frozen=True)
class TxLineProbeResult:
    """Aggregated result for the TxLINE probe command."""

    base_url: str
    guest_jwt_source: str | None
    api_token_configured: bool
    fixture_id: str | None
    steps: list[TxLineProbeStep] = field(default_factory=list)


class TxLinePerformanceProbe:
    """Measure TxLINE auth and data endpoint latency without persisting data."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = base_url or self.settings.txline_base_url or DEFAULT_TXLINE_BASE_URL
        self.client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def run(
        self,
        fixture_id: str | None = None,
        competition_id: int | None = None,
        start_epoch_day: int | None = None,
    ) -> TxLineProbeResult:
        steps: list[TxLineProbeStep] = []
        fresh_guest_jwt: str | None = None
        guest_jwt_source = "env" if self.settings.txline_guest_jwt else None

        auth_step, token = await self._start_guest_session()
        steps.append(auth_step)
        if token:
            fresh_guest_jwt = token
            guest_jwt_source = "fresh"

        guest_jwt = self.settings.txline_guest_jwt or fresh_guest_jwt
        if not self.settings.txline_api_token:
            steps.append(
                TxLineProbeStep(
                    name="fixtures_snapshot",
                    method="GET",
                    path=DEFAULT_FIXTURES_SNAPSHOT_PATH,
                    skipped_reason="TXLINE_API_TOKEN is not configured.",
                )
            )
            return TxLineProbeResult(
                base_url=self.base_url,
                guest_jwt_source=guest_jwt_source,
                api_token_configured=False,
                fixture_id=fixture_id,
                steps=steps,
            )

        if not guest_jwt:
            steps.append(
                TxLineProbeStep(
                    name="fixtures_snapshot",
                    method="GET",
                    path=DEFAULT_FIXTURES_SNAPSHOT_PATH,
                    skipped_reason="No valid guest JWT is available.",
                )
            )
            return TxLineProbeResult(
                base_url=self.base_url,
                guest_jwt_source=guest_jwt_source,
                api_token_configured=True,
                fixture_id=fixture_id,
                steps=steps,
            )

        headers = self._data_headers(guest_jwt)
        fixture_step, fixtures_payload = await self._get_json(
            name="fixtures_snapshot",
            path=DEFAULT_FIXTURES_SNAPSHOT_PATH,
            headers=headers,
            params={
                key: value
                for key, value in {
                    "competitionId": competition_id,
                    "startEpochDay": start_epoch_day,
                }.items()
                if value is not None
            },
        )
        steps.append(fixture_step)

        selected_fixture_id = fixture_id or first_fixture_id(fixtures_payload)
        if not selected_fixture_id:
            steps.append(
                TxLineProbeStep(
                    name="odds_snapshot",
                    method="GET",
                    path="/api/odds/snapshot/{fixtureId}",
                    skipped_reason="No fixture ID was provided or found in fixtures response.",
                )
            )
            steps.append(
                TxLineProbeStep(
                    name="scores_snapshot",
                    method="GET",
                    path="/api/scores/snapshot/{fixtureId}",
                    skipped_reason="No fixture ID was provided or found in fixtures response.",
                )
            )
            return TxLineProbeResult(
                base_url=self.base_url,
                guest_jwt_source=guest_jwt_source,
                api_token_configured=True,
                fixture_id=None,
                steps=steps,
            )

        odds_path = f"/api/odds/snapshot/{selected_fixture_id}"
        odds_step, odds_payload = await self._get_json(
            name="odds_snapshot",
            path=odds_path,
            headers=headers,
        )
        steps.append(
            _with_normalized_count(
                odds_step,
                normalize_odds_payload(_payload_for_normalizer(odds_payload), "txline_probe"),
                selected_fixture_id,
            )
        )

        scores_path = f"/api/scores/snapshot/{selected_fixture_id}"
        scores_step, scores_payload = await self._get_json(
            name="scores_snapshot",
            path=scores_path,
            headers=headers,
        )
        steps.append(
            _with_normalized_count(
                scores_step,
                normalize_score_payload(_payload_for_normalizer(scores_payload), "txline_probe"),
                selected_fixture_id,
            )
        )

        return TxLineProbeResult(
            base_url=self.base_url,
            guest_jwt_source=guest_jwt_source,
            api_token_configured=True,
            fixture_id=selected_fixture_id,
            steps=steps,
        )

    async def _start_guest_session(self) -> tuple[TxLineProbeStep, str | None]:
        path = "/auth/guest/start"
        started = time.perf_counter()
        try:
            response = await self.client.post(str(httpx.URL(self.base_url).join(path)))
            duration_ms = _elapsed_ms(started)
            response.raise_for_status()
            payload = response.json()
            token = payload.get("token") if isinstance(payload, dict) else payload
            if not isinstance(token, str) or not token:
                return (
                    TxLineProbeStep(
                        name="guest_session",
                        method="POST",
                        path=path,
                        duration_ms=duration_ms,
                        status_code=response.status_code,
                        error="Response did not include a token.",
                    ),
                    None,
                )
            return (
                TxLineProbeStep(
                    name="guest_session",
                    method="POST",
                    path=path,
                    duration_ms=duration_ms,
                    status_code=response.status_code,
                    item_count=1,
                ),
                token,
            )
        except Exception as exc:
            return (
                TxLineProbeStep(
                    name="guest_session",
                    method="POST",
                    path=path,
                    duration_ms=_elapsed_ms(started),
                    error=str(exc),
                ),
                None,
            )

    async def _get_json(
        self,
        name: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> tuple[TxLineProbeStep, Any]:
        started = time.perf_counter()
        try:
            response = await self.client.get(
                str(httpx.URL(self.base_url).join(path)),
                headers=headers,
                params=params or None,
            )
            duration_ms = _elapsed_ms(started)
            response.raise_for_status()
            payload = response.json()
            return (
                TxLineProbeStep(
                    name=name,
                    method="GET",
                    path=path,
                    duration_ms=duration_ms,
                    status_code=response.status_code,
                    item_count=count_records(payload),
                ),
                payload,
            )
        except Exception as exc:
            return (
                TxLineProbeStep(
                    name=name,
                    method="GET",
                    path=path,
                    duration_ms=_elapsed_ms(started),
                    error=str(exc),
                ),
                None,
            )

    def _data_headers(self, guest_jwt: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {guest_jwt}",
            "X-Api-Token": self.settings.txline_api_token or "",
            "Accept": "application/json",
        }


def first_fixture_id(payload: Any) -> str | None:
    """Return the first fixture ID found in a TxLINE fixtures payload."""

    for record in _records(payload):
        value = _fixture_id_from_mapping(record)
        if value is not None:
            return str(value)
    return None


def count_records(payload: Any) -> int:
    """Count top-level data records for TxLINE list/dictionary responses."""

    return len(_records(payload))


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("Data", "data", "Items", "items", "Events", "events", "Results", "results"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
            if isinstance(nested, dict):
                return _records(nested)
        return [payload]
    return []


def _fixture_id_from_mapping(record: dict[str, Any]) -> Any:
    for key in ("FixtureId", "fixtureId", "fixture_id", "EventId", "GameId"):
        value = record.get(key)
        if value is not None:
            return value
    return None


def _payload_for_normalizer(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {"Data": payload}


def _with_normalized_count(
    step: TxLineProbeStep,
    normalized: Iterable[object],
    fixture_id: str,
) -> TxLineProbeStep:
    return TxLineProbeStep(
        name=step.name,
        method=step.method,
        path=step.path,
        duration_ms=step.duration_ms,
        status_code=step.status_code,
        item_count=step.item_count,
        normalized_count=len(list(normalized)),
        fixture_id=fixture_id,
        skipped_reason=step.skipped_reason,
        error=step.error,
    )


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)
