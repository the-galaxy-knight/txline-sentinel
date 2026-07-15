from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.db import SessionLocal, init_db
from app.demo import reset_demo_data
from app.ingestion.replay_runner import list_replay_scenarios, replay_manager
from app.txline.historical_replay import (
    HistoricalReplayBuildResult,
    build_historical_replay,
)
from app.txline.performance import TxLinePerformanceProbe, TxLineProbeResult


def main() -> None:
    parser = argparse.ArgumentParser(description="TxLINE Sentinel backend utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "reset-db", help="Clear demo events, signals, evaluations, and replay runs."
    )
    subparsers.add_parser("seed-demo", help="Reset and run the default Argentina/France replay.")
    subparsers.add_parser("list-scenarios", help="List replay scenarios.")
    replay_parser = subparsers.add_parser("run-replay", help="Run a replay scenario.")
    replay_parser.add_argument("scenario_name")
    replay_parser.add_argument("--speed", type=float, default=30.0)
    replay_parser.add_argument("--reset-database", action="store_true")
    probe_parser = subparsers.add_parser(
        "txline-probe", help="Measure TxLINE guest auth and configured data endpoint latency."
    )
    probe_parser.add_argument("--base-url", help="Override TXLINE_BASE_URL for the probe.")
    probe_parser.add_argument("--fixture-id", help="Fixture ID for odds/scores snapshot probes.")
    probe_parser.add_argument(
        "--competition-id", type=int, help="Filter fixtures by competition ID."
    )
    probe_parser.add_argument(
        "--start-epoch-day", type=int, help="Filter fixtures from an epoch day."
    )
    probe_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    historical_parser = subparsers.add_parser(
        "build-historical-replay",
        help="Fetch TxLINE historical odds/scores intervals and save a replay scenario.",
    )
    historical_parser.add_argument(
        "--start",
        required=True,
        type=_parse_datetime_arg,
        help="Inclusive UTC start time, for example 2026-07-09T12:00:00Z.",
    )
    historical_parser.add_argument(
        "--end",
        required=True,
        type=_parse_datetime_arg,
        help="Exclusive UTC end time, for example 2026-07-09T12:30:00Z.",
    )
    historical_parser.add_argument("--fixture-id", help="Optional TxLINE fixture ID filter.")
    historical_parser.add_argument(
        "--scenario-name",
        help="Output scenario file stem. Defaults to a generated TxLINE historical name.",
    )
    historical_parser.add_argument("--display-name", help="Human-readable scenario name.")
    historical_parser.add_argument("--description", help="Replay description metadata.")
    historical_parser.add_argument(
        "--output-dir",
        help="Output directory. Defaults to REPLAY_SCENARIOS_DIR.",
    )
    historical_parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON."
    )

    args = parser.parse_args()
    if args.command == "reset-db":
        init_db()
        with SessionLocal() as db:
            reset_demo_data(db)
        print("Demo database tables reset.")
    elif args.command == "seed-demo":
        init_db()
        asyncio.run(_run_replay("argentina_france_no_score_sharp_move", 1_000_000, True))
    elif args.command == "list-scenarios":
        for scenario in list_replay_scenarios():
            print(f"{scenario.name}\t{scenario.events_total} events\t{scenario.description or ''}")
    elif args.command == "run-replay":
        init_db()
        asyncio.run(_run_replay(args.scenario_name, args.speed, args.reset_database))
    elif args.command == "txline-probe":
        result = asyncio.run(
            _run_txline_probe(
                base_url=args.base_url,
                fixture_id=args.fixture_id,
                competition_id=args.competition_id,
                start_epoch_day=args.start_epoch_day,
            )
        )
        if args.json:
            print(json.dumps(_probe_to_dict(result), indent=2))
        else:
            _print_probe_result(result)
    elif args.command == "build-historical-replay":
        result = asyncio.run(
            build_historical_replay(
                start=args.start,
                end=args.end,
                fixture_id=args.fixture_id,
                scenario_name=args.scenario_name,
                display_name=args.display_name,
                description=args.description,
                output_dir=Path(args.output_dir) if args.output_dir else None,
            )
        )
        if args.json:
            print(json.dumps(_historical_result_to_dict(result), indent=2))
        else:
            _print_historical_result(result)


async def _run_replay(scenario_name: str, speed: float, reset_database: bool) -> None:
    run = await replay_manager.start(
        scenario_name=scenario_name,
        speed_multiplier=speed,
        reset_database=reset_database,
    )
    if replay_manager.current_task:
        await replay_manager.current_task
    print(f"Replay {run.scenario_name} completed.")


async def _run_txline_probe(
    base_url: str | None,
    fixture_id: str | None,
    competition_id: int | None,
    start_epoch_day: int | None,
) -> TxLineProbeResult:
    probe = TxLinePerformanceProbe(base_url=base_url)
    try:
        return await probe.run(
            fixture_id=fixture_id,
            competition_id=competition_id,
            start_epoch_day=start_epoch_day,
        )
    finally:
        await probe.aclose()


def _print_probe_result(result: TxLineProbeResult) -> None:
    print(f"TxLINE base URL: {result.base_url}")
    print(f"Guest JWT source: {result.guest_jwt_source or 'none'}")
    print(f"API token configured: {result.api_token_configured}")
    print(f"Fixture ID: {result.fixture_id or 'none'}")
    print()
    for step in result.steps:
        status = "SKIP" if step.skipped_reason else "ERR" if step.error else "OK"
        duration = f"{step.duration_ms:.2f} ms" if step.duration_ms is not None else "-"
        http_status = str(step.status_code) if step.status_code is not None else "-"
        count = str(step.item_count) if step.item_count is not None else "-"
        normalized = str(step.normalized_count) if step.normalized_count is not None else "-"
        detail = step.skipped_reason or step.error or ""
        print(
            f"{status:4} {step.name:18} {step.method:4} {step.path:36} "
            f"http={http_status:3} time={duration:>10} items={count:>4} "
            f"normalized={normalized:>4} {detail}"
        )


def _probe_to_dict(result: TxLineProbeResult) -> dict:
    return {
        "base_url": result.base_url,
        "guest_jwt_source": result.guest_jwt_source,
        "api_token_configured": result.api_token_configured,
        "fixture_id": result.fixture_id,
        "steps": [
            {
                "name": step.name,
                "method": step.method,
                "path": step.path,
                "duration_ms": step.duration_ms,
                "status_code": step.status_code,
                "item_count": step.item_count,
                "normalized_count": step.normalized_count,
                "fixture_id": step.fixture_id,
                "skipped_reason": step.skipped_reason,
                "error": step.error,
            }
            for step in result.steps
        ],
    }


def _print_historical_result(result: HistoricalReplayBuildResult) -> None:
    print("TxLINE historical replay generated.")
    print(f"Scenario: {result.scenario_name}")
    print(f"Path: {result.path}")
    print(f"Intervals requested: {result.intervals_requested}")
    print(f"Odds events: {result.odds_events}")
    print(f"Score events: {result.score_events}")
    print(f"Total events: {result.events_total}")


def _historical_result_to_dict(result: HistoricalReplayBuildResult) -> dict:
    return {
        "scenario_name": result.scenario_name,
        "path": str(result.path),
        "intervals_requested": result.intervals_requested,
        "odds_events": result.odds_events,
        "score_events": result.score_events,
        "events_total": result.events_total,
    }


def _parse_datetime_arg(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("Datetime argument cannot be empty.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid datetime '{value}'. Use ISO format, for example 2026-07-09T12:00:00Z."
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    main()
