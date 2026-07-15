# TxLINE Integration

TxLINE integration is optional for local demo mode.

## World Cup Free Tier Flow

The documented World Cup flow is:

1. Choose one network and keep it consistent for Solana RPC, TxLINE program ID, guest JWT, and activation endpoint.
2. Subscribe on-chain to the free tier. Devnet documents service level `1`. Mainnet documents service level `1` for 60-second delayed World Cup and International Friendlies data and service level `12` for real-time data.
3. Start a guest session with `POST /auth/guest/start`. The response contains a guest JWT that expires after 30 days.
4. Activate API access with `POST /api/token/activate`, passing the subscription transaction signature, signed activation message, and selected leagues.
5. Call data endpoints with both `Authorization: Bearer <guest_jwt>` and `X-Api-Token: <api_token>`.

## Environment Variables

```text
TXLINE_BASE_URL=https://txline-dev.txodds.com
TXLINE_GUEST_JWT=
TXLINE_API_TOKEN=
TXLINE_FIXTURES_SNAPSHOT_PATH=/api/fixtures/snapshot
TXLINE_ODDS_SNAPSHOT_PATH=/api/odds/snapshot/<fixture_id>
TXLINE_SCORES_SNAPSHOT_PATH=/api/scores/snapshot/<fixture_id>
TXLINE_ODDS_STREAM_PATH=/api/odds/stream
TXLINE_SCORES_STREAM_PATH=/api/scores/stream
INGESTION_MODE=disabled
```

Do not commit real secrets.

Use `https://txline.txodds.com` only when the subscription transaction was made on mainnet.

## Devnet Activation Script

The devnet script subscribes to the documented free tier, activates API access, and writes `TXLINE_GUEST_JWT` plus `TXLINE_API_TOKEN` to `backend/.env`.

```powershell
npm install @solana/web3.js @solana/spl-token tweetnacl
node scripts/txline-devnet-free-tier.mjs --confirm-devnet
```

By default it uses `~/.config/solana/id.json`. To use a specific keypair:

```powershell
node scripts/txline-devnet-free-tier.mjs --keypair C:\path\to\id.json --confirm-devnet
```

If the wallet has no devnet SOL:

```powershell
solana airdrop 1 --url devnet
```

## Authentication

The client sends:

- `Authorization: Bearer <guest_jwt>` when configured.
- `X-Api-Token: <api_token>` when configured.

The backend also has a read-only probe command:

```powershell
cd backend
.venv\Scripts\python -m app.cli txline-probe
```

With no API token, this measures `POST /auth/guest/start` and skips protected data endpoints. With `TXLINE_API_TOKEN` configured, it measures:

- `GET /api/fixtures/snapshot`
- `GET /api/odds/snapshot/{fixtureId}`
- `GET /api/scores/snapshot/{fixtureId}`

Optional filters:

```powershell
.venv\Scripts\python -m app.cli txline-probe --competition-id 500005
.venv\Scripts\python -m app.cli txline-probe --fixture-id 17271370
.venv\Scripts\python -m app.cli txline-probe --json
```

## Snapshot Mode

`INGESTION_MODE=snapshot` polls configured fixture, odds, and score snapshot paths. Temporary upstream failures are logged and reflected in runtime status while the app stays up.

TxLINE odds and score snapshots are fixture-scoped. For the current MVP snapshot runner, configure `TXLINE_ODDS_SNAPSHOT_PATH` and `TXLINE_SCORES_SNAPSHOT_PATH` with a concrete fixture ID when testing snapshot ingestion. The performance probe can discover a fixture ID from `/api/fixtures/snapshot` automatically.

## Live SSE Mode

`INGESTION_MODE=live` starts independent odds and score stream tasks. Each stream:

- reconnects with exponential backoff
- persists offsets in `ingestion_offsets`
- resumes with `Last-Event-ID`
- uses heartbeat timeout to detect stalled streams
- reports degraded state without crashing the app

## Graceful Degradation

When TxLINE credentials or paths are missing, ingestion does not start, but the API remains available. Replay mode still works.
