# Replay Mode

Replay mode exists so judges can see TxLINE Sentinel generate real signals when no live World Cup match is happening.

## Scenario Format

Scenarios are JSON files in `backend/app/data/replay_scenarios`:

```json
{
  "name": "Argentina vs France - sharp no-score movement",
  "description": "Demo scenario where Argentina probability moves sharply without a score change.",
  "fixture_id": "demo-arg-fra-001",
  "events": [
    {
      "offset_ms": 0,
      "event_type": "score",
      "payload": {}
    },
    {
      "offset_ms": 1000,
      "event_type": "odds",
      "payload": {}
    }
  ]
}
```

Supported event types are `score` and `odds`.

## How Replay Runs

The replay manager schedules events by `offset_ms`, applies the speed multiplier, normalizes payloads, and sends them to the same event processor used by live and snapshot ingestion.

## API Commands

```bash
curl http://localhost:8000/api/replay/scenarios
curl -X POST http://localhost:8000/api/replay/start \
  -H "Content-Type: application/json" \
  -d '{"scenario_name":"argentina_france_no_score_sharp_move","speed_multiplier":30,"reset_database":true}'
curl http://localhost:8000/api/replay/status
curl http://localhost:8000/api/signals
```

Only one replay run is active at a time.
