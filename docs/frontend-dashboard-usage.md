# TxLINE Sentinel Frontend Dashboard Usage

This guide explains how to run and use the TxLINE Sentinel frontend dashboard for demos, testing, and backend validation.

The frontend is a Next.js app in `frontend/`. It connects to the FastAPI backend and makes the agent pipeline visible: backend status, data source mode, replay control, generated signals, explanations, evaluations, match state, odds movement, and SSE updates.

## Prerequisites

Run the backend first:

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Then run the frontend:

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Open:

```text
http://localhost:3000
```

The default frontend backend URL is:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Change `frontend/.env.local` if the backend runs elsewhere.

## Data Source Mode

The UI deliberately shows whether data is coming from:

- `LIVE`: TxLINE live SSE ingestion.
- `SNAPSHOT`: TxLINE snapshot polling.
- `REPLAY`: local replay scenarios running through the same backend detection pipeline.
- `DISABLED`: no live/snapshot ingestion configured.

You can see source mode in:

- the header `Data source` badge,
- the sidebar `Current data source` panel,
- the dashboard `Data Source Mode` card,
- every signal card via `source_mode`,
- match event timeline rows for odds and score events.

For hackathon demos, `REPLAY` is usually the safest path because it does not depend on an active live fixture.

## Main Pages

### Dashboard: `/`

Use this as the judge-facing home page.

It shows:

- backend health,
- app/runtime environment,
- configured ingestion mode,
- current effective source mode,
- TxLINE configured status,
- replay status,
- latest signals,
- high-confidence signal count,
- replay control panel,
- live SSE event timeline.

If the SSE stream disconnects, the page continues polling critical backend data.

### Replay: `/replay`

Use this page to drive the demo.

Available functions:

- list replay scenarios,
- build a TxLINE historical replay from start/end/fixture inputs,
- select a scenario,
- select speed multiplier: `1x`, `5x`, `10x`, `30x`, `60x`,
- choose whether to reset the database before starting,
- start replay,
- pause replay,
- resume replay,
- stop replay,
- reset replay state,
- inspect replay cursor, processed events, status, and latest generated signals.

Recommended demo scenario:

```text
argentina_france_no_score_sharp_move
```

Recommended speed:

```text
30x
```

The important demo point: replay mode is not fake UI data. Replay events go through the backend normalizer, market state, detector, scorer, explanation generator, evaluator, persistence layer, and SSE stream.

### TxLINE Historical Replay Builder

The `/replay` page includes `Build TxLINE Historical Replay`. This calls the backend historical replay builder without using the CLI.

Required fields:

- start UTC timestamp, for example `2026-07-09T12:00:00Z`,
- end UTC timestamp, for example `2026-07-09T12:30:00Z`.

Optional fields:

- fixture ID,
- scenario file name,
- display name,
- description.

After a successful build, the scenario list refreshes. Select the new scenario in the normal replay control panel and run it with the same replay controls.

Historical builds run as backend jobs. The panel shows:

- estimated 5-minute intervals and TxLINE requests before submit,
- queued/running/completed/failed status,
- completed interval count,
- odds, score, and total event counts,
- current historical interval being fetched,
- saved replay path after completion.

If you enter a large range, the request estimate is the first place to check. For example, `2026-06-01T12:00:00Z` to `2026-07-10T12:00:00Z` is 39 days, which means 11,232 historical intervals and 22,464 TxLINE requests because each interval fetches odds and scores.

### Signals: `/signals`

Use this page to inspect generated intelligence.

Available filters:

- minimum confidence,
- signal type,
- status,
- fixture ID.

Each signal card shows:

- source mode: `LIVE`, `SNAPSHOT`, or `REPLAY`,
- fixture ID,
- outcome name,
- signal type,
- direction,
- probability before and after,
- probability delta in percentage points,
- confidence score,
- explanation text,
- explanation source,
- signal status,
- 5/10/15 minute evaluation badges.

Open a signal card with `Inspect signal` for the technical detail view.

### Signal Detail: `/signals/[id]`

Use this page for technical judges.

It shows:

- complete signal metadata,
- source mode,
- confidence score,
- probability movement,
- explanation,
- confidence breakdown:
  - magnitude,
  - velocity,
  - volatility,
  - freshness,
  - context,
  - bookmaker agreement,
- evaluation table:
  - 5 minutes,
  - 10 minutes,
  - 15 minutes,
- score context,
- raw features,
- market key.

### Matches: `/matches`

Use this page to browse fixtures known to the backend.

It shows:

- fixture ID,
- participants,
- competition ID,
- start time,
- status,
- link to match state detail.

If no matches appear, run a replay scenario or enable TxLINE ingestion.

### Match Detail: `/matches/[fixtureId]`

Use this page to inspect one fixture.

It shows:

- latest score context,
- game state,
- latest action,
- current market snapshots,
- latest fixture signals,
- odds movement chart,
- odds and score event timeline.

Timeline rows include source mode badges so you can distinguish replay events from live or snapshot ingestion.

## Recommended Demo Flow

1. Start backend:

   ```powershell
   cd backend
   .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
   ```

2. Start frontend:

   ```powershell
   cd frontend
   npm run dev
   ```

3. Open:

   ```text
   http://localhost:3000
   ```

4. Go to `/replay`.

5. Select:

   ```text
   argentina_france_no_score_sharp_move
   ```

6. Select `30x`.

7. Enable reset database if you want a clean demo.

8. Click `Start replay`.

9. Watch the header/sidebar switch to `REPLAY`.

10. Go to `/signals`.

11. Open a generated signal.

12. Show explanation, confidence breakdown, and evaluation badges.

13. Go to `/matches/demo-arg-fra-001` to show match state and event timeline.

## Backend Endpoints Used

The frontend uses:

```text
GET  /health
GET  /api/settings/runtime

GET  /api/replay/scenarios
GET  /api/replay/status
POST /api/replay/start
POST /api/replay/pause
POST /api/replay/resume
POST /api/replay/stop
POST /api/replay/reset
POST /api/replay/historical/build
GET  /api/replay/historical/build/{job_id}
GET  /api/replay/historical/build/latest

GET  /api/signals
GET  /api/signals/latest
GET  /api/signals/high-confidence
GET  /api/signals/{signal_id}

GET  /api/matches
GET  /api/matches/{fixture_id}/state
GET  /api/matches/{fixture_id}/signals

GET  /api/events/odds
GET  /api/events/scores

GET  /api/stream
```

If an endpoint is temporarily unavailable, the UI shows an error or empty state instead of crashing.

## Build And Validation

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm run build
```

Expected result: all commands pass.

## Troubleshooting

### Backend unavailable

Check that FastAPI is running:

```text
http://localhost:8000/health
```

If the backend uses a different port, update:

```text
frontend/.env.local
```

### No signals

Start a replay scenario from `/replay`. Use reset database for a clean run.

### SSE disconnected

The dashboard still polls replay status and signals. SSE is useful for live timeline updates but is not required for basic dashboard operation.

### No odds chart

The selected fixture may not have odds events yet. Run a replay scenario or choose a fixture with odds events.

### Browser CORS error

The backend allows `localhost:3000` and `127.0.0.1:3000`. If you run the frontend on another port, update the backend CORS settings in `backend/app/main.py`.

## Known Limitations

- The dashboard is read-only except replay controls.
- It does not execute trades.
- It relies on the backend for all signal detection and evaluation.
- Live TxLINE quality depends on active fixtures and configured ingestion mode.
- Replay is the recommended deterministic demo mode.
