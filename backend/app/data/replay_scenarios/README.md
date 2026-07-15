# Replay Scenarios

Place replay scenario JSON files in this directory.

The current backend lists scenarios from `*.json` files and reads optional metadata:

```json
{
  "name": "sample-world-cup-swing",
  "description": "Demo scenario for odds and score movement.",
  "events": []
}
```

Supported event fields:

- `offset_ms`: replay offset from scenario start.
- `event_type`: `odds` or `score`.
- `payload`: raw TxLINE-style payload.

Included demos:

- `argentina_france_no_score_sharp_move.json`
- `brazil_germany_post_goal_reaction.json`
- `spain_portugal_bookmaker_divergence.json`

## Historical Replays

TxLINE provides historical replay/data endpoints for past match analysis,
including odds and score updates by historical 5-minute intervals.

The current JSON files in this folder are TxLINE-style demo scenarios. They are
not automatically downloaded historical TxLINE intervals. If a scenario is
generated from TxLINE historical endpoints, label it as a TxLINE historical
replay and preserve fixture IDs, message IDs, timestamps, bookmakers, prices,
and percentages.

Generate a TxLINE historical replay from the backend directory:

```powershell
.venv\Scripts\python -m app.cli build-historical-replay `
  --start 2026-07-09T12:00:00Z `
  --end 2026-07-09T12:30:00Z `
  --fixture-id 18143850
```

Use the label historical-inspired synthetic replay only when the match pattern
is inspired by a previous match but the odds path is manually authored.

Good replay patterns:

- late equalizer causing a rapid probability reversal
- red card causing one bookmaker to move before consensus
- penalty or disallowed goal causing a short-lived overreaction
- long no-score period with sharp market pressure
- post-goal reaction unfolding across multiple odds updates

Use synthetic fixture IDs such as `demo-arg-ned-2022-inspired`, include score
events when context matters, and ensure at least one odds event crosses the
documented thresholds in `docs/signal-detection-v1.md`.
