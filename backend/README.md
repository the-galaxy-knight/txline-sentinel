# TxLINE Sentinel Backend

Backend API for **TxLINE Sentinel: Autonomous World Cup Odds Intelligence Agent**.

TxLINE Sentinel monitors World Cup odds and score events, detects meaningful probability movements, explains why they matter, and tracks whether signals were predictive. It works with live TxLINE credentials when available and with replay scenarios for hackathon judging.

## Architecture Overview

- **FastAPI** exposes REST and SSE endpoints.
- **SQLAlchemy + SQLite** stores fixtures, events, signals, evaluations, replay runs, offsets, and alert records.
- **TxLINE client** supports REST snapshots and SSE streams.
- **Event processor** is the shared pipeline for live, snapshot, and replay events.
- **Market state** tracks rolling odds windows and bookmaker consensus.
- **Signal engine** deterministically detects and scores signals.
- **Explanation layer** uses template fallback and optional OpenAI rewriting.
- **Telegram alerts** are optional and threshold-based.
- **Replay mode** runs local JSON scenarios through the same event processor as live ingestion.

## Module Map

- `app/main.py`: FastAPI app lifecycle and router registration.
- `app/config.py`: safe environment-driven settings.
- `app/db.py`: ORM models and local schema setup.
- `app/txline/`: TxLINE auth, REST/SSE client, SSE parser.
- `app/ingestion/`: event processor, live/snapshot/replay runners, dashboard stream.
- `app/market/`: implied probability and rolling market/score state.
- `app/signals/`: detection, scoring, deduplication, evaluation.
- `app/explanation/`: template and optional LLM explanations.
- `app/alerts/`: Telegram formatting and dispatch.
- `app/api/`: REST and SSE route modules.
- `app/data/replay_scenarios/`: demo replay JSON files.

## Environment Variables

Start from `.env.example`.

Core:

```text
APP_ENV=local
DATABASE_URL=sqlite:///./txline_sentinel.db
INGESTION_MODE=disabled
REPLAY_SCENARIOS_DIR=app/data/replay_scenarios
```

TxLINE:

```text
TXLINE_BASE_URL=https://txline-dev.txodds.com
TXLINE_GUEST_JWT=
TXLINE_API_TOKEN=
TXLINE_FIXTURES_SNAPSHOT_PATH=/api/fixtures/snapshot
TXLINE_ODDS_SNAPSHOT_PATH=/api/odds/snapshot/<fixture_id>
TXLINE_SCORES_SNAPSHOT_PATH=/api/scores/snapshot/<fixture_id>
TXLINE_ODDS_STREAM_PATH=/api/odds/stream
TXLINE_SCORES_STREAM_PATH=/api/scores/stream
LIVE_RECONNECT_INITIAL_SECONDS=1
LIVE_RECONNECT_MAX_SECONDS=60
LIVE_STREAM_HEARTBEAT_TIMEOUT_SECONDS=90
```

Optional LLM:

```text
LLM_ENABLED=false
OPENAI_API_KEY=
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=8
```

Optional Telegram:

```text
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_MIN_CONFIDENCE=80
```

Secrets are never required for tests or replay demos.

## Local Setup

Unix/macOS:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Run Locally

```bash
uvicorn app.main:app --reload
```

Open:

- `GET /health`
- `GET /docs`
- `GET /api/settings/runtime`

## Tests And Lint

```bash
pytest
ruff check . --no-cache
```

PowerShell:

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check . --no-cache
```

## Replay Mode

Replay mode is the judge/demo path and needs no TxLINE credentials.

```bash
curl http://localhost:8000/api/replay/scenarios
curl -X POST http://localhost:8000/api/replay/start \
  -H "Content-Type: application/json" \
  -d '{"scenario_name":"argentina_france_no_score_sharp_move","speed_multiplier":30,"reset_database":true}'
curl http://localhost:8000/api/signals
```

PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/replay/scenarios
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/replay/start `
  -ContentType "application/json" `
  -Body '{"scenario_name":"argentina_france_no_score_sharp_move","speed_multiplier":30,"reset_database":true}'
Invoke-RestMethod http://localhost:8000/api/signals
```

Included scenarios:

- `argentina_france_no_score_sharp_move`
- `brazil_germany_post_goal_reaction`
- `spain_portugal_bookmaker_divergence`

## TxLINE Historical Replay

TxLINE historical odds and score interval endpoints can be converted into local replay JSON files. This gives the demo real TxLINE-sourced historical data while keeping the deterministic replay UX.

Generate a replay from historical 5-minute intervals:

```powershell
cd backend
.venv\Scripts\python -m app.cli build-historical-replay `
  --start 2026-07-09T12:00:00Z `
  --end 2026-07-09T12:30:00Z `
  --fixture-id 18143850 `
  --scenario-name txline_fixture_18143850_history `
  --display-name "TxLINE historical fixture 18143850"
