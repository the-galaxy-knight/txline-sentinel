# TxLINE Sentinel Backend Architecture

TxLINE Sentinel is a FastAPI backend that turns TxLINE World Cup odds and score events into deterministic market intelligence signals.

## Runtime Shape

- **FastAPI API**: health, fixtures, events, signals, replay, stream, settings, demo, and match-state endpoints.
- **SQLite database**: local MVP storage for fixtures, normalized events, signals, evaluations, replay runs, offsets, and Telegram alert results.
- **Ingestion modes**:
  - `disabled`: safe default.
  - `snapshot`: polls configured TxLINE REST snapshot paths.
  - `live`: consumes configured TxLINE SSE streams.
  - `replay`: API-triggered local scenario playback for judging/demo.
- **Event processor**: one shared pipeline for live, snapshot, and replay events.

## Event Processor

`app/ingestion/event_processor.py` centralizes backend behavior:

1. Persist normalized odds or score events with duplicate protection.
2. Update in-memory market or score state.
3. Run deterministic signal detection for odds events.
4. Deduplicate generated signals.
5. Generate template or optional LLM explanations.
6. Persist signals and pending evaluations.
7. Dispatch optional Telegram alerts.
8. Publish dashboard SSE events.

## Signal Engine

The LLM never decides whether a signal exists. `app/signals/detector.py` uses deterministic market snapshots and score context to create signal candidates. `app/signals/scoring.py` assigns confidence scores. `app/signals/evaluator.py` tracks follow-through.

## Replay Mode

Replay scenarios live in `backend/app/data/replay_scenarios`. The replay manager plays JSON events through the same event processor used by live ingestion. This makes demos meaningful even when no TxLINE match is live.

## External Integrations

- **TxLINE**: configured by base URL, auth credentials, snapshot paths, and SSE paths.
- **OpenAI**: optional explanation rewriting only.
- **Telegram**: optional alerts for high-confidence signals.

All integrations are optional. The backend boots and tests pass without external credentials.
