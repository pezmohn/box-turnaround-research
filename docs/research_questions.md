# Research Questions

## Core Questions

1. How long do same-color box streaks typically last?
2. How does continuation probability change after 1, 2, 3, 4, and 5+ boxes?
3. In which session buckets do long red/green streaks occur most often?
4. Which features increase the probability of the next confirmed box being opposite direction?
5. Which features increase the probability of a real turnaround rather than a pause?
6. Is extension failure after a long streak predictive?
7. Is ADX fade after a long streak predictive?
8. Is VWAP reclaim/loss predictive?
9. Are shrinking box ranges after a streak predictive of exhaustion?
10. Are these effects stable out-of-sample and across symbols?
11. Do confirmed-box streaks and turnaround probabilities differ between in-play and out-of-play symbol-days?
12. Does the indicator produce cleaner context when premarket volume and gap are elevated?

## Provisional Context Labels

These are labels for research, not executable trade rules.

### continuation

Original streak direction continues and a same-direction extension/new extreme is achieved before meaningful opposite structure appears.

### opposite_box

The next confirmed box after the current event is opposite direction.

### turnaround_candidate

A candidate bullish turnaround after a red streak requires, by default:

- red streak length >= `min_streak`
- confirmed green box appears
- price reclaims VWAP or breaks above the midpoint of the last red trend box within `forward_window`
- original downside extension is not hit first

A candidate bearish turnaround after a green streak uses the inverse conditions.

### failed_turnaround

An opposite box appears, but price resumes original streak direction and hits the original extension/new extreme before the context transition is confirmed.

### exhaustion

A same-direction streak shows at least one exhaustion condition:

- ADX fades from streak high
- same-direction extension fails
- box ranges shrink
- price stalls near extension
- volume confirms less continuation than prior boxes

## Default Parameter Grid

```text
min_streak: 2, 3, 4, 5
forward_windows: 3, 6, 12 boxes
adx_drop_thresholds: 1.5, 3.0, 5.0
extension_targets: 1.2772, 1.4144, 1.618, 2.272
```

## Desired Outputs

- Streak survival table by direction and session bucket.
- Heatmap: P(opposite box next) by streak length x session bucket.
- Heatmap: P(turnaround_candidate) by streak length x ADX fade bucket.
- Heatmap: P(continuation extension hit) by streak length x VWAP distance bucket.
- Heatmap: P(turnaround_candidate) by streak length x in-play classification.
- Distribution of remaining streak length after each observed streak length.
- Feature-importance analysis for `turnaround_candidate` using a simple, explainable model.
- Written caveats and validation notes.
