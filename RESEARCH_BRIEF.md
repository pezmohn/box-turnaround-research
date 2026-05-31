# Research Brief

## Objective

Analyze the MTF Breakout Box indicator as a discretionary market-context tool, not as a finished mechanical trading strategy.

The trader currently uses the indicator for realtime tape-reading/context. There are no hard trade rules yet. The research goal is to quantify what the indicator is showing:

- how long confirmed 5-minute green/red box phases tend to last
- which session windows produce long same-direction box streaks
- which measurable conditions favor continuation vs turnaround
- whether exhaustion features such as extension failure, ADX fade, VWAP reclaim/loss, and shrinking box ranges have predictive value

Do not start with PnL optimization. First build a market-state/event dataset and test whether the context labels are stable.

## Source Indicator Concept

The Pine indicator prints confirmed 5-minute breakout boxes:

- Long/green box: current confirmed 5m candle breaks above the prior 5m candle, optionally by close confirmation.
- Short/red box: current confirmed 5m candle breaks below the prior 5m candle, optionally by close confirmation.
- Box range is based on recent 5m highs/lows.
- Optional filters include ADX, session, VWAP, volume, and minimum ATR range.
- The indicator plots 0.236, 0.5, and extension levels.
- A Ghost Box exists for realtime preview, but should not be used for historical labels unless intrabar reconstruction is possible.

## Key Framing

This is not yet a trading strategy.

Treat the system as a market-state classifier and context research problem. A useful output is a calibrated read such as:

```text
Current state:
- Red streak: 4 boxes
- Session bucket: 10:00-10:30
- ADX: falling
- VWAP distance: extended
- Last extension: failed

Historical read:
- Opposite box next: 46%
- Turnaround candidate within 3 boxes: 38%
- Continuation extension hit: 29%
- Median remaining streak length: 1 box
```

## First Research Hypothesis

After a same-color box streak, the probability of a meaningful opposite-direction transition increases when:

- streak length is elevated relative to the session norm
- ADX fades from the streak high
- the latest same-direction extension fails
- price reclaims/loses VWAP against the streak direction
- the opposite box breaks the midpoint of the last trend box
- box ranges stop expanding or begin shrinking

## Required Discipline

- Avoid lookahead bias. A box event can only use information available at the close of that box.
- Separate research and validation periods.
- Report sample size for every conditional probability.
- Do not recommend optimized parameters unless they survive out-of-sample validation.
- Document every ambiguous assumption in `docs/assumptions.md`.
