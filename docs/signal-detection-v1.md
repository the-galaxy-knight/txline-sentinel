# Signal Detection V1

Signal detection is deterministic and uses normalized implied probability events.

## Implied Probability

TxLINE odds payloads may provide `Pct` values or decimal prices. `Pct` values are normalized so `52.1` becomes `0.521`. If only decimal odds exist, probability is `1 / price`.

## Rolling Windows

For each market/outcome, the in-memory market state tracks recent events for up to 15 minutes. Keys include fixture, bookmaker, market type, period, parameters, and outcome. A consensus key omits bookmaker.

Tracked values include:

- current probability
- 60/180/300/600 second deltas
- velocity
- rolling volatility
- bookmaker count
- bookmaker dispersion
- same-direction bookmaker count

## Signal Types

- `sharp_movement`: absolute 5-minute move of at least 5 percentage points.
- `fast_velocity_movement`: 60-second move of at least 2.5 percentage points, or high z-score.
- `no_score_market_pressure`: 5-minute move of at least 4 percentage points with no recent goal-like event.
- `post_event_reaction`: recent goal/card context plus a 3-minute move of at least 3 percentage points.
- `bookmaker_divergence`: one bookmaker deviates from consensus by at least 3.5 percentage points.

## Confidence Scoring

Signals are scored from 0 to 100 using magnitude, velocity, bookmaker consistency, context, freshness, cleanliness, and volatility penalty.

## Signal Math

The numeric confidence score is deterministic. The LLM, when enabled, may rewrite the explanation text, but it does not decide the signal type, thresholds, scoring inputs, or final confidence.

The backend source of truth is `backend/app/signals/scoring.py`.

Confidence is calculated as:

```text
confidence =
  25 * magnitude_score
+ 20 * velocity_score
+ 20 * bookmaker_agreement_score
+ 15 * context_score
+ 10 * freshness_score
+ 10 * cleanliness_score
- volatility_penalty
```

The result is clamped to the `0..100` range and rounded to two decimals.

Scoring inputs:

- `magnitude_score`: absolute probability movement scaled against an 8 percentage point reference move. A move of at least 8 percentage points receives `1.00`.
- `velocity_score`: recent probability movement scaled against a 4 percentage point short-window move. A recent move of at least 4 percentage points receives `1.00`.
- `bookmaker_agreement_score`: share of bookmakers moving in the same direction. If only one bookmaker is available, the MVP fallback is `0.60`.
- `context_score`: deterministic weight based on signal type:
  - `post_event_reaction`: `1.00`
  - `no_score_market_pressure`: `0.85`
  - `sharp_movement`: `0.65`
  - `bookmaker_divergence`: `0.45`
  - default, including `fast_velocity_movement`: `0.50`
- `freshness_score`: currently fixed at `1.00` because signals are emitted as events are processed.
- `cleanliness_score`: fraction of required data fields present: fixture ID, outcome name, probability after, and signal timestamp.
- `volatility_penalty`: subtracts up to 15 points when rolling market volatility is high.

Example for a post-goal reaction:

```text
Magnitude              1.00 -> +25
Velocity               1.00 -> +20
Bookmaker agreement    0.60 -> +12
Context                1.00 -> +15
Freshness              1.00 -> +10
Cleanliness            1.00 -> +10
Volatility penalty     0.00 ->  -0

Confidence = 92/100
```

This design keeps the numbers auditable and reproducible. The agent can explain and monitor the score, but the score itself comes from market features rather than free-form language generation.

## Deduplication

A new signal is suppressed if a matching fixture, market, outcome, type, and direction was created within 3 minutes and the new confidence is not at least 10 points higher.

## Predictiveness Evaluation

Each signal receives pending 5, 10, and 15 minute evaluations. A signal is confirmed if the probability continues in the signal direction by at least 0.5 percentage points.