```

The command calls:

```text
GET /api/odds/updates/{epochDay}/{hourOfDay}/{interval}
GET /api/scores/updates/{epochDay}/{hourOfDay}/{interval}
```

It writes a replay file under `REPLAY_SCENARIOS_DIR` with `source: txline_historical`. Then run it like any other replay:

```powershell
.venv\Scripts\python -m app.cli run-replay txline_fixture_18143850_history --speed 30 --reset-database
```

The same builder is also exposed to the frontend as a background job:

```text
POST /api/replay/historical/build
GET  /api/replay/historical/build/{job_id}
GET  /api/replay/historical/build/latest
```

`POST /api/replay/historical/build` returns `202 Accepted` with a `job_id`. Poll the job endpoint to see `status`, `intervals_completed`, `intervals_requested`, odds/score event counts, current interval, saved path, and any error. The frontend `/replay` page does this automatically and also estimates TxLINE request volume before starting. A 39-day range is 11,232 five-minute intervals and 22,464 TxLINE historical requests.

Official TxLINE references:

- World Cup free tier: https://txline.txodds.com/documentation/worldcup
- Historical odds interval: https://txline.txodds.com/api-reference/odds/get-a-json-array-of-all-odd-updates-from-a-specific-historical-5-minute-interval
- Historical scores interval: https://txline.txodds.com/api-reference/scores/get-a-json-array-of-all-score-updates-from-a-specific-historical-5-minute-interval-no-live-data-is-returned

## Snapshot Mode

Set:

```text
INGESTION_MODE=snapshot
TXLINE_BASE_URL=...
TXLINE_GUEST_JWT=...
TXLINE_API_TOKEN=...
TXLINE_FIXTURES_SNAPSHOT_PATH=...
TXLINE_ODDS_SNAPSHOT_PATH=...
TXLINE_SCORES_SNAPSHOT_PATH=...
```

The runner polls configured snapshots, deduplicates events, logs stats, and keeps the API running through temporary errors.

## Live TxLINE Mode

Set:

```text
INGESTION_MODE=live
TXLINE_BASE_URL=...
TXLINE_GUEST_JWT=...
TXLINE_API_TOKEN=...
TXLINE_ODDS_STREAM_PATH=...
TXLINE_SCORES_STREAM_PATH=...
```

Odds and score streams run independently, reconnect with exponential backoff, persist offsets, resume with `Last-Event-ID`, and expose degraded state without crashing the app.

## Demo CLI

```bash
python -m app.cli list-scenarios
python -m app.cli reset-db
python -m app.cli seed-demo
python -m app.cli run-replay argentina_france_no_score_sharp_move --speed 30 --reset-database
python -m app.cli build-historical-replay --start 2026-07-09T12:00:00Z --end 2026-07-09T12:30:00Z --fixture-id 18143850
python -m app.cli txline-probe
```

`txline-probe` measures `POST /auth/guest/start` without secrets. When `TXLINE_API_TOKEN` is configured, it also measures fixtures, odds, and scores snapshots and reports normalized event counts.

`build-historical-replay` requires configured `TXLINE_BASE_URL`, `TXLINE_GUEST_JWT`, and `TXLINE_API_TOKEN`. It fetches real TxLINE historical odds/scores intervals and writes a local replay scenario.

## TxLINE Devnet Activation

From the repo root:

```powershell
npm install @solana/web3.js @solana/spl-token tweetnacl
node scripts/txline-devnet-free-tier.mjs --confirm-devnet
```

The script uses TxLINE devnet, subscribes to the documented free tier service level `1`, activates API access, and updates `backend/.env`.

## Docker

From the repo root:

```bash
docker build -t txline-sentinel-backend ./backend
docker run --rm -p 8000:8000 txline-sentinel-backend
docker compose up --build
```

## Makefile

From the repo root:

```bash
make install
make dev
make test
make lint
make replay
make docker-build
make docker-run
```

Windows equivalents are the PowerShell commands shown above.

## API Endpoints

Health/settings:

- `GET /health`
- `GET /api/settings`
- `GET /api/settings/runtime`

Fixtures/matches:

- `GET /api/fixtures`
- `GET /api/fixtures/{fixture_id}`
- `GET /api/matches`
- `GET /api/matches/{fixture_id}`
- `GET /api/matches/{fixture_id}/state`
- `GET /api/matches/{fixture_id}/signals`

Events:

- `GET /api/events/odds`
- `GET /api/events/scores`

Signals:

- `GET /api/signals`
- `GET /api/signals?fixture_id=...&signal_type=...&status=...&min_confidence=80`
- `GET /api/signals/latest`
- `GET /api/signals/high-confidence`
- `GET /api/signals/{signal_id}`

Replay:

- `GET /api/replay/scenarios`
- `GET /api/replay/status`
- `POST /api/replay/start`
- `POST /api/replay/pause`
- `POST /api/replay/resume`
- `POST /api/replay/stop`
- `POST /api/replay/reset`
- `POST /api/replay/historical/build`
- `GET /api/replay/historical/build/{job_id}`
- `GET /api/replay/historical/build/latest`

Stream/demo:

- `GET /api/stream`
- `POST /api/demo/reset` local only

## Judge Demo Flow

1. Start API: `uvicorn app.main:app --reload`
2. Show health: `curl http://localhost:8000/health`
3. Show runtime settings: `curl http://localhost:8000/api/settings/runtime`
4. Start replay with `argentina_france_no_score_sharp_move`.
5. Show `GET /api/signals/high-confidence`.
6. Show `GET /api/matches/demo-arg-fra-001/state`.
7. Explain that live mode uses the same event processor as replay.

## LLM Explanations

Template explanations always work. Optional OpenAI rewriting:

```bash
pip install -e ".[llm]"
```

Set `LLM_ENABLED=true` and `OPENAI_API_KEY`. If the SDK, timeout, or validation fails, the backend uses deterministic template fallback.

## Telegram Alerts

Set `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `TELEGRAM_MIN_CONFIDENCE`. Alert failures are stored and logged without crashing the app.

## Local Schema Note

This MVP creates tables at startup and includes lightweight SQLite column/index checks for local development. If local schema changes cause trouble, deleting `txline_sentinel.db` and restarting is acceptable.

## Known Limitations

- Signal thresholds are v1 heuristics.
- SQLite is the MVP database.
- SSE dashboard stream is in-memory.
- Replay supports one active run at a time.
- No real betting or trading execution is included.

## Roadmap

- PostgreSQL and migrations.
- Frontend dashboard.
- More TxLINE market types and richer score context.
- Signal tuning with real match data.
- Auth for public deployments.
