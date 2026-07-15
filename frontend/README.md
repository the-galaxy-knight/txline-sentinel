# TxLINE Sentinel Frontend

Next.js dashboard for the TxLINE Sentinel backend. It is built for the hackathon demo flow: inspect backend health, run replay scenarios, watch signals appear, read explanations, and review predictiveness tracking.

For a full page-by-page usage guide, see [frontend-dashboard-usage.md](../docs/frontend-dashboard-usage.md).

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Environment

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The FastAPI backend must be running at that URL unless you change the environment variable.

## Pages

- `/` dashboard home with health, runtime, source mode, latest signals, replay controls, and SSE timeline.
- `/replay` scenario selector and replay controls.
- `/signals` filterable signal feed.
- `/signals/[id]` technical signal detail with scoring and evaluations.
- `/matches` fixture list.
- `/matches/[fixtureId]` match state, odds chart, event timeline, and fixture signals.

## Data Source Mode

The UI clearly surfaces source mode in two places:

- Header/sidebar: current effective mode from runtime settings and replay status.
- Signal/event cards: per-record `source_mode` badge showing `LIVE`, `SNAPSHOT`, or `REPLAY`.

## Demo Flow

1. Start backend:

   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. Start frontend:

   ```bash
   cd frontend
   npm run dev
   ```

3. Open `/replay`, select `argentina_france_no_score_sharp_move`, and start at `30x`.
4. Open `/signals` and inspect generated signal cards.
5. Open a signal detail page to show confidence breakdown and evaluations.

## Troubleshooting

- If the dashboard shows backend unavailable, confirm FastAPI is running on `http://localhost:8000`.
- If SSE disconnects, the UI keeps polling health, replay status, and signals.
- If no signals appear, run a replay scenario with database reset enabled.
