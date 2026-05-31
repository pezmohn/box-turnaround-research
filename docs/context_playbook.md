# Box Context Playbook

This playbook converts the Phase 1-3 research into a discretionary tape-reading guide.
It is not an entry model, not a stop model, and not a PnL claim.

## Scope

Use confirmed 5-minute box events as a market-state classifier:

- Is the current same-direction box streak still likely to continue?
- Is the streak showing structural failure?
- Has price reclaimed a meaningful level after the failure?
- Is the context worth watching, or should it be ignored?

Do not use this document to automate trades. The current research only validates context labels and forward structure.

## Core Read

Long same-color box streaks do not reverse by themselves.

In the validation split, the base rate for `streak_length >= 5` was:

| Context | Validation n | P(opposite within 3) | Reversal followthrough | Continuation |
| --- | ---: | ---: | ---: | ---: |
| All 5+ streaks | 18,746 | 42.4% | 28.4% | 41.7% |

That means a long red or green streak alone is not a reversal setup. It is often still a continuation state.

The context becomes interesting only when the streak also shows failure and structural reclaim.

## Must-Watch Contexts

### 1. Hard Confirmation: Extension Failure + VWAP Reclaim

Pattern:

```text
streak_length >= 5
extension_failure_3 = true
vwap_reclaim_3 = true
```

Validation result:

| Pattern | Validation n | P(opposite within 3) | Lift vs 5+ base | Reversal followthrough | Continuation |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5+ streak + extension failure + VWAP reclaim | 1,443 | 96.5% | +54.2pp | 86.1% | 2.3% |

Interpretation:

- This is the strongest context transition in the current dataset.
- It usually means the old streak has already lost control.
- Treat it as a hard confirmation filter, not as an early reversal predictor.

Caveat:

- VWAP reclaim is close to the outcome itself. Do not claim "edge" from this alone.
- The useful claim is that after extension failure, a VWAP reclaim marks a confirmed context shift.

### 2. Broad Confirmation: Extension Failure + Prior Box Midpoint Break

Pattern:

```text
streak_length >= 5
extension_failure_3 = true
midpoint_break_3 = true
```

Validation result:

| Pattern | Validation n | P(opposite within 3) | Lift vs 5+ base | Reversal followthrough | Continuation |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5+ streak + extension failure + midpoint break | 9,274 | 53.7% | +11.3pp | 47.4% | 24.1% |

Interpretation:

- This is less extreme than VWAP reclaim, but much broader and less outcome-tautological.
- It is a useful watchlist filter: the streak is no longer clean continuation, but it is not automatically a reversal.
- This should be the main "early structural warning" context.

### 3. Highest Conviction: Extension Failure + VWAP Reclaim + Midpoint Break

Pattern:

```text
streak_length >= 5
extension_failure_3 = true
vwap_reclaim_3 = true
midpoint_break_3 = true
```

Validation result:

| Pattern | Validation n | P(opposite within 3) | Lift vs 5+ base | Reversal followthrough | Continuation |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5+ streak + extension failure + VWAP + midpoint | 1,392 | 96.8% | +54.5pp | 86.4% | 2.1% |

Interpretation:

- Strongest confirmed transition state.
- By the time this is visible, the move may already be underway.
- Best used as "do not fight the transition" context, not as proof of a clean late entry.

## Session Notes

Power hour improves the broad failure/reclaim context.

| Pattern | Validation n | P(opposite within 3) | Lift vs 5+ base | Reversal followthrough | Continuation |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5+ extension failure + VWAP or midpoint, power hour | 1,615 | 57.8% | +15.4pp | 52.1% | 16.1% |
| 5+ extension failure + VWAP or midpoint, morning trend | 2,139 | 46.7% | +4.3pp | 42.7% | 25.9% |

Interpretation:

- Morning trend is more continuation-heavy.
- Power hour is more responsive to failure/reclaim context.
- Do not apply one session's read blindly to another.

## Ignore Zones

### Long Streak Alone

Ignore:

```text
streak_length >= 5
no extension failure
no midpoint break
no VWAP reclaim
```

Reason:

- Base 5+ streaks still have high continuation rate.
- The old direction is not dead just because the streak is long.

### Extension Failure Without Structural Reclaim

Extension failure helps, but alone it is not enough.

For 5+ streaks with `extension_failure_3 = true`, P(opposite within 3) was 49.0% in the full sample. That is better than failed-extension false, but still not clean enough for a standalone read.

Use it as a warning light, not as confirmation.

### Range Shrinking

Current range-shrinking definition is not a clean separator.

Reason:

- It barely changes the forward probabilities.
- It may need a better definition later, but it should not drive decisions now.

### Current In-Play Label

The current in-play label is not a booster.

For 5+ streaks:

| In-play | n | P(opposite within 3) | Reversal followthrough | Continuation |
| --- | ---: | ---: | ---: | ---: |
| False | 59,354 | 42.9% | 28.5% | 42.1% |
| True | 2,373 | 39.9% | 28.2% | 44.5% |

Interpretation:

- The first in-play definition is useful as a day label, but not as a turnaround filter.
- Do not optimize it yet. First improve the label definition or add news/relative liquidity context.

## Practical Tape-Reading Use

### Watchlist State

Move a symbol into active observation when:

```text
streak_length >= 5
extension_failure_3 = true
midpoint_break_3 = true
```

This is the broadest validated early context shift.

### Transition Confirmation

Upgrade the read when:

```text
streak_length >= 5
extension_failure_3 = true
vwap_reclaim_3 = true
```

This suggests the old streak has likely lost control.

### Do-Not-Fight State

Strongest transition state:

```text
streak_length >= 5
extension_failure_3 = true
vwap_reclaim_3 = true
midpoint_break_3 = true
```

Use this as a context warning against blindly fading the new opposite structure.

## Directional Examples

### Red Streak

Watch for bullish context only after:

- a 5+ red box streak,
- downside extension failure,
- break above prior red box midpoint,
- and ideally reclaim of VWAP.

Without midpoint/VWAP reclaim, the red streak can still continue.

### Green Streak

Watch for bearish context only after:

- a 5+ green box streak,
- upside extension failure,
- break below prior green box midpoint,
- and ideally loss of VWAP.

Without midpoint/VWAP loss, the green streak can still continue.

## Caveats

- All boxes are confirmed only after the 5-minute candle closes.
- Forward labels must never be used as same-bar input features.
- VWAP reclaim is partly outcome-near; treat it as confirmation, not prediction.
- This playbook does not define entries, stops, targets, sizing, or PnL.
- The dataset covers the current baseline universe only: SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMD, META.
- Ad-hoc ticker reports should be run before applying the same read to a new symbol.

## Next Research Step

The next useful research task is not another broad feature table.

Build a visual casebook:

- sample 20-50 events for each must-watch context,
- inspect charts around the event,
- classify whether the context was tradable, late, noisy, or clean,
- then decide whether a TradingView overlay should mark these states live.

